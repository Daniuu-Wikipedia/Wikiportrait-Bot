# Required inputs from the flask module
# Flask: the core app, incorporating all functionality to set up a proper web page
# render_template: the functionality to deal with .html-templates
# request: to be able to handle requests using the Flask library
import threading
import mwoauth

import flask
# Import Toolforge to update the user agent of the app
import toolforge

# Datetime library to assist handling of some dates
import datetime as dt

toolforge.set_user_agent('Wikiportret-updater',
                         email='wikiportret@wikimedia.org')  # Just setting up a custom user agent

# Import all utilities for working with a database
# Not required in this project
# from flask_sqlalchemy import SQLAlchemy

# Import some auxiliary classes
import os
import tomllib
from objects import SiteSettings
from Wikiportret_core import Image

data = SiteSettings()
bot_object = None

# Define the application (this will be the object representing the web page we're interested in)
app = flask.Flask(__name__)

# Load configuration from TOML file
__dir__ = os.path.dirname(__file__)
with open(os.path.join(__dir__, 'config.toml'), 'rb') as f:
    app.config.update(tomllib.load(f))

# New code featuring OAuth

# Load configuration from TOML file
__dir__ = os.path.dirname(__file__)
with open(os.path.join(__dir__, 'config.toml'), 'rb') as f:
    app.config.update(tomllib.load(f))


@app.route('/')
def index():
    greeting = app.config['GREETING']
    username = flask.session.get('username', None)
    return flask.render_template(
        'input.html', username=username, greeting=greeting)


@app.route('/login')
def login():
    """Initiate an OAuth login.

    Call the MediaWiki server to get request secrets and then redirect the
    user to the MediaWiki server to sign the request.
    """
    consumer_token = mwoauth.ConsumerToken(
        app.config['CONSUMER_KEY'], app.config['CONSUMER_SECRET'])
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
        flask.session['access_token'] = dict(zip(
            access_token._fields, access_token))
        flask.session['username'] = identity['username']

    return flask.redirect(flask.url_for('input'))


@app.route('/logout')
def logout():
    """Log the user out by clearing their session."""
    flask.session.clear()
    return flask.redirect(flask.url_for('index'))


# Setup up the starting screen
@app.route('/input')
def input():
    global data
    # Landing page
    # The template is stored internally in the templates-folder, there is no need to mention this in the argument
    # Perform these actions if a POST request is sent (submitted via the form)
    if flask.request.method == 'POST':
        pass  # Perform actions to initialize the form
    return flask.render_template('input.html',
                                 data=data,
                                 user_name=flask.session['username'])


# Create a page to be displayed while the bot is getting the initial data
@app.route('/load', methods=['POST', 'GET'])
def load():
    # This page is designed to facilitate loading relevant data in the background
    # This page must be called by the index page
    global data
    global bot_object  # Not ideal, but it does work
    if flask.request.method == 'GET':
        return 'This page cannot be loaded directly!'
    elif flask.request.method != 'POST':
        return 'You can only POST to this page!'
    else:
        # Handle the POST request
        article_nl = flask.request.form['Article'].strip()
        image = flask.request.form['File'].strip()
        data.image_name = image
        data.nlart = article_nl  # Centralize the settings to the global DATA object
        # In the background, we will start setting up the bot
        bot_object = Image(data.image_name, data.nlart)  # Set the bot up

        def background_load():
            bot_object.prepare_image_data()  # Load stuff in the background
            bot_object.get_commons_claims()
            bot_object.get_commons_text()
            bot_object.ini_wikidata()
            print(bot_object.claims)

        # Start the background loading in a separate thread
        thread = threading.Thread(target=background_load)
        thread.start()

        # Redirect naar de loading pagina
        return flask.render_template('loading.html')


# Define the routing towards the review section
@app.route('/review', methods=['POST', 'GET'])
def review():
    global data, bot_object
    # We rendered some data - now load the template just before reviewing
    # To add: this template can only be loaded if the verification procedure has been performed!
    return flask.render_template('review.html',
                                 data=data,
                                 bot=bot_object,
                                 license_options=Image.licenses.keys(),
                                 selected_license='CC-BY-SA 4.0',
                                 user_name='Test user')


# The page the users will see whenever they submit an image for posting
@app.route('/submit', methods=['POST', 'GET'])
def submit():
    global data, bot_object
    if flask.request.method == 'POST':
        # First things first: we need to adjust some values
        # But this only happens if some specific checkboxes are checked
        # If a checkbox is checked, it's name will appear in flask.request.form
        if 'checkdate' in flask.request.form:  # Date of image capture is adjusted
            d, m, y = flask.request.form['datevalue'].strip().split('/')
            d, m, y = int(d.strip()), int(m.strip()), int(y.strip())
            bot_object.date = dt.datetime(y, m, d)
            del d, m, y  # Temporary variables, clear these
        if 'checksummary' in flask.request.form:  # Use custom edit summary
            bot_object.sum = flask.request.form['summaryvalue'].strip()
        if 'checkcat' in flask.request.form:  # Custom category name
            bot_object.catname = flask.request.form['catvalue'].strip()  # Call the correct catname
        if 'checkcaption' in flask.request.form:  # Custom caption
            bot_object.caption = flask.request.form['captionvalue'].strip()
        if 'checklicence' in flask.request.form:  # Custom license, there is still a bug here...
            bot_object.license = flask.request.form['licencevalue'].strip()

        return flask.render_template('review.html',
                                     data=data,
                                     bot=bot_object,
                                     license_options=Image.licenses.keys(),
                                     selected_license='CC-BY-SA 4.0',
                                     user_name='Test user')
    else:
        print('THIS PAGE CAN ONLY BE CALLED VIA A POST REQUEST!')


if __name__ == '__main__':
    # NEVER RUN THE SERVICE ON TOOLFORGE WITH DEBUGGING SWITCHED ON
    app.run(debug=False)
