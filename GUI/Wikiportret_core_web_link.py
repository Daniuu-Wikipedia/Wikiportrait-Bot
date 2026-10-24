"""
A module to couple Wikiportret Core to some very handy Flask utilities
"""
# import flask
import toolforge

from Wikiportret_core import Image, NlBot
import Wikiportret_db_utils as dbut
import Wikiportret_job_signature as job_signature
import datetime as dt
import json
import re

# Templates that mark a file on Commons as a Wikiportret upload (same patterns as Image.ticket)
TICKET_TEMPLATES = (r'\{\{wikiportrait2\|\d{16}', r'\{\{PermissionTicket\|id=\d{16}')


class WebImage(Image):
    """
    An Image that is processed through the web interface.

    Who makes the edits (only Wikidata can trigger maxlag, see Wikiportret_core):
        * The operator, with their own OAuth tokens: everything on the Dutch Wikipedia and on Commons, except the
          category (see next point). Done during the first attempt, so never postponed.
        * The operator if their tokens are still stored, otherwise the bot account (acting_as_bot is True):
          only the parts that were postponed because of Wikidata, i.e. the Wikidata edits and creating & adding
          the category on Commons.
    Whether the bot account is acting is decided once, in __init__, and is available as acting_as_bot.
    """

    def __init__(self, file, name, config, user, connection=None, bot_credentials=None):
        super().__init__(file, name)
        self.dbname = config['DB_NAME']
        self.acting_as_bot = False  # True if the edits are made by the bot account instead of the user
        try:
            self.verify_OAuth(config, user=user, connection=connection)  # Edits are made as the operator
        except LookupError:  # The user's tokens are gone (e.g. removed at logout): only a postponed job gets here
            if bot_credentials is None:
                raise
            print(f'No tokens stored for {user!r}: edits for {file!r} will be made by the bot account')
            for bot in (self._commons, self._wikidata, self._nl, self._meta):
                bot.verify_OAuth(bot_credentials)  # Same validation as the command line version of the bot
            self.acting_as_bot = True
            # Work with the Wikidata claims that are stored in the db (refreshed after every attempt) instead of
            # reading them again: Wikidata being overloaded is the reason that this job is stuck in the first place
            self.reuse_claims = True
            try:
                self.verify_bot_target()  # The db is not trusted blindly when the bot account does the work
            except UnverifiedTargetError:
                raise
            except Exception as error:  # E.g. network problems: what cannot be verified is not edited
                raise UnverifiedTargetError(f'Could not verify the target of the job: {error!r}') from error

    def job_fields(self, session_number, operator_id):
        """The fields that are signed when a job is submitted (and checked before the bot account may finish it)"""
        return {'session_id': session_number, 'operator_id': operator_id, 'page': self.name, 'file': self.file,
                'qid': self.qid, 'mid': self.mid, 'caption': self.caption, 'category': self.catname,
                'summary': self.sum}

    def verify_job_signature(self, config, session_number, operator_id, signature):
        """Refuse to continue (UnverifiedTargetError) if the job was not signed by the web app, see job_signature"""
        if not job_signature.verify_job(config, signature, **self.job_fields(session_number, operator_id)):
            raise UnverifiedTargetError('The job has no valid signature: it was changed in the db or never approved')

    def verify_bot_target(self):
        """
        Before the bot account is used on behalf of a (long gone) operator, check that the target is a legit
        Wikiportret job according to the wikis themselves, so rows tampered with in the db cannot aim the bot at
        arbitrary pages or files. Raises UnverifiedTargetError if something does not add up.

        Read-only: nothing is edited here. The bot account only reads the Dutch Wikipedia and Commons for this check;
        it never edits them (those edits are always made by the operator, see the class docstring).
        """
        info = next(iter(self._nl.get({'action': 'query', 'titles': self.name, 'prop': 'info'})
                         .get('query', {}).get('pages', {}).values()), {})
        if not info or 'missing' in info or 'invalid' in info or info.get('ns') != 0 or 'redirect' in info:
            raise UnverifiedTargetError(f'{self.name!r} is not an existing article on the Dutch Wikipedia')

        # Always read the file page live: the copy of the text in the db is not trusted either
        wikitext = (self._commons.get({'action': 'parse', 'page': f'File:{self.file}', 'prop': 'wikitext'})
                    .get('parse', {}).get('wikitext', {}).get('*', ''))
        if not any(re.search(pattern, wikitext) for pattern in TICKET_TEMPLATES):
            raise UnverifiedTargetError(f'File:{self.file} is not a Wikiportret upload (no VRT ticket template)')

    def verify_OAuth(self, config, secret=None, user=None, connection=None):  # Overloading from parent class
        if secret is None:
            if isinstance(user, (int, str)):
                secret = dbut.get_tokens_from_db(self.dbname, user, connection=connection)
            else:
                raise TypeError('Only integers and strings are accepted as input for the user!')

        # Call OAuth verification subroutines for separate bots
        self._commons.verify_OAuth_web(config, secret)
        self._wikidata.verify_OAuth_web(config, secret)
        self._nl.verify_OAuth_web(config, secret)
        self._meta.verify_OAuth_web(config, secret)
        del secret  # Destroy these immediately for obvious reasons

    def write_to_db(self, session_number, connection=None):
        connection_provided = connection is None
        if connection is None:
            connection = toolforge.toolsdb(self.dbname)
        if self.claims is None:
            self.ini_wikidata()
        if self.comtext is None:
            self.get_commons_text()
        if self.mc is None:
            self.get_commons_claims()
        query = """
        insert into `claims` (`session_id`, `json_response`, `commons_claims`, `qid`, `mid`, `comm_text`)
        values  (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        json_response = VALUES(json_response),
        commons_claims = VALUES(commons_claims),
        comm_text = VALUES(comm_text),
        qid = VALUES(qid)
        ;
        """
        dbut.adjust_db(query, self.dbname, connection=connection,
                       params=(session_number, self.wikidata_claims_json, json.dumps(self.mc),
                               self.qid, self.mid, self.comtext))
        if connection_provided is True:
            connection.close()

    def input_data_to_db(self, session_number, connection=None):
        connection_provided = connection is None
        if connection is None:
            connection = toolforge.toolsdb(self.dbname)
        query = """
        INSERT INTO input_data (`session_id`, `custom_caption`, `category_name`, `edit_summary`, `ticket`)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        category_name = VALUES(category_name),
        edit_summary = VALUES(edit_summary),
        custom_caption = VALUES(custom_caption)
        ;
        """
        dbut.adjust_db(query, self.dbname, connection=connection,
                       params=(session_number, self.caption, self.catname, self.sum, self.ticket_number))

        if self.date is not None:
            query = """
            UPDATE input_data
            SET date = %s
            WHERE session_id = %s;
            """
            dbut.adjust_db(query, self.dbname, connection=connection,
                           params=('%4d-%02d-%02d' % (self.date.year, self.date.month, self.date.day),
                                   session_number))

        # And now time to add the birth & death date of the subject
        if self.birth is not None:
            query = """
                    UPDATE input_data
                    SET birth_date = %s
                    WHERE session_id = %s;
                    """
            dbut.adjust_db(query, self.dbname, connection=connection,
                           params=('%4d-%02d-%02d' % (self.birth.year, self.birth.month, self.birth.day),
                                   session_number))

        if self.death is not None:
            query = """
                    UPDATE input_data
                    SET death_date = %s
                    WHERE session_id = %s;
                    """
            dbut.adjust_db(query, self.dbname, connection=connection,
                           params=('%4d-%02d-%02d' % (self.death.year, self.death.month, self.death.day),
                                   session_number))
        if connection_provided is True:
            connection.close()

    # Part 1 of the extension: additional properties for interaction with the session
    @property
    def claims_dict(self):  # Goal of property is to secure the required information
        return self.claims

    @claims_dict.setter
    def claims_dict(self, value):
        if isinstance(value, dict):
            self.claims = value
            # Also update the chap's date of birth & date of death
            # These are not automatically read when an object is reset from the db
            self.date_born()
            self.date_deceased()

    @property
    def wikidata_claims_json(self):
        """
        Property that generates the json string for use in the _claims_ table
        """
        return json.dumps(self.claims)

    @wikidata_claims_json.setter
    def wikidata_claims_json(self, value):
        if isinstance(value, dict):
            self.claims_dict = value
        elif isinstance(value, str):
            self.claims_dict = json.loads(value)  # Directly load claims from JSON

    @property
    def commmons_claims(self):
        return self.mc

    @commmons_claims.setter
    def commmons_claims(self, value):
        if isinstance(value, dict):
            self.mc = value

    @property
    def commons_claims_json(self):
        """
        Generates the json string for use in the _claims_ table.
        """
        return json.dumps(self.mc)

    @commons_claims_json.setter
    def commons_claims_json(self, value):
        if isinstance(value, dict):
            self.mc = value
        elif isinstance(value, str):
            self.mc = json.loads(value)

    @property
    def ticket_number(self):
        if self.mc is None:
            self.mc = {}  # If stuff goes wrong
        parent = self.mc.get('P6305', None)
        if parent is not None:
            # noinspection PyUnresolvedReferences
            parent = parent[0]
            return int(parent['mainsnak']['datavalue']['value'])
        return self.ticket(action=False)

    def get_commons_text(self, session=None, connection=None):
        super().get_commons_text(True)
        if session is not None:
            query = """
            UPDATE claims
            set comm_text = %s
            where session_id = %s;
            """
            dbut.adjust_db(query, self.dbname, connection=connection, params=(self.comtext, session))
        return self.comtext

    def ini_wikidata(self, session=None, connection=None):
        super().ini_wikidata()
        if session is not None:
            query = """
                        UPDATE claims
                        set json_response = %s
                        where session_id = %s;
                        """
            dbut.adjust_db(query, self.dbname, connection=connection,
                           params=(self.wikidata_claims_json, session))
        return self.qid, self.claims


