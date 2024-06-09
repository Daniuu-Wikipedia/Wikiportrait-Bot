# Required inputs from the flask module
# Flask: the core app, incorporating all functionality to set up a proper web page
# render_template: the functionality to deal with .html-templates
# request: to be able to handle requests using the Flask library
import threading

from flask import Flask, render_template, request, Response
from time import sleep

# Import Toolforge to update the user agent of the app
import toolforge

toolforge.set_user_agent('Wikiportret-updater',
                         email='wikiportret@wikimedia.org')  # Just setting up a custom user agent

# Import all utilities for working with a database
# Not required in this project
# from flask_sqlalchemy import SQLAlchemy

# Import some auxiliary classes
from objects import SiteSettings
from Wikiportret_core import Image

data = SiteSettings()
bot_object = None

# Define the application (this will be the object representing the web page we're interested in)
app = Flask(__name__)


# Setup up the starting screen
@app.route('/')
def index():
    global data
    # Landing page
    # The template is stored internally in the templates-folder, there is no need to mention this in the argument
    # Perform these actions if a POST request is sent (submitted via the form)
    if request.method == 'POST':
        pass  # Perform actions to initialize the form
    return render_template('index.html',
                           data=data,
                           user_name='Test')


# Create a page to be displayed while the bot is getting the initial data
@app.route('/load', methods=['POST', 'GET'])
def load():
    # This page is designed to facilitate loading relevant data in the background
    # This page must be called by the index page
    global data
    global bot_object  # Not ideal, but it does work
    if request.method == 'GET':
        return 'This page cannot be loaded directly!'
    elif request.method != 'POST':
        return 'You can only POST to this page!'
    else:
        # Handle the POST request
        article_nl = request.form['Article'].strip()
        image = request.form['File'].strip()
        data.image_name = image
        data.nlart = article_nl  # Centralize the settings to the global DATA object
        # In the background, we will start setting up the bot
        bot_object = Image(data.image_name, data.nlart)  # Set the bot up
        bot_object.prepare_image_data()  # Load stuff in the background

        # Now we can start the auxiliary function
        def respond_while_preparing():
            yield "I am loading your data!"
            sleep(1)
            t1 = threading.Thread(target=bot_object.get_commons_claims)
            t2 = threading.Thread(target=bot_object.get_commons_text)
            t3 = threading.Thread(target=bot_object.ini_wikidata)

            t1.start()
            t2.start()
            t3.start()
            t1.join()
            t2.join()
            t3.join()
            # Include JavaScript for redirection
            # JavaScript provided by ChatGPT
            del t1, t2, t3
            print(bot_object.claims)
            # return None  # Just added to debug
            yield """
            <script>
                setTimeout(function() {
                    window.location.href = '/review';  // Redirect to the final page
                }, 1000);  // Adjust the delay (in milliseconds) before redirection
            </script>"""

        return Response(respond_while_preparing(), content_type='text/html')


# Define the routing towards the review section
@app.route('/review', methods=['POST', 'GET'])
def review():
    global data, bot_object
    # We rendered some data - now load the template just before reviewing
    # To add: this template can only be loaded if the verification procedure has been performed!
    return render_template('review.html',
                           data=data,
                           bot=bot_object,
                           license_options=Image.licenses.keys(),
                           selected_license='CC-BY-SA 4.0',
                           user_name='Test user')


# The page the users will see whenever they submit an image for posting
@app.route('/submit', methods=['POST', 'GET'])
def submit():
    global data
    if request.method == 'POST':
        print('check12' in request.form)

        return render_template('review.html',
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
