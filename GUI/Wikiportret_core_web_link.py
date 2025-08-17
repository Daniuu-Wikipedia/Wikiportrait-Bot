"""
A module to couple Wikiportret Core to some very handy Flask utilities
"""

from Wikiportret_core import Image
from flask import session
import datetime as dt


class WebImage(Image):
    def __init__(self, file, name):
        super().__init__(file, name)
        # self.load_properties_from_session()

    # Part 1 of the extension: additional properties for interaction with the session
    @property
    def claims_dict(self):  # Goal of property is to secure the required information
        out = {}  # Empty dict
        if self.claims is None:
            self.ini_wikidata()
        out['P373'] = self.claims.get('P373')  # Regular string
        for i in (569, 570):  # Dates, so be careful
            temp = self.claims.get(f'P{i:d}')
            if temp is not None:
                temp = temp.isoformat(timespec='auto')
            out[f'P{i:d}'] = temp
            del temp
        # P18 is a special case, requires a list as default
        out['P18'] = self.claims.get('P18', [])
        return out

    @claims_dict.setter
    def claims_dict(self, value):
        if isinstance(value, dict):
            self.claims = value  # To be used when loading to Commons
            for i in (569, 570):
                if isinstance(self.claims[i], str):
                    self.claims[i] = dt.datetime.fromisoformat(self.claims[i])


    @property
    def commmons_claims(self):
        out = {}  # Empty dict
        if self.mc is None:
            self.get_commons_claims()
        for i in (180, 275, 6216, 6305):
            out[f'P{i:d}'] = self.claims.get(f'P{i:d}')
        return out

    @commmons_claims.setter
    def commmons_claims(self, value):
        if isinstance(value, dict):
            self.mc = value

    @property
    def sessiondic(self):
        out = {'qid': self.qid,
               'mid': self.mid,
               'name': self.name,
               'file': self.file}

    # Part 2: overloads for some methods: will directly write stuff to the session once parsed
    # Note: these methods will use the properties from part 1 of the file
    def set_session_variables(self):
        """
        Method stores some variables in the user's session.
        These variables are used for communication within one specific upload thread
        """
        session['name'] = self.name
        session['file'] = self.file
        session['qid'] = self.claims_dict
        session['mid'] = self.commmons_claims

    def read_session_variables(self):
        """
        Method re-reads the session variables.
        Please note: file name & person's name are automatically set from the form
        """
        self.claims_dict = session.get('claims_dict')
        self.commmons_claims = session.get('commmons_claims')

    def clear_session_variables(self):
        session.pop('name', None)
        session.pop('qid', None)
        session.pop('mid', None)
        session.pop('file', None)
