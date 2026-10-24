# Required inputs from the flask module
# Flask: the core app, incorporating all functionality to set up a proper web page
# render_template: the functionality to deal with .html-templates
# request: to be able to handle requests using the Flask library
import mwoauth
import requests
import json  # Makes life slightly easier

import flask
# Import Toolforge to update the user agent of the app
import toolforge

# Some datetime stuff
import datetime as dt

# Import some auxiliary classes
import os
import re
import hmac
import secrets
import urllib.parse
from objects import SiteSettings

# from Wikiportret_core import Image
import Wikiportret_core_web_link as wcl
from Wikiportret_core import ERROR_MESSAGES
import Wikiportret_API_utils as wpor_api
import Wikiportret_db_utils as db_utils
import Wikiportret_job_signature as job_signature
import Wikiportret_config

toolforge.set_user_agent('Wikiportret-updater',
                         email='wikiportret@wikimedia.org')  # Just setting up a custom user agent

data = SiteSettings()

# Define the application (this will be the object representing the web page we're interested in)
app = flask.Flask(__name__)

# Load configuration: config.toml and/or the WPOR_ environment variables (see Wikiportret_config)
__dir__ = os.path.dirname(__file__)
app.config.update(Wikiportret_config.load_config())

# 20261024 - CSRF protection (part 1): browsers do not send the session cookie along with POST requests that other
# sites make, so those requests arrive without a login. Can be overruled in config.toml, but should not be
# (Flask's own default is None, so setdefault would not work here)
if app.config.get('SESSION_COOKIE_SAMESITE') is None:
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


# CSRF protection (part 2): every form carries a secret token that is only known to this login session
# A page on another website cannot read it, so it cannot make a POST request that passes the check below
def csrf_token():
    """The CSRF token of this session (created on first use). Use it in templates as {{ csrf_token() }}"""
    if 'csrf_token' not in flask.session:
        flask.session['csrf_token'] = secrets.token_urlsafe(32)
    return flask.session['csrf_token']


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def check_csrf_token():
    """Refuses every POST request without the CSRF token of this session (hidden field csrf_token in each form)"""
    if flask.request.method != 'POST':
        return None
    expected = flask.session.get('csrf_token')
    received = flask.request.form.get('csrf_token', '')
    if expected is None or not hmac.compare_digest(expected, received):  # Constant time comparison
        # Usually harmless: e.g. a form that was opened before the login session ended. Just ask to try again
        return flask.render_template('error.html',
                                     message='Dit formulier is verlopen of niet geldig. '
                                             'Laad de pagina opnieuw en probeer het nog eens.',
                                     user_name=flask.session.get('username')), 400
    return None


# General utility
def credentials_valid():
    """
    True if the logged in user can still work: the login is less than an hour old (token_expiry in the session
    cookie) AND the db still holds their tokens. The db removes tokens older than an hour on its own schedule, so
    the two can be out of sync for a little while: both have to be checked.
    """
    expiry = flask.session.get('token_expiry')
    if expiry is None or dt.datetime.utcnow() > dt.datetime.fromisoformat(expiry):
        return False
    user_id = db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME'], cache=flask.session)
    return user_id is not None and db_utils.has_tokens(user_id, app.config['DB_NAME'])


def check_login_data(origin=None):
    """
    Method to perform some checks concerning the loading of data, user identity & session id.

    Method is designed to replace some repeated checks that need to be performed while loading.

    Argument origin contains the page that is being loaded (to avoid getting circular redirects

    If a check fails, the redirect is raised through flask.abort, so the calling route stops immediately
    (a returned redirect would just be ignored by the caller).
    """
    if app.config.get('LOCAL_DEV'):
        return  # Bypass restriction locally
    if origin not in {'login', 'logout', 'oauth-callback', 'renew'}:
        if flask.session.get('username') is None:
            flask.abort(flask.redirect(flask.url_for('login')))  # Never logged in (or cookie gone): just log in
        if not credentials_valid():
            # 20261024 - logged in before, but the credentials expired or were removed from the db (after an hour)
            flask.abort(flask.redirect(flask.url_for('renew')))
        # These pages do not belong to a running session ('load' is where a new session gets created)
        if origin not in {'input', 'load', 'uploads'}:
            if 'session_id' not in flask.session:
                flask.abort(flask.redirect(flask.url_for('input')))
    return  # Return None, nothing to do here...


