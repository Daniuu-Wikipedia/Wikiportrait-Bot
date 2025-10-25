# Required inputs from the flask module
# Flask: the core app, incorporating all functionality to set up a proper web page
# render_template: the functionality to deal with .html-templates
# request: to be able to handle requests using the Flask library
import mwoauth
import json  # Makes life slightly easier

import flask
# Import Toolforge to update the user agent of the app
import toolforge

# Some datetime stuff
import datetime as dt

# Import some auxiliary classes
import os
import tomllib
from objects import SiteSettings

# from Wikiportret_core import Image
import Wikiportret_core_web_link as wcl
import Wikiportret_API_utils as wpor_api
import Wikiportret_db_utils as db_utils

toolforge.set_user_agent('Wikiportret-updater',
                         email='wikiportret@wikimedia.org')  # Just setting up a custom user agent

data = SiteSettings()

# Define the application (this will be the object representing the web page we're interested in)
app = flask.Flask(__name__)

# Load configuration from TOML file
__dir__ = os.path.dirname(__file__)
with open(os.path.join(__dir__, 'config.toml'), 'rb') as f:
    app.config.update(tomllib.load(f))

# Load configuration from TOML file
__dir__ = os.path.dirname(__file__)
with open(os.path.join(__dir__, 'config.toml'), 'rb') as f:
    app.config.update(tomllib.load(f))


@app.route('/')
def index():
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
        flask.flash(u'OAuth callback failed. Are cookies disabled?')
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
            return flask.redirect(flask.url_for('index'))  # Error, do not continue
        # Store the access_token
        token_to_store = json.dumps(dict(zip(access_token._fields, access_token)))
        # Obtain a valid token from the Wikiportret API
        wikiportret_key = wpor_api.generate_wikiportret_key()

        # Write data to the db (tokens table)
        # On duplicate key overwrites tokens if needed
        query = f"""
        INSERT INTO tokens (operator_id, oauth_token, wikiportrait_token)
        VALUES ({user_id}, '{token_to_store}', '{wikiportret_key}')
        ON DUPLICATE KEY UPDATE
            oauth_token = '{token_to_store}',
            wikiportrait_token = '{wikiportret_key}',
            `timestamp` = NOW();
        """
        # And now, time to push this to the db
        db_utils.adjust_db(query, app.config['DB_NAME'])

        # Store the username in the session (just making my life slightly easier)
        # For security reasons, the underlying keys are never shown to the user
        # Even though flask.session has some security built in to prevent tampering with the session cookie
        flask.session['username'] = identity['username']

    return flask.redirect(flask.url_for('input'))  # After logging in, direct user to login screen


@app.route('/logout', methods=['GET'])
def logout():
    """Log the user out by clearing their session."""
    # To do: remove associated entries from the db (clean up stuff)
    # To do: remove tokens from the db
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


# Setup up the starting screen
@app.route('/input')
def input():
    # Landing page
    # The template is stored internally in the templates-folder, there is no need to mention this in the argument
    # Perform these actions if a POST request is sent (submitted via the form)
    if flask.request.method == 'POST':
        raise NotImplementedError('API-based loading is not yet supported!')  # Perform actions to initialize the form
    elif db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME']) is None:
        return flask.redirect(flask.url_for('login'))  # Back to the index - invalid username passed
    return flask.render_template('input.html',
                                 user_name=flask.session['username'])


# Create a page to be displayed while the bot is getting the initial data
@app.route('/load', methods=['POST', 'GET'])
def load():
    # This page is designed to facilitate loading relevant data in the background
    # This page must be called by the index page
    if flask.request.method == 'GET':
        return 'This page cannot be loaded directly!'
    elif flask.request.method != 'POST':
        return 'You can only POST to this page!'
    elif db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME']) is None:
        return flask.redirect(flask.url_for('login'))  # Back to the index - invalid username passed
    else:
        # Handle the POST request
        # In the background, we will start setting up the bot
        bot_object = wcl.WebImage(flask.request.form['File'].strip(),
                                  flask.request.form['Article'].strip(),
                                  app.config,
                                  flask.session['username'])  # Configure a new bot object
        # bot_object.verify_OAuth(app.config, user=flask.session['username'])

        # Previous versions of code set stuff to the session (now no longer needed: done via db)
        # Set stuff to the database - this goes into the sessions table
        query = f"""
        insert into `sessions` (`operator_id`, `page`, `file`) 
        values ('{db_utils.get_user_id(flask.session['username'], app.config['DB_NAME'])}',
         '{bot_object.name}', '{bot_object.file}');
        """
        flask.session['session_id'] = db_utils.adjust_db(query,
                                                         app.config['DB_NAME'],
                                                         retrieve_id=True)

        # Background load is truly done in the background, by the continuous bg job

        # Redirect naar de loading pagina
        return flask.render_template('loading.html',
                                     user_name=flask.session['username'])


# Define the routing towards the review section
@app.route('/review', methods=['POST', 'GET'])
def review():
    # We rendered some data - now load the template just before reviewing
    # To add: this template can only be loaded if the verification procedure has been performed!
    try:
        if db_utils.get_user_id(flask.session.get('username'), app.config['DB_NAME']) is None:
            return flask.redirect(flask.url_for('login'))  # Back to the index - invalid username passed
        bot_object = wcl.create_from_db(flask.session['session_id'],
                                        app.config,
                                        flask.session['username'])  # To do: continue
        # bot_object.verify_OAuth(app.config, user=flask.session['username'])
        return flask.render_template('review.html',
                                     license_options=wcl.WebImage.licenses.keys(),
                                     selected_license='CC-BY-SA 4.0',
                                     bot=bot_object,
                                     user_name=flask.session['username'])
    except wcl.WikiError:
        raise NotImplementedError  # Still need to work on this - will go to sep page
    except wcl.BackgroundError:
        raise NotImplementedError
    except wcl.TimeError:
        raise NotImplementedError


# The page the users will see whenever they submit an image for posting
@app.route('/submit', methods=['POST', 'GET'])
def submit():
    # To do: clear the global object (all required stuff is dumped in the session anyway)
    if flask.request.method == 'POST':
        update_dict = {}  # Key-value pairs for updating stuff in the db
        bot_object = wcl.create_from_db(flask.session['session_id'],
                                        app.config,
                                        flask.session['username'])  # To do: make adjustments needed
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
        connection = toolforge.toolsdb(app.config['DB_NAME'])
        if update_dict:
            for i, j in update_dict.items():
                query = """
                UPDATE input_data
                SET %s = %r
                WHERE session_id = %d
                """ % (i, j, flask.session['session_id'])
                db_utils.adjust_db(query,
                                   app.config['DB_NAME'],
                                   connection=connection)

        # Uploading the stuff to the wiki will be done in the background
        # Prepare everything for the background job
        query = """
        UPDATE sessions
        SET status = 'ready'
        WHERE session_id = %d
        """ % flask.session['session_id']
        db_utils.adjust_db(query, app.config['DB_NAME'], connection=connection)
        connection.close()

        return flask.render_template('review.html',
                                     bot=bot_object,
                                     license_options=wcl.WebImage.licenses.keys(),
                                     selected_license='CC-BY-SA 4.0',
                                     user_name=flask.session['username'])


if __name__ == '__main__':
    # NEVER RUN THE SERVICE ON TOOLFORGE WITH DEBUGGING SWITCHED ON
    app.run(debug=False)
