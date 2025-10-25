"""
A module to couple Wikiportret Core to some very handy Flask utilities
"""
import toolforge

from Wikiportret_core import Image
import Wikiportret_db_utils as dbut
import datetime as dt
import json


class WebImage(Image):
    def __init__(self, file, name, config, user):
        super().__init__(file, name)
        self.dbname = config['DB_NAME']
        self.verify_OAuth(config, user=user)  # Automatically verify OAuth

    def verify_OAuth(self, config, secret=None, user=None):  # Overloading from parent class
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
        del secret  # Destroy these immediately for obvious reasons

    def write_to_db(self, session_number, connection=None):
        if self.claims is None:
            self.ini_wikidata()
        if self.comtext is None:
            self.get_commons_text()
        if self.mc is None:
            self.get_commons_claims()
        query = f"""
        insert into `claims` (`session_id`, `json_response`, `commons_claims`, `qid`, `mid`, `comm_text`) 
        values  ({session_number},
         '{json.dumps(self.claims)}',
          '{json.dumps(self.mc)}',
           '{self.qid}',
            '{self.mid}',
             '{self.comtext}');
        """
        dbut.adjust_db(query, self.dbname, connection=connection)

    def input_data_to_db(self, session_number, connection=None):
        query = f"""
        insert into input_data (`session_id`, `custom_caption`, `category_name`, `edit_summary`, `ticket`)
        values ({session_number}, '{self.caption}', '{self.catname}', '{self.sum}', {self.ticket_number});
        """
        dbut.adjust_db(query, self.dbname, connection=connection)

        if self.date is not None:
            query = """
            UPDATE input_data
            SET date = %r
            WHERE session_id = %d;
            """ % (self.date.isoformat(), session_number)
            dbut.adjust_db(query, self.dbname, connection=connection)

        # And now time to add the birth & death date of the subject
        if self.birth is not None:
            query = """
                    UPDATE input_data
                    SET birth_date = %r
                    WHERE session_id = %d;
                    """ % (self.birth.isoformat(), session_number)
            dbut.adjust_db(query, self.dbname, connection=connection)

        if self.death is not None:
            query = """
                    UPDATE death_date
                    SET death_date = %r
                    WHERE session_id = %d;
                    """ % (self.death.isoformat(), session_number)
            dbut.adjust_db(query, self.dbname, connection=connection)

        # And now time to add the birth & death date of the subject
        if self.birth is not None:
            query = """
                    UPDATE input_data
                    SET birth_date = %r
                    WHERE session_id = %d;
                    """ % (self.birth, session_number)
            dbut.adjust_db(query, self.dbname, connection=connection)

        if self.death is not None:
            query = """
                    UPDATE death_date
                    SET birth_date = %r
                    WHERE session_id = %d;
                    """ % (self.death, session_number)
            dbut.adjust_db(query, self.dbname, connection=connection)

    # Part 1 of the extension: additional properties for interaction with the session
    @property
    def claims_dict(self):  # Goal of property is to secure the required information
        return self.claims

    @claims_dict.setter
    def claims_dict(self, value):
        if isinstance(value, dict):
            self.claims = value
            # Also update the chap's date of birth & date of death
            # These are not automatically read when an object is reset from the db
            self.date_born()
            self.date_deceased()

    @property
    def wikidata_claims_json(self):
        """
        Property that generates the json string for use in the _claims_ table
        """
        return json.dumps(self.claims)

    @wikidata_claims_json.setter
    def wikidata_claims_json(self, value):
        if isinstance(value, dict):
            self.claims_dict = value
        elif isinstance(value, str):
            self.claims_dict = json.loads(value)  # Directly load claims from JSON

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

    @commons_claims_json.setter
    def commons_claims_json(self, value):
        if isinstance(value, dict):
            self.mc = value
        elif isinstance(value, str):
            self.mc = json.loads(value)

    @property
    def ticket_number(self):
        parent = self.mc.get('P6305', None)
        if parent is not None:
            parent = parent[0]
            return int(parent['mainsnak']['datavalue']['value'])


# Define custom exception for dealing with incorrect data
class WikiError(Exception):
    def __str__(self):
        return 'Something went wrong while loading the data from the wiki'


class BackgroundError(Exception):
    def __str__(self):
        return 'The bg job is down!'


class TimeError(Exception):
    def __str__(self):
        return 'Still processing in the background'


def create_from_db(session_number,
                   config,
                   username=None,  # Username can also be passed, but not worry about it for now
                   retrieve_claims=True,
                   adjust_input_data=True,
                   check_status=True):
    """
    Reads a session number & will then parse all relevant output form the db.
    Method takes two arguments:
        * session number: integer representing a session in the database
    """
    # To make our life slightly easier...
    dbname = config['DB_NAME']

    # First job: create a connection to the db
    # Since we need to run a few queries, we will just use one steady connection
    connection = toolforge.toolsdb(dbname)

    # Second job: check in the db what file & nlwiki page the user wishes to process
    query = "SELECT * FROM sessions WHERE session_id=%d;" % session_number
    result = dbut.query_db(query, dbname, connection=connection)  # Get relevant row as a tuple
    operator_id = result[1]  # Operator id, needed further down the road
    page, file = result[2], result[3]  # Make life slightly easier & shorten notation
    status = result[4]

    # Error handling section
    if check_status:  # Allow for manually bypassing the status check
        match status:
            case 'failed':
                raise WikiError('That did not work')
            case 'processing':
                raise TimeError('Still processing in the background')
            case 'pending':
                raise BackgroundError('BG JOB IS DOWN!!!')

    # Third job: all input is there to generate the WebImage desperately needed
    output = WebImage(file, page, config, operator_id)

    # Fourth job: obtain the relevant parameters from the db
    if retrieve_claims is True:
        query = "SELECT * FROM claims WHERE session_id=%d;" % session_number
        result = dbut.query_db(query, dbname, connection=connection)
        output.qid, output.mid = result[3], result[4]
        output.wikidata_claims_json = result[1]  # JSON loading is done through the property
        output.commons_claims_json = result[2]
        output.comtext = result[5]

        # Fifth job: if there is already some customized input data, get it
        if adjust_input_data is True:
            query = "SELECT * FROM input_data WHERE session_id=%d;" % session_number
            result = dbut.query_db(query, dbname, connection=connection)
            # Now set the relevant properties
            if result[1] is not None:
                output.caption = result[1]
            if result[2] is not None:
                output.date = dt.date.fromisoformat(result[2])
            if result[4] is not None:
                output.category_name = result[4]
            if result[5] is not None:
                output.edit_summary = result[5]
            if result[7] is not None:
                output.birth = dt.date.fromisoformat(result[7])
            if result[8] is not None:
                output.death = dt.date.fromisoformat(result[8])
            # Result 3 = ticket number, we don't need it for now
            # Result 6 = used only for the db and cleanup scripts
    return output
