"""
Python code supporting the web page.

This file contains the object class "WebImage", which stores all information on a given file
"""

test = None

class WebImage:
    def __init__(self, image, article):
        self.image, self.article = image, article

        # Perform type checks
        if not isinstance(self.image, str):
            raise TypeError('The name of the image to be processed must be passed as a string!')
        if not isinstance(self.article, str):
            raise TypeError('The name of the target article must be a string!')

    def __repr__(self):
        return self.image

    def __str__(self):
        return self.image