BOT_SUMMARY_NOTE = 'finished by bot account'  # Marks summaries that were already adjusted (keeps this idempotent)


def attributed_summary(summary, username):
    """
    The edit summary, extended with who requested the edit and the fact that the bot account makes it.
    Edit summaries are cut off at 500 bytes by MediaWiki, so the user's part is shortened (by bytes) to keep the note.
    """
    if BOT_SUMMARY_NOTE in summary:
        return summary
    note = f' (requested by {username}, {BOT_SUMMARY_NOTE})'
    room = max(500 - len(note.encode('utf8')), 0)
    return summary.encode('utf8')[:room].decode('utf8', 'ignore') + note


def attribute_open_jobs(config, user_id, username):
    """
    To be called BEFORE the tokens of an operator are removed (logout): from that moment on, the bot account may have
    to finish the jobs that are still open. Their edit summary (input_data.edit_summary) is extended with the name of
    the operator, so the edits of the bot account still say who requested them.

    Only jobs that the bot account can end up with are touched: 'ready' (not started yet) and 'maxlag' (postponed).
    A job that is 'up' right now keeps its summary: the running attempt rewrites input_data at the end, which would
    undo the change and invalidate the signature. If such a job maxlags, the bot account refuses it (signature) and the
    job is listed on the failed jobs page.

    The edit summary is part of the signed job fields (see Wikiportret_job_signature). So the signature is checked
    first, and only a job that was properly signed gets a new signature: re-signing a job that has been tampered
    with would approve the tampering. Summary and signature change in one statement, so a run of the maxlag handler
    can never see the one without the other. Problems are only printed: logging out must never be blocked.
    """
    if dbut.LOCAL_DEV:
        return
    dbname = config['DB_NAME']
    connection = toolforge.toolsdb(dbname)
    try:
        jobs = dbut.query_db("SELECT session_id FROM sessions WHERE operator_id=%s AND status IN ('ready', 'maxlag')",
                             dbname, need_all=True, connection=connection, params=(user_id,))
        for (session_id,) in jobs:
            try:
                job = create_from_db(session_id, config, check_status=False, user=user_id, connection=connection)
                was_signed = job_signature.verify_job(config, job.signature, **job.job_fields(session_id, user_id))
                job.sum = attributed_summary(job.sum, username)
                signature = (job_signature.sign_job(config, **job.job_fields(session_id, user_id))
                             if was_signed else job.signature)
                dbut.adjust_db("UPDATE input_data i JOIN sessions s ON s.session_id = i.session_id "
                               "SET i.edit_summary = %s, s.signature = %s "
                               "WHERE i.session_id = %s AND s.operator_id = %s",
                               dbname, connection=connection, params=(job.sum, signature, session_id, user_id))
            except Exception as error:
                print(f'Could not adjust the summary of session {session_id}: {error!r}')
    finally:
        connection.close()