@app.route('/')
def index():
    if app.config.get('LOCAL_DEV'):
        flask.session['username'] = "TestGebruiker"
        return flask.redirect(flask.url_for('input'))
    
    username = flask.session.get('username', None)
    # For development purposes only: manually override the username
    if username is None:
        return flask.render_template(
            'index.html', username=None)
    # In case user is already logged in, continue
    return flask.redirect(flask.url_for('input'))


@app.route('/login', methods=['GET'])
def login():
    """Initiate an OAuth login.

    Call the MediaWiki server to get request secrets and then redirect the
    user to the MediaWiki server to sign the request.
    """
    flask.session.clear()  # Triggers a new login
    consumer_token = mwoauth.ConsumerToken(
        app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'])
    # noinspection PyBroadException
    try:
        redirect, request_token = mwoauth.initiate(
            app.config['OAUTH_MWURI'], consumer_token)
    except Exception:
        app.logger.exception('mwoauth.initiate failed')
        return flask.redirect(flask.url_for('index'))
    else:
        flask.session['request_token'] = dict(zip(
            request_token._fields, request_token))
        return flask.redirect(redirect)


@app.route('/oauth-callback')
def oauth_callback():
    """OAuth handshake callback."""
    if 'request_token' not in flask.session:
        flask.flash('De OAuth-callback is mislukt. Staan cookies mogelijk uitgeschakeld?')
        return flask.redirect(flask.url_for('index'))

    consumer_token = mwoauth.ConsumerToken(
        app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'])

    try:
        access_token = mwoauth.complete(
            app.config['OAUTH_MWURI'],
            consumer_token,
            mwoauth.RequestToken(**flask.session['request_token']),
            flask.request.query_string)

        identity = mwoauth.identify(
            app.config['OAUTH_MWURI'], consumer_token, access_token)
    except Exception:
        app.logger.exception('OAuth authentication failed')
        return flask.redirect(flask.url_for('index'))

    else:
        # Verify that the user is actually authorized
        user_id = db_utils.get_user_id(identity['username'], app.config['DB_NAME'])  # Safety check
        if user_id is None:
            return flask.abort(403)  # Error, do not continue
        # Store the access_token
        token_to_store = dict(zip(access_token._fields, access_token))
        # Obtain a valid (bare) key from the Wikiportret API, only the API utils talk to that API
        try:
            wikiportret_key = wpor_api.request_wikiportret_key()  # Generated under a bot account
        except requests.RequestException:
            # The Wikiportret API being down must not block the login: an empty value is stored, and the first
            # call that needs the key creates it then (wpor_api.get_wikiportret_key)
            app.logger.exception('Could not get a key from the Wikiportret API')
            wikiportret_key = ''

        # Write data to the db (tokens table)
        # On duplicate key overwrites tokens if needed

        # 20260314 - stuff moved to separate table
        sec = {}
        for i, j in token_to_store.items():
            sec[i] = db_utils.store_secret(j, app.config['DB_NAME'])  # Only the ciphertext is kept
        del token_to_store  # Get rid of the raw tokens asap

        # 20261024 - the Wikiportret key is encrypted the same way (own nonce). Only the bare key is stored: the
        # 'Bearer ' prefix is added again when the key is read (wpor_api.get_wikiportret_key)
        if wikiportret_key:
            wikiportret_key = db_utils.store_secret(wikiportret_key, app.config['DB_NAME'])

        query = """
        INSERT INTO tokens (operator_id, oauth_token, wikiportrait_token)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            oauth_token = VALUES(oauth_token),
            wikiportrait_token = VALUES(wikiportrait_token),
            `timestamp` = NOW();
        """
        # And now, time to push this to the db
        db_utils.adjust_db(query, app.config['DB_NAME'],
                           params=(user_id, json.dumps(sec), wikiportret_key))
        del sec  # Delete as soon as we don't need it anymore

        # Store the username in the session (just making my life slightly easier)
        # For security reasons, the underlying keys are never shown to the user
        # Even though flask.session has some security built in to prevent tampering with the session cookie
        flask.session['username'] = identity['username']
        flask.session['user_id'] = user_id  # Cached so that other pages do not need to look it up again

        # 20260409 - extension to avoid login issues (tokens automatically removed after some time)
        expiry = dt.datetime.utcnow() + dt.timedelta(hours=1)
        flask.session['token_expiry'] = expiry.isoformat()
        del expiry

    return flask.redirect(flask.url_for('input'))  # After logging in, direct user to login screen



# Jobs that were not submitted yet: dropped when the login of their operator expired (see renew)
# Submitted jobs ('ready' and later) are kept: the background job or the bot account finishes them without the user
UNSUBMITTED_STATUSES = ('pending', 'processing', 'completed', 'failed')


def discard_unsubmitted_session():
    """
    Removes the job the user was working on (flask.session['session_id']) if it was not submitted yet.
    Returns True if a job was removed. Never raises: the renew page must always be shown.
    """
    session_id = flask.session.pop('session_id', None)
    user_id = flask.session.get('user_id')
    if session_id is None or user_id is None:
        return False
    try:
        dbname = app.config['DB_NAME']
        row = db_utils.query_db("SELECT status FROM sessions WHERE session_id=%s AND operator_id=%s;", dbname,
                                params=(session_id, user_id))
        if row is None or row[0] not in UNSUBMITTED_STATUSES:
            return False
        # claims & messages follow through ON DELETE CASCADE; input_data has no foreign key, so it goes separately
        db_utils.adjust_db("DELETE FROM input_data WHERE session_id=%s;", dbname, params=(session_id,))
        db_utils.adjust_db("DELETE FROM sessions WHERE session_id=%s AND operator_id=%s AND status IN %s;", dbname,
                           params=(session_id, user_id, UNSUBMITTED_STATUSES))
        return True
    except Exception:
        app.logger.exception('Could not remove session %r after the login expired', session_id)
        return False


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    """Log the user out by clearing their session."""
    # 20261024 - logging out deletes data, so it only happens through the (CSRF protected) logout form
    # A plain link (old bookmark, or a page of another website) only leads to the start page, with a logout button
    if flask.request.method != 'POST':
        return flask.redirect(flask.url_for('index'))
    # 20260314 - HACKATHON remove tokens from the db
    # Nobody logged in (e.g. session cookie expired): nothing to clean up in the db
    # 20261024 - the tokens may already be gone (removed by the db after an hour): every step below works without
    # them, and logging out must always succeed, so a failing cleanup is only logged
    username = flask.session.get('username')
    try:
        user_id = (db_utils.get_user_id(username, app.config['DB_NAME'], cache=flask.session)
                   if username is not None else None)
        if user_id is not None:
            # Once the tokens are gone, the bot account may have to finish this user's open jobs: first make sure that
            # the edit summaries of those jobs say who requested them
            wcl.attribute_open_jobs(app.config, user_id, username)

            query = 'delete from tokens where operator_id = %s'  # Removes nothing if the db already did
            db_utils.adjust_db(query, app.config['DB_NAME'], params=(user_id,))

            # 20260314 - HACKATHON remove associated entries from the db (clean up stuff)
            # 20260927 - keep the stuff that was not properly handled inside the db!
            query = (
                "DELETE FROM sessions "
                "WHERE operator_id = %s "  # User id is set through the browser itself
                "AND status = 'uploaded'"
            )
            db_utils.adjust_db(query, app.config['DB_NAME'], params=(user_id,))

            # The job that the user was working on is dropped if it was never submitted (submitted jobs, including
            # postponed ones ('maxlag'), are kept: see UNSUBMITTED_STATUSES)
            discard_unsubmitted_session()
    except Exception:
        app.logger.exception('Cleanup at logout failed for %r', username)

    flask.session.clear()  # Clears session_id, username & token_expiry
    return flask.redirect(flask.url_for('index'))


@app.route('/renew')
def renew():
    """
    Shown when the credentials of a logged in user expired or were removed from the db (automatically, after an
    hour). The job they were working on is dropped if it was not submitted yet, and they can log in again (which
    brings them back to the input form) or log out.
    """
    if app.config.get('LOCAL_DEV'):
        return flask.redirect(flask.url_for('input'))
    if flask.session.get('username') is None:
        return flask.redirect(flask.url_for('index'))  # Not logged in at all: the start page has the login button
    if credentials_valid():
        return flask.redirect(flask.url_for('input'))  # Nothing to renew (and no reason to drop any job)
    return flask.render_template('renew.html',
                                 job_removed=discard_unsubmitted_session(),
                                 user_name=flask.session['username'])


def session_errors():
    """
    The problems that the background job logged for the current session (codes: Wikiportret_core.ERROR_MESSAGES),
    for templates/error_list.html. Both the errors that stopped the job and warnings of a job that did work out.
    """
    return [{'code': code, 'message': ERROR_MESSAGES.get(code, ERROR_MESSAGES[500]), 'details': details}
            for code, details in db_utils.get_errors(flask.session.get('session_id'), app.config['DB_NAME'])]


# Race: the db removed the tokens between check_login_data and their use (e.g. while building the WebImage)
@app.errorhandler(db_utils.TokensMissingError)
def tokens_missing(e):
    return flask.redirect(flask.url_for('renew'))


# Setup up the starting screen
@app.route('/input')
def input():
    # Landing page
    # The template is stored internally in the templates-folder, there is no need to mention this in the argument
    # Perform these actions if a POST request is sent (submitted via the form)

    # 20260613 - check if all credentials are present
    check_login_data('input')
    if 'session_id' in flask.session:
        del flask.session['session_id']
    if db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME'],
                              cache=flask.session) is None:
        return flask.redirect(flask.url_for('login'))  # Back to the index - invalid username passed
    return flask.render_template('input.html',
                                 user_name=flask.session.get('username', 'TestGebruiker'))


# Create a page to be displayed while the bot is getting the initial data
@app.route('/load', methods=['POST', 'GET'])
def load():
    # 20260613 - check whether all relevant login credentials are present
    check_login_data('load')

    # This page is designed to facilitate loading relevant data in the background
    # This page must be called by the index page
    if flask.request.method == 'GET':
        return 'Deze pagina kan niet rechtstreeks geladen worden.'
    elif flask.request.method != 'POST':
        return 'Naar deze pagina kan alleen met POST verzonden worden.'
    elif db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME'],
                              cache=flask.session) is None:
        return flask.redirect(flask.url_for('login'))  # Back to the index - invalid username passed
    elif '.' not in flask.request.form['File'].strip():
        return flask.redirect(flask.url_for('input'))
    else:
        if app.config.get('LOCAL_DEV'):
            flask.session['session_id'] = 999  # Just set a dummy value for reference in the local development db
            return flask.render_template('loading.html',
                                         user_name=flask.session['username'])

        # Handle the POST request
        # In the background, we will start setting up the bot
        user_id = flask.session['user_id']  # Cached by the check above
        bot_object = wcl.WebImage(flask.request.form['File'].strip(),
                                  flask.request.form['Article'].strip(),
                                  app.config,
                                  user_id)  # Configure a new bot object
        # bot_object.verify_OAuth(app.config, user=flask.session['username'])

        # Previous versions of code set stuff to the session (now no longer needed: done via db)
        # Set stuff to the database - this goes into the sessions table
        query = """
        insert into `sessions` (`operator_id`, `page`, `file`)
        values (%s, %s, %s);
        """
        flask.session['session_id'] = db_utils.adjust_db(query,
                                                         app.config['DB_NAME'],
                                                         retrieve_id=True,
                                                         params=(user_id,
                                                                 bot_object.name,
                                                                 bot_object.file))

        # Background load is truly done in the background, by the continuous bg job

        # Redirect naar de loading pagina
        return flask.render_template('loading.html',
                                     user_name=flask.session['username'])


