"""
Python code supporting the web page.

This file contains the object class "WebImage", which stores all information on a given file
"""

# Functionality to process a submitted image can be drawn directly from the Wikiportret code


# Functionality to control how certain content is being displayed
class SiteSettings:
    goodcol = '#ffffff'
    startcol = '#ceffaa'  # Color to be displayed if the input value meets some conditions
    badcol = '#ffffff'
    subcol = '#ffffff'
    black = '#000000'
    blue = '#0000ff'
    red = "#ff0000"
    green = "#00ff00"
    white = "#ffffff"
    inputcol = 'rgb(185, 233, 255)'  # #b9e9ff

    def __init__(self):
        # Constructor defines all variables that could be called by the site
        # Variables controlling the "STATUS" field
        self._statusmessage = "Geen fouten - houden zo"  # Message to be displayed on the status tab
        self._statuscolor = SiteSettings.subcol   # Color of the status field
        self._statusfront = SiteSettings.black  # Color of the text in the status field

        # Variables controlling the state of the "SUBMIT" button
        self._loadmessage = 'LADEN'
        self._loadcolor = SiteSettings.blue
        self._loadfront = SiteSettings.black

        # Variables controlling the state of the two main input fields
        # Part 1: field inputting the name of the image
        self.imageval = True  # Check whether we got some valid input here
        # Front color is always black
        # Background color will be set through a property

        # Part 2: field for inputting the name of the article on nlwiki

    @property
    def image_input_bg(self):
        print(self.imageval)
        if self.imageval is True:
            return SiteSettings.inputcol
        return SiteSettings.red  # Indicative of an invalid input

    @image_input_bg.setter
    def image_input_bg(self, new):
        if isinstance(new, bool):
            self.imageval = new