FAILED_JOBS_PAGE = 'Gebruiker:Daniuu/Failed_jobs'  # Page on nlwiki where failed jobs of the bot account are listed


def log_failed_job(bot_credentials, session_id, name, file, signature):
    """
    Append a line about a job that the bot account could not finish to FAILED_JOBS_PAGE (text only), so that it
    can be picked up manually. This is an edit of the bot account on the Dutch Wikipedia, but only to log a failure:
    it never places images in articles. The values come from the db, which is not trusted: everything is put in <nowiki>
    tags (after removing angle brackets, so the tags cannot be closed early) and cut to a sane length, so a
    tampered row cannot inject links, templates or markup into a public page.
    """
    def plain(text):
        return '<nowiki>' + re.sub(r'[<>\r\n]+', ' ', str(text))[:200] + '</nowiki>'

    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M')
    line = f'\n* {stamp} (UTC) – sessie {int(session_id)} – {plain(name)} – {plain(file)} – hash {plain(signature)}'
    nlwiki = NlBot()
    nlwiki.verify_OAuth(bot_credentials)  # The bot account logs its own failures
    response = nlwiki.post({'action': 'edit', 'title': FAILED_JOBS_PAGE, 'appendtext': line,
                            'summary': 'Failed job logged', 'bot': True})
    if 'error' in response:
        raise RuntimeError(f'Could not write to {FAILED_JOBS_PAGE}: {response["error"]}')