# Define the routing towards the review section
@app.route('/review', methods=['POST', 'GET'])
def review():
    # 20260613 - check login credentials of the user
    check_login_data('review')
    # We rendered some data - now load the template just before reviewing
    # To add: this template can only be loaded if the verification procedure has been performed!
    # Sessions that are not ready raise WikiError/BackgroundError/TimeError: the error handlers show the "loading failed" page
    if app.config.get('LOCAL_DEV'):
        class MockBot:
            def __init__(self):
                self.file = "VuilTestertje.jpg"
                self.name = "Henk Appelsien"
                self.date = dt.date(2023, 5, 12)
                self.birth = dt.date(1990, 1, 1)
                self.death = None
                self.caption = "Een dummy bijschrift voor testdoeleinden."
                self.sum = "Test upload via lokale development mode."
                self.catname = "People from Mock City"
            def input_data_to_db(self, sid): pass

        bot_object = MockBot()
    else:
        if db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME'],
                                cache=flask.session) is None:
            return flask.redirect(flask.url_for('login'))  # Back to the index - invalid username passed
        bot_object = wcl.create_from_db(flask.session['session_id'],
                                        app.config,
                                        user=flask.session['username'])  # Raises a 403 for foreign sessions
    # bot_object.verify_OAuth(app.config, user=flask.session['username'])
    return flask.render_template('review.html',
                                 license_options=wcl.WebImage.licenses.keys(),
                                 selected_license='CC-BY-SA 4.0',
                                 bot=bot_object,
                                 errors=session_errors(),  # Warnings of the loading, e.g. an invalid date
                                 user_name=flask.session['username'])


