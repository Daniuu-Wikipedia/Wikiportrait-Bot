# Required inputs from the flask module
# Flask: the core app, incorporating all functionality to set up a proper web page
# render_template: the functionality to deal with .html-templates
# request: to be able to handle requests using the Flask library
from flask import Flask, render_template, request

# Import Toolforge to update the user agent of the app
import toolforge
toolforge.set_user_agent('Wikiportret', email='wikiportret@wikimedia.org')  # Just setting up a custom user agent

# Import all utilities for working with a database
# Not required in this project
# from flask_sqlalchemy import SQLAlchemy

# Import some auxiliary classes
from objects import SiteSettings

data = SiteSettings()

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
    return render_template('index.html', data=data)

# Define the routing towards the review section
@app.route('/review', methods=['POST', 'GET'])
def review():
    global data
    return 'Hello World!'


if __name__ == '__main__':
    app.run(debug=True)