# Define custom exception for dealing with incorrect data
class WikiError(Exception):
    def __str__(self):
        return 'Something went wrong while loading the data from the wiki'


class SessionAccessError(Exception):
    """Raised when a session does not exist or does not belong to the requesting user"""
    def __str__(self):
        return 'That session does not exist or belongs to someone else'


class UnverifiedTargetError(Exception):
    """Raised when the bot account is asked to edit a page/file that the wikis do not confirm as a Wikiportret job"""
    def __str__(self):
        return (self.args[0] if self.args else
                'The target of this job could not be verified, refusing to edit with the bot account')


class BackgroundError(Exception):
    def __str__(self):
        return 'The bg job is down!'


class TimeError(Exception):
    def __str__(self):
        return 'Still processing in the background'


def date_from_db(string):
    # Not ideal, but a fix that will hold while I figure out the issues with the db & string formatting
    year, month, day = string.split('-')
    return dt.date(int(year), int(month), int(day))


def create_from_db(session_number,
                   config,
                   retrieve_claims=True,
                   adjust_input_data=True,
                   check_status=True,
                   user=None,
                   connection=None,
                   any_user=False,
                   bot_credentials=None):
    """
    Reads a session number & will then parse all relevant output form the db.
    Method takes the following arguments:
        * session number: integer representing a session in the database
        * user: user id (int) or username (str) of the requesting user. The session must belong to this user,
          otherwise (or if no user is given) SessionAccessError is raised.
        * connection: an open db connection to reuse. If omitted, one is opened (and closed) here.
        * any_user: skip the ownership check (only for the background jobs, which act on any session)
        * bot_credentials: path of a token file of the bot account. Only used if the user's own tokens are missing,
          which only happens for jobs that were postponed (maxlag): edits are then made by the bot account instead of
          the operator (see WebImage for which edits that may be).
    """
    connection_passed = connection is not None
    if connection is None:
        # Since we need to run a few queries, we will just use one steady connection
        connection = toolforge.toolsdb(config['DB_NAME'])
    try:
        return _create_from_db(session_number, config, retrieve_claims, adjust_input_data,
                               check_status, user, any_user, connection, bot_credentials)
    finally:
        if not connection_passed:
            connection.close()