# The page the users will see whenever they submit an image for posting
@app.route('/submit', methods=['POST', 'GET'])
def submit():
    # 20260613 - check login data
    check_login_data('submit')

    # To do: clear the global object (all required stuff is dumped in the session anyway)
    if flask.request.method == 'POST':
        if app.config.get('LOCAL_DEV'):
            return flask.render_template('submit.html',
                                         user_name=flask.session.get('username', 'TestGebruiker'))

        update_dict = {}  # Key-value pairs for updating stuff in the db
        bot_object = wcl.create_from_db(flask.session['session_id'],
                                        app.config,
                                        user=flask.session['username'])  # Raises a 403 for foreign sessions
        # bot_object.verify_OAuth(app.config, user=flask.session['username'])
        # First things first: we need to adjust some values
        # But this only happens if some specific checkboxes are checked
        # If a checkbox is checked, it's name will appear in flask.request.form
        if 'checkdate' in flask.request.form:  # Date of image capture is adjusted
            bot_object.date = flask.request.form['datevalue']
            update_dict['date'] = bot_object.date
        if 'checkbirthdate' in flask.request.form:
            bot_object.birth = flask.request.form['birthdatevalue']
            update_dict['birth_date'] = bot_object.birth
        if 'checkdeathdate' in flask.request.form:
            bot_object.death = flask.request.form['deathdatevalue']
            update_dict['death_date'] = bot_object.death
        if 'checksummary' in flask.request.form:  # Use custom edit summary
            bot_object.sum = flask.request.form['summaryvalue'].strip()
            update_dict['edit_summary'] = bot_object.sum
        if 'checkcat' in flask.request.form:  # Custom category name
            bot_object.catname = flask.request.form['catvalue'].strip()  # Call the correct catname
            update_dict['category_name'] = bot_object.catname
        if 'checkcaption' in flask.request.form:  # Custom caption
            bot_object.caption = flask.request.form['captionvalue'].strip()
            update_dict['custom_caption'] = bot_object.caption
        if 'checklicence' in flask.request.form:  # Custom license, there is still a bug here...
            bot_object.license = flask.request.form['licencevalue'].strip()

        # Overwrite some custom data in the db if needed
        if update_dict:
            bot_object.input_data_to_db(flask.session['session_id'])

        # Uploading the stuff to the wiki will be done in the background, with the tokens of this operator
        # (Dutch Wikipedia & Commons edits are always theirs; only Wikidata-dependent edits can be postponed and
        # may later be finished by the bot account, see Wikiportret_core_web_link.WebImage)
        # Prepare everything for the background job
        # Sign what the operator just reviewed: only jobs carrying a valid signature may later be finished by the
        # bot account (maxlag handler). The key is not stored in the db, see Wikiportret_job_signature for the why
        # None (no key configured) simply means that the job is not eligible for the bot account
        signature = job_signature.sign_job(
            app.config,
            **bot_object.job_fields(flask.session['session_id'],
                                    db_utils.get_user_id(flask.session['username'], app.config['DB_NAME'],
                                                         cache=flask.session)))
        query = """
        UPDATE sessions s JOIN users u ON u.user_id = s.operator_id
        SET s.status = 'ready', s.signature = %s
        WHERE s.session_id = %s AND u.username = %s
        """
        db_utils.adjust_db(query, app.config['DB_NAME'],
                           params=(signature, flask.session['session_id'], flask.session['username']))

        return flask.render_template('submit.html',
                                     user_name=flask.session['username'])


