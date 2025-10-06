"""
A module to couple Wikiportret Core to some very handy Flask utilities
"""

from Wikiportret_core import Image
import json
import mwoauth


class WebImage(Image):
    def __init__(self, file, name):
        super().__init__(file, name)

    # Part 1 of the extension: additional properties for interaction with the session
    @property
    def claims_dict(self):  # Goal of property is to secure the required information
        return self.claims

    @claims_dict.setter
    def claims_dict(self, value):
        if isinstance(value, dict):
            self.claims = value

    @property
    def wikidata_claims_json(self):
        """
        Property that generates the json string for use in the _claims_ table
        """
        return json.dumps(self.claims)

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


def create_from_db(session_number):
    """
    Reads a session number & will then parse all relevant output form the db.
    Method takes two arguments:
        * session number: integer representing a session in the database
    """
    pass