def _create_from_db(session_number, config, retrieve_claims, adjust_input_data, check_status, user, any_user,
                    connection, bot_credentials):
    # To make our life slightly easier...
    dbname = config['DB_NAME']

    # First job: check in the db what file & nlwiki page the user wishes to process
    # Ownership is verified in the very same query
    if user is None and not any_user:
        raise SessionAccessError()
    if any_user:
        query = "SELECT * FROM sessions WHERE session_id=%s;"
        params = (session_number,)
    elif isinstance(user, int):
        query = "SELECT * FROM sessions WHERE session_id=%s AND operator_id=%s;"
        params = (session_number, user)
    else:
        query = ("SELECT s.* FROM sessions s JOIN users u ON u.user_id = s.operator_id "
                 "WHERE s.session_id=%s AND u.username=%s;")
        params = (session_number, user)
    result = dbut.query_db(query, dbname, connection=connection, params=params)  # Get relevant row as a tuple
    if result is None:
        raise SessionAccessError()
    operator_id = result[1]  # Operator id, needed further down the road
    page, file = result[2], result[3]  # Make life slightly easier & shorten notation
    status = result[4]
    signature = result[8] if len(result) > 8 else None  # Added by the web app when the operator submits the job

    # Error handling section
    if check_status:  # Allow for manually bypassing the status check
        match status:
            case 'failed':
                raise WikiError('That did not work')
            case 'processing':
                raise TimeError('Still processing in the background')
            case 'pending':
                raise BackgroundError('BG JOB IS DOWN!!!')

    # Third job: all input is there to generate the WebImage desperately needed
    output = WebImage(file, page, config, operator_id, connection=connection, bot_credentials=bot_credentials)
    output.signature = signature  # Stored as it was loaded, so it can be verified (and renewed) later on

    # Fourth job: obtain the relevant parameters from the db
    if retrieve_claims is True:
        query = "SELECT * FROM claims WHERE session_id=%s;"
        result = dbut.query_db(query, dbname, connection=connection, params=(session_number,))
        output.qid, output.mid = result[3], result[4]
        output.wikidata_claims_json = result[1]  # JSON loading is done through the property
        output.commons_claims_json = result[2]
        output.comtext = None if output.acting_as_bot else result[5]  # The bot account never trusts the db copy

        # Fifth job: if there is already some customized input data, get it
        if adjust_input_data is True:
            query = "SELECT * FROM input_data WHERE session_id=%s;"
            result = dbut.query_db(query, dbname, connection=connection, params=(session_number,))
            # Now set the relevant properties
            if result[1] is not None:
                output.caption = result[1]
            if result[2] is not None:
                output.date = date_from_db(result[2])
            if result[4] is not None:
                output.catname = result[4]  # 20260314 - HACKATHON: old property name called
            if result[5] is not None:
                output.sum = result[5]
            if result[7] is not None:
                output.birth = date_from_db(result[7])
            if result[8] is not None:
                output.death = date_from_db(result[8])
            # Result 3 = ticket number, we don't need it for now
            # Result 6 = used only for the db and cleanup scripts

    # The bot account only finishes jobs that the web app signed when the operator submitted them
    # This is checked on the values as loaded above, before any (date) logic below touches the wikis
    if output.acting_as_bot:
        output.verify_job_signature(config, session_number, operator_id, signature)
    # 20260405 - addition to fix the bugs with birth dates...
    output.date_born()
    output.date_deceased()
    output.get_date_from_commons_text()  # 20260405 - let's give it a try
    return output