# The message for the operator of a session (shown on the upload result pages)
MESSAGE_QUERY = """
SELECT m.* FROM messages m JOIN users u ON u.user_id = m.user_id
WHERE m.session_id = %s AND u.username = %s"""


@app.route('/statussubmit')
def statussubmit():
    check_login_data('statussubmit')
    # Idea: provide the user with an overview of all error messages that were generated
    # For now: a checklist of things to check also do the job
    # Also add the "thank you, dear donateur"-message to this screen
    # Work still in progress
    query = """
    SELECT s.status FROM sessions s JOIN users u ON u.user_id = s.operator_id
    WHERE s.session_id = %s AND u.username = %s
    """
    message_data = db_utils.query_db(query, app.config['DB_NAME'],
                                     params=(flask.session['session_id'], flask.session['username']))
    if message_data is None:  # Not the user's own session
        flask.abort(403)
    match message_data[0]:
        case 'uploaded':
            return flask.redirect(flask.url_for('uploaddone'))
        case 'althere':  # The article already has an image: own page, the operator decides what to do with it
            return flask.redirect(flask.url_for('uploadexists'))
        case 'ufail':  # What went wrong was logged by the background job
            return flask.render_template('error.html',
                                         message='De afbeelding kon niet (volledig) verwerkt worden. Controleer het '
                                                 'bestand op Commons en het artikel op Wikipedia.',
                                         errors=session_errors(),
                                         user_name=flask.session['username']), 500
        case 'maxlag':
            message_from_db = db_utils.query_db(MESSAGE_QUERY, app.config['DB_NAME'],
                                                params=(flask.session['session_id'], flask.session['username']))
            return flask.render_template('uploadmaxlag.html',
                                         message=message_from_db[2] if message_from_db else '',
                                         errors=session_errors(),
                                         user_name=flask.session['username'])
    # To do: change this, but for alpha testing, just keep as is...
    return 'Daniuu moet gewaarschuwd worden: er is mogelijk iets misgegaan met deze upload.'


