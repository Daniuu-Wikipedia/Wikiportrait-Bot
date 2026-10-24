"""
A module to couple Wikiportret Core to some very handy Flask utilities
"""
# import flask
import toolforge

from Wikiportret_core import Image
import Wikiportret_db_utils as dbut
import datetime as dt
import json


class WebImage(Image):
    def __init__(self, file, name, config, user, connection=None):
        super().__init__(file, name)
        self.dbname = config['DB_NAME']
        self.verify_OAuth(config, user=user, connection=connection)  # Automatically verify OAuth

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


# Define custom exception for dealing with incorrect data
class WikiError(Exception):
    def __str__(self):
        return 'Something went wrong while loading the data from the wiki'


class SessionAccessError(Exception):
    """Raised when a session does not exist or does not belong to the requesting user"""
    def __str__(self):
        return 'That session does not exist or belongs to someone else'


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
                   any_user=False):
    """
    Reads a session number & will then parse all relevant output form the db.
    Method takes the following arguments:
        * session number: integer representing a session in the database
        * user: user id (int) or username (str) of the requesting user. The session must belong to this user,
          otherwise (or if no user is given) SessionAccessError is raised.
        * connection: an open db connection to reuse. If omitted, one is opened (and closed) here.
        * any_user: skip the ownership check (only for the background jobs, which act on any session)
    """
    connection_passed = connection is not None
    if connection is None:
        # Since we need to run a few queries, we will just use one steady connection
        connection = toolforge.toolsdb(config['DB_NAME'])
    try:
        return _create_from_db(session_number, config, retrieve_claims, adjust_input_data,
                               check_status, user, any_user, connection)
    finally:
        if not connection_passed:
            connection.close()


def _create_from_db(session_number, config, retrieve_claims, adjust_input_data, check_status, user, any_user,
                    connection):
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
    output = WebImage(file, page, config, operator_id, connection=connection)

    # Fourth job: obtain the relevant parameters from the db
    if retrieve_claims is True:
        query = "SELECT * FROM claims WHERE session_id=%s;"
        result = dbut.query_db(query, dbname, connection=connection, params=(session_number,))
        output.qid, output.mid = result[3], result[4]
        output.wikidata_claims_json = result[1]  # JSON loading is done through the property
        output.commons_claims_json = result[2]
        output.comtext = result[5]

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
    # 20260405 - addition to fix the bugs with birth dates...
    output.date_born()
    output.date_deceased()
    output.get_date_from_commons_text()  # 20260405 - let's give it a try
    return output
