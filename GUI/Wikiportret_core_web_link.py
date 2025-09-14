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
        for i in (373, 569, 570):
            out[f'P{i:d}'] = self.claims.get(f'P{i:d}')
        out['P373'] = self.claims.get('P373')  # Regular string
        # P18 is a special case, requires a list as default
        out['P18'] = self.claims.get('P18', [])
        return out

    @claims_dict.setter
    def claims_dict(self, value):
        if isinstance(value, dict):
            self.claims = value  # To be used when loading to Commons

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
        session['customcommons'] = self._customcatname
        session['birth'] = self.bd_for_session
        session['death'] = self.dd_for_session
        session['date'] = self.date_for_session
        session.modified = True

    def read_session_variables(self):
        """
        Method re-reads the session variables.
        Please note: file name & person's name are automatically set from the form
        """
        self.claims_dict = session.get('claims_dict')
        self.commmons_claims = session.get('commmons_claims')
        self.catname = session.get('customcommons')
        print('Session read', session.get('birth'), session.get('death'), session.get('date'))
        # Important dates
        # P569: birth date
        if session.get('birth') is not None:
            self.birth = dt.date.fromisoformat(session['birth'])
        # P570: death date
        if session.get('death') is not None:
            self.death = dt.date.fromisoformat(session['death'])
        # Image generation date
        if session.get('date') is not None:
            self.date = dt.date.fromisoformat(session['date'])
        print('Read', self.birth, self.death, self.date, 'Session date', session.get('date'))

    @staticmethod
    def clear_session_variables():
        session.pop('name', None)
        session.pop('qid', None)
        session.pop('mid', None)
        session.pop('file', None)
        session.pop('customcommons', None)


# Convenient auxiliary method
def read_from_session():
    new = WebImage(session['file'], session['name'])
    new.read_session_variables()
    return new