def wiki_url(site, title, prefix=''):
    """Link to a page on a wiki (site: e.g. 'nl.wikipedia.org'). quote() makes sure a title cannot break the link"""
    return f'https://{site}/wiki/' + urllib.parse.quote(prefix + title.replace(' ', '_'), safe='/:')


def thumbnail_url(file, width=320):
    """
    Scaled-down version of a file (Special:FilePath redirects to upload.wikimedia.org). Asked to the Dutch Wikipedia,
    so that a local file in an infobox works as well as a file on Commons
    """
    return wiki_url('nl.wikipedia.org', file, 'Special:FilePath/') + f'?width={width:d}'


def file_in_infobox(details):
    """
    The file in the infobox of the article, from the details of error 202 ('The infobox on "X" has: |afbeelding = Y').
    None if there is no plain file name (e.g. a template or a gallery in the parameter)
    """
    match = re.search(r'afbeelding\s*=\s*(.+)', details or '', flags=re.IGNORECASE)
    if match is None:
        return None
    name = match.group(1).strip().strip('[]').split('|')[0].strip()
    name = re.sub(r'^(file|bestand|image|afbeelding)\s*:\s*', '', name, flags=re.IGNORECASE)
    if not re.search(r'\.(jpe?g|png|gif|svg|tiff?|webp)$', name, flags=re.IGNORECASE) or re.search(r'[{}<>]', name):
        return None
    return name


# Codes of ImageAlreadyError (Wikiportret_core.ERROR_MESSAGES): the image itself is in the article / another image is
IMAGE_ALREADY_CODES = (201, 202)


@app.route('/uploadexists')
def uploadexists():
    """
    The article already had an image (status 'althere'): only the edit of the article was skipped, the job went on
    with all other steps (Commons, Wikidata, category), see Image.operator_steps. The operator gets an overview.
    """
    check_login_data('uploadexists')
    query = """
    SELECT s.page, s.file, c.qid FROM sessions s
    JOIN users u ON u.user_id = s.operator_id
    LEFT JOIN claims c ON c.session_id = s.session_id
    WHERE s.session_id = %s AND u.username = %s AND s.status = 'althere'
    """
    row = db_utils.query_db(query, app.config['DB_NAME'],
                            params=(flask.session['session_id'], flask.session['username']))
    if row is None:  # Not the user's own session, or not stopped because of an image that was already there
        flask.abort(403)
    page, file, qid = row

    errors = session_errors()
    reason = next((error for error in errors if error['code'] in IMAGE_ALREADY_CODES), None)
    existing = file_in_infobox(reason['details']) if reason and reason['code'] == 202 else None
    return flask.render_template(
        'uploadexists.html',
        same_image=reason is None or reason['code'] == 201,  # Without a logged reason: the image itself was found
        page=page, file=file, qid=qid, existing=existing,
        article_url=wiki_url('nl.wikipedia.org', page),
        edit_url=wiki_url('nl.wikipedia.org', page) + '?action=edit',
        history_url=wiki_url('nl.wikipedia.org', page) + '?action=history',
        file_url=wiki_url('commons.wikimedia.org', file, 'File:'),
        file_thumbnail=thumbnail_url(file),
        existing_url=wiki_url('nl.wikipedia.org', existing, 'Bestand:') if existing else None,
        existing_thumbnail=thumbnail_url(existing) if existing else None,
        wikidata_url=wiki_url('www.wikidata.org', qid) if qid else None,
        structured_data_failed=any(error['code'] == 301 for error in errors),
        errors=[error for error in errors if error['code'] not in IMAGE_ALREADY_CODES],  # The reason is the page itself
        user_name=flask.session['username'])


