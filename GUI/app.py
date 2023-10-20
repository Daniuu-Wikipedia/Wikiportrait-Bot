# Required inputs from the flask module
# Flask: the core app, incorporating all functionality to set up a proper web page
# render_template: the functionality to deal with .html-templates
from flask import Flask, render_template, url_for

# Import Toolforge to update the user agent of the app
import toolforge

# Import all utilities for working with a database
# Not required in this project
# from flask_sqlalchemy import SQLAlchemy

# Define the application (this will be the object representing the web page we're interested in)
app = Flask(__name__)

# Setup up the starting screen
@app.route('/')
def index():
    # Landing page
    # The template is stored internally in the templates-folder, there is no need to mention this in the argument
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
