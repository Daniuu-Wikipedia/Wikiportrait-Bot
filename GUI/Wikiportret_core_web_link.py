"""
A module to couple Wikiportret Core to some very handy Flask utilities
"""

from Wikiportret_core import Image
import Wikiportret_db_utils as dbut
import json
from requests_oauthlib import OAuth1

class WebImage(Image):
    def __init__(self, file, name, config, user):
        super().__init__(file, name)
        self.dbname = config['DB_NAME']
        self.verify_OAuth(config, user=user)  # Automatically verify OAuth

    def verify_OAuth(self, config, secret=None, user=None):  # Overloading from parent class
        # Note: self._auth is defined in the parent class
        if self._auth is not None:
            return None
        if secret is None:
            if isinstance(user, (int, str)):
                secret = dbut.get_tokens_from_db(self.dbname, user)
            else:
                raise TypeError('Only integers and strings are accepted as input for the user!')

        # Call OAuth verification subroutines for separate bots
        self._commons.verify_OAuth_web(config, secret)
        self._wikidata.verify_OAuth_web(config, secret)
        self._nl.verify_OAuth_web(config, secret)
        self._meta.verify_OAuth_web(config, secret)

    def write_to_db(self, session_number):
        if self.claims is None:
            self.ini_wikidata()
        if self.comtext is None:
            self.get_commons_text()
        if self.mc is None:
            self.get_commons_claims()
        query = f"""
        insert into `claims` (`session_number`, `json_response`, `commons_claims`, `qid`, `mid`, `comm_text`) 
        values ({session_number},
         '{json.dumps(self.claims)}',
          '{json.dumps(self.mc)}',
           '{self.qid}',
            '{self.mid}',
             '{self.comtext}');
        """
        dbut.adjust_db(query, self.dbname)

    def input_data_to_db(self, session_number):
        query = f"""
        insert into input_data (`session_id`, `custom_caption`, `date`, `ticket`, `category_name`, `edit_summary`)
        values ({session_number}, '{self.caption}', {self.date}, {self.mc.get('P6305')}, '{self.catname}', '{self.sum}')
        """
        dbut.adjust_db(query, self.dbname)

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


def create_from_db(session_number, dbname, operator):
    """
    Reads a session number & will then parse all relevant output form the db.
    Method takes two arguments:
        * session number: integer representing a session in the database
    """
    pass