@app.route('/uploaddone')
def uploaddone():
    check_login_data('uploaddone')
    message_from_db = db_utils.query_db(MESSAGE_QUERY, app.config['DB_NAME'],
                                        params=(flask.session['session_id'], flask.session['username']))
    if message_from_db is None:  # No message of this user for this session
        flask.abort(403)
    return flask.render_template('uploaddone.html', message=message_from_db[2],
                                 errors=session_errors())  # Warnings: things that could not be done


@app.route('/uploads')
def uploads():
    """Overview of the images that the logged-in user uploaded in the past, newest first."""
    check_login_data('uploads')
    user_id = db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME'], cache=flask.session)
    if user_id is None:
        return flask.redirect(flask.url_for('login'))

    # Only the user's own rows: the id comes from the (signed) session, never from the request
    rows = db_utils.query_db("SELECT file_uploaded, upload_time FROM user_uploads "
                             "WHERE operator_id = %s ORDER BY upload_time DESC, upload_id DESC",
                             app.config['DB_NAME'], need_all=True, params=(user_id,)) or ()

    entries = []
    for file, uploaded in rows:
        # Titles use underscores in urls; quote() makes sure that special characters cannot break out of the link
        entries.append({
            'file': file,
            'commons_url': 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(file.replace(' ', '_'),
                                                                                           safe='/'),
            'uploaded': uploaded.strftime('%d-%m-%Y %H:%M') if hasattr(uploaded, 'strftime') else str(uploaded)})

    # General statistics for the top of the page (rows are sorted newest first, so the last one is the oldest)
    now = dt.datetime.now()
    times = [uploaded for _, uploaded in rows if hasattr(uploaded, 'year')]  # Skips anything that is no timestamp
    stats = {'total': len(rows),
             'this_year': sum(1 for t in times if t.year == now.year),
             'this_month': sum(1 for t in times if (t.year, t.month) == (now.year, now.month)),
             'first': times[-1].strftime('%d-%m-%Y') if times else None}
    return flask.render_template('uploads.html', uploads=entries, stats=stats,
                                 user_name=flask.session.get('username'))


@app.route('/uploadfailed')
def uploadfailed():
    check_login_data('uploadfailed')
    pass

@app.route('/403')
def forbidden_test():
    check_login_data('forbidden_test')
    return flask.render_template('403.html')

@app.errorhandler(wcl.WikiError)  # Raised for sessions with status 'failed': loading the data in the background failed
def load_failed(e):
    # Raised from every route that loads a session (review, submit), so it is handled in one place
    # The background job logged why (e.g. a typo in the name of the file)
    return flask.render_template('loadfailed.html', errors=session_errors(),
                                 user_name=flask.session.get('username')), 500


@app.errorhandler(wcl.TimeError)  # Status 'processing': the data is not there (yet)
@app.errorhandler(wcl.BackgroundError)  # Status still 'pending': the background job never picked the session up
def load_not_started(e):
    return flask.render_template('loadfailed.html', pending=True,
                                 user_name=flask.session.get('username')), 500


@app.errorhandler(wcl.SessionAccessError)  # Someone else's session: same page as a regular 403
@app.errorhandler(403)
def forbidden(e):
    # No login check here: unauthorised users (no token_expiry yet) must see this page, not loop back to login
    return flask.render_template('403.html'), 403

if __name__ == '__main__':
    # NEVER RUN THE SERVICE ON TOOLFORGE WITH DEBUGGING SWITCHED ON
    app.run(debug=False)
