# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 19:38:55 2021

@author: Daniuu

This is a script that should make it easier to process requests done through Wikiportret.

The bot will do a couple of tasks:
    1) It will create a new category for the name of the person on the image
    2) It will post the image and category created in 1 to a Wikidata-item
    3) It will attempt to place the image in the Infobox on Wikipedia
    4) Generate a standard e-mail (to be implemented)
    
Information can be found in Wikiportret ticket 2021021010009189 (VRT access required)
"""
import threading
import requests
import urllib
import time
import datetime as dt
import re  # Regex to filter the ticket number
from requests_oauthlib import OAuth1


class MaxlagError(Exception):
    "This is a special error, specially made for when Maxlag occurs - it warns the operator of the bot"

    def __str__(self):
        print('\n')
        print(
            'Watch out! a maxlag error was spotted. This means that the Wikimedia API is slow. The bot run will be terminated, please try again in a few minutes!')
        time.sleep(2)
        return "Maxlag error occured, bot run aborted."


class Bot:
    'This class is designed to facilitate all interactions with Wikipedia (and to get the processing functions out of other calsses)'
    max_edit = 12  # The maximum number of edits that a single bot can do per minute

    def __init__(self, api, m=None):
        'Constructs a bot, designed to interact with one Wikipedia'
        self.api = api
        self.ti = []  # A list to store the time stamps of the edits in
        self._token = None  # This is a token that is handy
        self._auth = None  # The OAuth ID (this is the token that will allow the auth - store this for every bot)
        self._max = Bot.max_edit if m is None else m  # this value is set, and can be changed if a bot bit would be granted

    def __str__(self):
        return self.api.copy()

    def verify_OAuth(self, file="Tokens_Wikiportraitbot.txt"):
        'This function will verify whether the OAuth-auth has been configured. If not, it will do the configuration.'
        if self._auth is None:
            with open(file, 'r') as secret:
                self._auth = OAuth1(
                    *[i.strip() for i in secret][1::2])  # This is the reason why those keys should never be published

    def verify_token(self):
        if self._token is None:
            self.get_token()
        elif float(time.time()) - self._token[1] > 8:
            self.get_token()  # Tokens expire after approximately 8 seconds, so generate a new one
        return self._token[0]

    def get(self, payload):
        "This function will provide functionality that does all the get requests"
        self.verify_OAuth()
        payload['format'] = 'json'  # Set the output format to json
        return requests.get(self.api, params=payload, auth=self._auth).json()

    def get_token(self, t='csrf', n=0, store=True):
        'This function will get a token'
        assert isinstance(t, str), 'Please provide a string as a token!'
        pay = {'action': 'query',
               'meta': 'tokens',
               'type': t}
        z = self.get(pay), float(time.time())
        try:
            if store is True:
                self._token = z[0]['query']['tokens'][f'{t}token'], z[1]
                return self._token[0]
            else:
                return self._token[0]  # Just return the token
        except KeyError:
            assert n <= 1, 'Cannot generate the requested token'
            return self.get_token(t, n + 1)

    def post(self, params):
        raise NotImplementedError('This version should NEVER post!')
        assert 'action' in params, 'Please provide an action'
        t = float(time.time())
        self.ti = [i for i in self.ti if i >= t - 60]  # Clean this mess
        if len(self.ti) >= Bot.max_edit:  # Check this again, after doing the cleaning
            print('Going to sleep for a while')
            time.sleep(20)  # Fuck, we need to stop
            return self.post(params)  # run the function again - but: with a delay of some 60 seconds
        if 'token' not in params:  # Place this generation of the key here, to avoid having to request too many tokens
            params['token'] = self.verify_token()  # Generate a new token
        params['format'] = 'json'
        params['maxlag'] = 5  # Using the standard that's implemented in PyWikiBot
        self.ti.append(float(time.time()))
        k = requests.post(self.api, data=params, auth=self._auth).json()
        if 'error' in k:
            print('An error occured somewhere')  # We found an error
            if 'code' in k['error'] and 'maxlag' in k['error']['code']:
                print('Maxlag occured, please try to file the request at a later point in space and time.')
                raise MaxlagError
                time.sleep(10)
        return k


class WikidataBot(Bot):
    def __init__(self):
        super().__init__('https://www.wikidata.org/w/api.php')


class CommonsBot(Bot):
    def __init__(self):
        super().__init__('https://commons.wikimedia.org/w/api.php')


class MetaBot(Bot):
    def __init__(self):
        super().__init__('https://meta.wikimedia.org/w/api.php')

    def short(self, params):
        "This function can be used to create a short url (without generating a token first)"
        params['format'] = 'json'
        return requests.post(self.api, data=params, auth=self._auth).json()


class NlBot(Bot):
    def __init__(self):
        super().__init__('https://nl.wikipedia.org/w/api.php')


class Image:
    'This class will contain the main methods that are required for the post-processing of an image from Wikiportrait'
    # Program some endpoints as static variables (they will be common for all objects)
    commons = "https://commons.wikimedia.org/w/api.php"
    wikidata = "https://www.wikidata.org/w/api.php"
    nlwiki = "https://nl.wikipedia.org/w/api.php"

    licenses = {'CC-BY-SA 4.0': 18199165,
                'CC-BY-SA-3.0': 14946043,
                'CC-BY-SA-2.0': 19068220,
                'CC-BY-4.0': 20007257}  # This dictionary links the relevant images to their structured data on Wikidata

    def __init__(self, file, name):
        """
        This function will do some construction works
        ----------
        file : string
            This string should contain the name of the image that was processed.
        name : string
            This parameter contains the name of the corresponding person on nl-wiki.
        """
        self.file, self.name = file.replace('File:', '').strip(), name.strip()  # Just assign the values
        self.sum = f'Processing image of {self.name}'

        # Store a bunch of tokens, that can be used in the further processing (and to make edits in general)
        self._commons = CommonsBot()
        self._wikidata = WikidataBot()
        self._nl = NlBot()
        self._meta = MetaBot()
        self.qid = None  # this is the Wikidata item that we want to use
        self._claims = None  # temporary storage of the _claims @Wikidata
        self.mid = None  # id of the file on Wikimedia commons
        self.mc = None  # A dictionary to store the _claims for the Commons item in
        self.date = None  # Variable to store the data at which image was taken.
        self.comtext = None  # Text associated with the image on Commons (save for a couple of purposes)
        self.deaddate = None  # Centrally store date the person died
        self.catname = None  # Custom name of the Commons' category
        self.personname = None  # Store the name of the subject (used in the caption & response)

    def __str__(self):
        return f'Processing {self.file}, an image of {self.name}.'

    # Property, mainly used for debugging purposes
    @property
    def claims(self):
        return str(self._claims)

    # Function needed for interface: prepare the bot (use threading for efficiency)
    def prepare_image_data(self):
        # Setting up the initial data for Commons & Wikidata
        t1 = threading.Thread(target=self.get_commons_claims)
        t2 = threading.Thread(target=self.get_commons_text)
        t3 = threading.Thread(target=self.ini_wikidata)

        # Once initial data have been set up, second layer of data should be loaded
        t4 = threading.Thread(target=self.get_deceased_date)
        t5 = threading.Thread(target=self.collect_date)
        t4.start()
        t5.start()
        t4.join()
        t5.join()
        return True  # Just return True to indicate that the function was performed normally

    # Do a first task - make the category on commons
    def make_cat(self, name=None):
        'This function will, when triggered, generate an empty category on Wikimedia Commons.'
        if name is None:
            name = self.name  # Just use the value stored centrally
        elif not isinstance(name, str):
            raise TypeError('I can only use strings as category names!')
        content = r'{{Wikidata Infobox}}'  # Only call this method if there is a valid Wikidata item!
        pars = {'action': 'edit',
                'title': f'Category:{name}',
                'text': content,
                'summary': self.sum,
                'createonly': True,
                'bot': True}
        return self._commons.post(pars)

    # Second task - go to Wikidata and modify somethings there
    # First get the number of the item on Wikidata and the associated _claims
    def ini_wikidata(self):
        """this function will generate the item number and gets the _claims connected to that item"""
        # first, get the initial json from the API ()
        pars = {'action': 'wbgetentities',
                'titles': self.name,
                'sites': 'nlwiki',
                'props': 'claims'}
        q = self._wikidata.get(pars)['entities']
        self.qid = next(iter(q.keys()))
        # For some reason, the claims were no longer stored
        self._claims = q[self.qid]['claims']
        assert self.qid != '-1', 'I could not find a valid Wikidata item!'
        self.get_deceased_date()  # Get this limitation - once the claims are set
        self.collect_date()  # Get the date of the image - once the claims are set
        return self.qid, self._claims

    def interwiki(self):
        """This function will set the interwikilink at Wikidata"""
        if self._claims is None or self.qid is None:
            self.ini_wikidata()  # the Wikidata interface should first be  called to see what's already present
        # Begin to initialize the dictionary that will do the job
        iwd = {'action': 'wbsetsitelink',
               'id': self.qid,
               'bot': True,
               'summary': self.sum,
               'linksite': 'commonswiki',
               'linktitle': f'Category:{self.name}'}
        return self._wikidata.post(iwd)

    def set_image(self):
        "This function will modify the P18-property of the selected item (which inserts the image at commons)"
        if self._claims is None or self.qid is None:
            self.ini_wikidata()
        for i in self._claims.get('P18', ()):
            print('Watch out, there are already images present! Please check this!')
            j = i['mainsnak']['datavalue']['value']
            if j == self.file:
                return j  # It is already in there, stop the function
        # Continue with the setting of the new claim
        p18d = {'action': 'wbcreateclaim',
                'property': 'P18',
                'snaktype': 'value',
                'bot': True,
                'summary': self.sum,
                'entity': self.qid,
                'value': f'"{self.file}"'}
        k = self._wikidata.post(p18d)
        self._claims['P18'] = self._claims.get('P18', []) + [k['claim']]
        return k

    def commons_cat(self, custom=None):
        "This function will set the Commons category of the subject (P373)"
        if self._claims is None or self.qid is None:
            self.ini_wikidata()
        for i in self._claims.get('P373', ()):
            j = i['mainsnak']['datavalue']['value']
            if j == self.name:
                return j  # It is already in there, stop the frunction
        p18d = {'action': 'wbcreateclaim',
                'property': 'P373',
                'snaktype': 'value',
                'bot': True,
                'summary': self.sum,
                'entity': self.qid,
                'value': f'"{self.name}"'}  # Set a new P373 claim
        return self._wikidata.post(p18d)

    def purge(self):
        "This function will purge the cache of the corresponding page on Commons and the Wikidata-item"
        print('I am starting with purging the cache of the file on Commons.')
        purgedic = {'action': 'purge',
                    'titles': f'Category:{self.name}',
                    'forcelinkupdate': True,
                    'forcerecursivelinkupdate': True}
        self._commons.post(purgedic)
        p2d = purgedic.copy()
        print('Clearing the cache on Wikidata now.')  # Preparing to go to Wikidata
        p2d['titles'] = self.qid
        self._wikidata.post(p2d)
        print('Preparing to empty the cache on the Dutch Wikipedia')
        p3d = purgedic.copy()  # Also do the Dutch Wikipedia
        p3d['titles'] = self.name
        self._nl.post(p3d)

    # Generate a shortened URL to the image on Commons
    def short_url_commons(self):
        'This function will generate a shortened url for the image'
        url = 'https://' + urllib.parse.quote(
            f'commons.wikimedia.org/wiki/File:{self.file}')  # https:// added in front of the parser
        z = self._meta.short({'action': 'shortenurl',
                              'url': url})
        return z['shortenurl']['shorturl']

    def short_url_nlwiki(self):
        "This function will generate a shortened url for the article on nlwiki"
        url = 'https://' + urllib.parse.quote(
            f'nl.wikipedia.org/wiki/{self.name}')  # https:// added in front of the parser
        z = self._meta.short({'action': 'shortenurl',
                              'url': url})
        return z['shortenurl']['shorturl']

    def short_urls(self):
        return self.short_url_commons(), self.short_url_nlwiki()

    def get_deceased_date(self):
        "This function checks whether the subject is deceased, and when this happened."
        if not self._claims:
            self.ini_wikidata()
        claim = self._claims.get('P570')  # Returns none if no such claim is present
        if claim is None:
            # The claim was not set
            # Even though it is likely that the person is not dead, we'll set a placeholder
            # This does NOT mean that the queried object will die today or one of the coming days
            # This shenanigan is just a technicality to stop people from dating images in the future
            # There is thus no need to contact emergency@ after seeing this code
            self.deaddate = dt.datetime.utcnow().replace(hour=0,
                                                         minute=0,
                                                         second=0) + dt.timedelta(days=1)
            return self.deaddate
        for i in claim:
            if 'mainsnak' in i:
                main = i['mainsnak']['datavalue']['value']['time']
                self.deaddate = dt.datetime.strptime(main,
                                                     "+%Y-%m-%dT%H:%M:%SZ").replace(hour=0,
                                                                                    minute=0,
                                                                                    second=0)
                return self.deaddate

    def check_deceased(self, custom=None):
        if self.deaddate is None:
            self.get_deceased_date()
        # Check whether the supplied date is valid
        if custom is None:
            custom = self.date
        return custom <= self.deaddate  # True if the date is valid, False if there's a problem

    def get_date_from_commons_text(self):
        "Scans the source code of the file page on Commons to determine the date at which the image was made"
        if self.comtext is None:
            self.get_commons_text()
        date_regex = r'\|\s*[Dd]ate\s*=.+?[\}\|\n]'  # Regex to search where the match occurs
        date_match = re.search(date_regex, self.comtext)
        if date_match is None:
            return None  # No usefull date in the Commons source text
        date_found = self.comtext[date_match.start():date_match.end()].strip().lower()
        date_found = date_found.replace(' ', '').replace('|date=', '')
        print(date_found)

    def collect_date(self):
        "Tries to figure out when an image was generated"
        if self.date is not None:
            return self.date  # Abort the function execution here
        z = self._commons.get({'action': 'query',
                               'titles': f'File:{self.file}',
                               'prop': 'imageinfo',
                               'iiprop': 'commonmetadata'})
        q = next(iter(z['query']['pages'].values()))['imageinfo'][0]['commonmetadata']
        t = [i['value'] for i in q if 'datetime' in i['name'].lower().strip()]
        u = sorted((i for i in t if i.count(':') == 4))  # Filter the correct format
        if u:
            self.date = dt.datetime.strptime(u[0],
                                     "%Y:%m:%d %H:%M:%S").replace(hour=0, minute=0,
                                                                        second=0)  # Remove the precise timestamp

        return None

    def date_meta(self, d=None):
        # SIGNIFICANT CHANGES WERE MADE TO THIS FUCNTION - BE CAREFUL!!!
        "Writes the date of image generation and pushes it to Wikidata"
        if d is None:
            d = self.collect_date()  # We still need to get the date
        if d:
            cl = self._claims.get('P18')  # We can get this one - image value passed to the system
            assert cl is not None, 'Watch out, we found an error'
            for i in cl:
                if i['mainsnak']['datavalue']['value'] == self.file:
                    idc = i['id']  # Locate the claim containing the image name
                    break  # Stop the iterations
            if 'P585' not in idc.get('qualifiers', ()):  # Code should only be executed if this hasn't been specified yet
                if self.check_deceased() is False:
                    return None  # Something's wrong
                val = f'"time": "+{d.isoformat()}Z", "timezone": 0, "before": 0, "after": 0, "precision": 11, "calendarmodel": "http://www.wikidata.org/entity/Q1985727"'
                n = {'action': 'wbsetqualifier',
                     'claim': idc,
                     'value': '{' + val + '}',
                     'snaktype': 'value',
                     'property': 'P585',
                     'summary': self.sum,
                     'bot': True}
                self._wikidata.post(n)
        else:
            print('Could not find a useful date')

    def get_commons_claims(self):
        "This function will get the _claims on Commons (and content of the page)"
        temp = self._commons.get({'action': 'wbgetentities',
                                  'props': '_claims',
                                  'sites': 'commonswiki',
                                  'titles': f'File:{self.file}'})['entities']
        self.mid = next(iter(temp))
        self.mc = next(iter(temp.values())).get('statements', [])

    def get_commons_text(self):
        "This function will get the content of the file page on Commons"
        if self.comtext is None:
            self.comtext = self._commons.get({'action': 'parse',
                                              'page': f'File:{self.file}',
                                              'prop': 'wikitext'})['parse']['wikitext']['*']
        return self.comtext  # Store this one as a variable of the class, will be more pratical

    def ticket(self):
        "This function will add the ticket number (from the Wikiportrait template) as P6305 on Commons"
        # First, check whether the number has already been set or not
        if self.mc is None:
            self.get_commons_claims()
        if 'P6305' not in self.mc:  # the property still has to be set
            if self.comtext is None:
                self.get_commons_text()
            tick = re.findall(r'(\{\{wikiportrait2\|\d{16})', self.comtext)
            if not tick:
                tick = re.findall(r'(\{\{PermissionTicket\|id=\d{16})', self.comtext)
            if not tick:
                print("I could not find a valid ticket number, will skip this for now.")
                return None  # No match found, just emptying this one
            num = tick[0].replace('{', '').replace('}', '').replace('wikiportrait2|', '').replace(
                'PermissionTicket|id=', '')
            if not num.strip().isdigit():
                print('Something went wrong, the obtained Ticket number is not an integer, so skipping.')
                return None
            td = {'action': 'wbcreateclaim',
                  'snaktype': 'value',
                  'entity': self.mid,
                  'property': 'P6305',
                  'value': f'"{num}"',
                  'summary': self.sum,
                  'bot': True}
            self._commons.post(td)
        else:
            print('The ticket number is already added as a claim.')

    def set_license_properties(self):
        "This function will set the copyright related structured data (P275 and P6216)"
        if self.mc is None:
            self.get_commons_claims()  # Set the _claims using the previously defined function

        # First, do the P275 thingy
        if 'P275' not in self.mc:
            if self.comtext is None:
                self.get_commons_text()
            k = re.findall('PERMISSION=\s?\S+ [\d.]+', self.comtext.upper())  # Filter the permission rule (using regex)
            lic = sorted((i for i in k if i), key=lambda t: len(t))[-1].replace('PERMISSION', '').replace('=',
                                                                                                          '').strip()
            # lic = 'CC-BY-SA 4.0'
            licq = Image.licenses.get(lic)
            if licq is not None:  # We found an item for Wikidata that can be connected to this one
                val = f'"entity-type": "item", "numeric-id": {licq},"id": "Q{licq}"'
                dic = {'action': 'wbcreateclaim',
                       'summary': self.sum,
                       'property': 'P275',
                       'bot': True,
                       'entity': self.mid,
                       'snaktype': 'value',
                       'value': '{' + val + '}'}
                self._commons.post(dic)
                print('Copyright license (P275) has been set.')
                del dic  # Removing to avoid all kind of conflicts
            else:
                print('Could not find a license')
                return None  # No licence found
        else:
            print('The P275 was already set')

        # Now set the second claim
        if 'P6216' not in self.mc:
            if self.comtext is None:
                self.get_commons_text()
            if any((i in self.comtext.lower() for i in ('pd', 'public domain'))):
                print('I found a potential indication that the file could be in the public domain!')
                a = input('\nIs this an incorrect indication? [y/n] ').lower().strip()
                if a == 'n':
                    print('Terminating the process of P6216 setting')
                    return None
            val = '"entity-type": "item", "numeric-id": 50423863,"id": "Q50423863"'
            dic = {'action': 'wbcreateclaim',
                   'summary': self.sum,
                   'property': 'P6216',
                   'bot': True,
                   'entity': self.mid,
                   'snaktype': 'value',
                   'value': '{' + val + '}'}
            self._commons.post(dic)
            print("Copyright status (P6216) is set.")
        else:
            print('The copyright status was already present')

    def add_category(self, catname=None):
        "This function will append the category generated before if it is not yet in the Commons datasheet"
        if self.comtext is None:
            self.get_commons_text()
        if catname is None:  # Provide the option to override some things
            catname = self.name
        cat = f'[[Category:{catname}]]'
        if cat in self.comtext:
            print('The category was already in the text')
            return None
        dic = {'action': 'edit',
               'bot': True,
               'title': f'File:{self.file}',
               'summary': f'{self.sum}: adding correct category',
               'nocreate': True,
               'appendtext': '\n' * (not self.comtext.endswith('\n')) + cat + '\n'}
        self._commons.post(dic)
        print('Category has been added.')

    def depicts(self):
        "This function adds a P180-statement to the file on Commons"
        if self.mc is None:
            self.get_commons_claims()
        if self.qid is None:
            self.ini_wikidata()
        if 'P180' not in self.mc:
            val = f'"entity-type": "item", "numeric-id": {self.qid[1:]},"id": "{self.qid}"'
            dic = {'action': 'wbcreateclaim',
                   'summary': f'{self.sum}, upload via #Wikiportret',
                   'property': 'P180',
                   'bot': True,
                   'entity': self.mid,
                   'snaktype': 'value',
                   'value': '{' + val + '}'}
            self._commons.post(dic)
        else:
            print('Property P180 already present')

    def generate_confirmation(self, shorts=None):
        "This function can be used to generate a standard response for the uploader"
        commonslink, nllink = shorts if shorts is not None else self.short_urls()
        lines = (
            f"Hartelijk dank voor het vrijgeven van uw afbeelding. Ik heb de afbeelding in de centrale mediadatabase van Wikimedia (Wikimedia Commons) geplaatst. U kunt de afbeelding hier bekijken: {commonslink} .",
            f"Daarnaast heb ik de afbeelding in dit artikel geplaatst op de Nederlandstalige Wikipedia: {nllink} .",
            "Dank voor de donatie van deze afbeelding!")
        # The lines are prepared, now clearly print it
        return '\n\n'.join(lines)  # Returns the string itself. The final printing stuff is done in the interface

    def generate_caption(self):
        "Generates a caption to be added to the article with the image"
        # Important case: date was filed
        if self.date:
            return f'{self.name} in {self.date.year}'
        return self.name

    def add_image_to_article(self):
        "This function is designed to add the image to the article in an automated fashion"
        # Get the current Wikitext
        parsedic = {'action': 'parse',
                    'page': self.name,
                    'prop': 'wikitext'}
        content = self._nl.get(parsedic)['parse']['wikitext'][
            '*']  # The wikitext of the page (split into the various lines)

        low = content.lower()  # Store once to reduce computation time

        if '#redirect' in low or '#doorverwijzing' in low:
            print('\nYOU REQUESTED TO A REDIRECT PAGE - ABORTING - PLEASE REVIEW THIS MANUALLY')
            time.sleep(3)
            return None  # Do not continue with this function

        # Check whether or not an infobox is present on the article (and get the rule with the image)
        if self.file in content:
            print('\n\nERROR: Image was already on the page, please verify this!\n\n')
            time.sleep(3)  # Sleep two seconds before continuing, accentuate the error to the operator
            return None  # File is already on the page, abort the run
        if '{{infobox' in low:  # If possible, we would like to place the image in an infobox
            # An infobox has been detected, initiate process of finding the place where the infobox
            pattern1 = r'\|\s*afbeelding\s*=[^\|]+'  # Regex pattern to find out where the image is located
            image_match = re.search(pattern1, low)

            # Second part: add the image to the text of the article (step only needed if an infobox is present, other case can be handled straight away)
            if image_match is not None:
                # Case in which an infobox is present (so, some post-processing steps needed)
                line = content[image_match.start():image_match.end()]
                if len(line.strip().replace(' ',
                                            '')) > 12:  # length of the line > len(|afbeelding=), there is already an image there
                    print('\n\nERROR: There was already an image in the infobox. Please check this!\n\n')
                    time.sleep(3)  # Sleep two seconds before continuing, accentuate the error to the operator
                    return None  # Abort the run

                # Continue with the completion
                content = content.replace(line, line.rstrip() + f' {self.file}\n')

                # Next step: add caption to the infobox
                caploc = re.search(r'\|\s*(bij|onder)schrift\s*=[^\|]+',
                                   content.lower())  # find where caption should be inserted - DO NOT REUSE LOW SINCE CHANGES WERE MADE
                if caploc is not None:
                    check_caption = content[caploc.start():caploc.end()].rstrip().split('=')
                    if len(check_caption) == 1 or not check_caption[1]:
                        capline = content[caploc.start():caploc.end()]
                        content = content.replace(capline, capline.rstrip() + f' {self.generate_caption()}\n')
                    else:
                        # There is already a caption present, there's no need to add something new
                        print('\nWARNING: there was already a caption present!\n')
                        time.sleep(1)
            else:
                # Case: there is an infobox, but we don't have the Image parameter present - we need to add it ourselves
                # Determine the precise location of the infobox (and where we need to insert the image)
                append_location = re.search(r'\{\{infobox[^\|]*', low).end()
                # Determine the number of spaces that must be inserted to get a nice lay-out of the infobox
                next_par = re.match(r'\|[^=]+', low[append_location:])
                spaces = next_par.end() - next_par.start() - 12  # The number of additional spaces that we must insert
                # Determine what text we should add
                add_text = f'| afbeelding{" " * spaces}= {self.file}' + '\n' * (low[append_location - 1] == '\n')
                content = content[:append_location] + add_text + content[append_location:]
                print("\nEr ontbraken enkele parameters in de infobox, CHECK DE EDITS VAN DE BOT!")
                time.sleep(3)  # Give the operator the time to read the warning

        # Third part: no infobox is present - just prepend the new image
        else:
            content = f'[[File:{self.file}|thumb|{self.generate_caption()}]]\n' + content

        # Remove template asking for a photo
        for i in ('fotogewenst', 'verzoek om afbeelding', 'afbeelding gewenst'):
            loc = re.search('{{%s}}' % (i.lower()), content.lower())
            if loc is not None:
                content = content.replace(content[loc.start():loc.end() + 1], '').strip()

        # Fourth part: post new content on the wiki (bot edit)
        editdic = {'action': 'edit',
                   'title': self.name,
                   'text': content,
                   'notminor': True,
                   'bot': False,
                   'nocreate': True,
                   'summary': '+Upload via #Wikiportret'}
        self._nl.post(editdic)

        # Some cleaning, save the garbage collector some work
        del content, low

    def __call__(self, commons_perm=True, category=True, data_connect=True, nlwiki=True, conf=False):
        """This function can be used to do handle an entire request at once.
        Arguments (and their function):
            * Commons_perm: if set to True, the bot will set all permission-related properties of the file @Commons
            * Category: if set to True, the bot will create and set the category on Commons AND connect it to the Wikidata item.
            * Data_connect: if set to True, the image will be connected to the given person's Wikidata item.
            * Nlwiki: if set to True, the image will be placed on the Dutch Wikipedia article.
            * Conf: is set to True, the confirmation for VRT will be printed explicitly.
        """

        # Category on Wikimedia Commons
        print('I will now process the image on Commons')

        # Properties that should be set on Commons
        print(
            "I'll initialize the interface for Commons (getting the _claims already present and the page of the file).")
        try:
            # Perform these tasks at all time
            self.get_commons_claims()
            self.get_commons_text()
            if commons_perm is True:  # Only perform this task when requested
                print('I will now add the P6305 property to the file on Commons - the VRT-ticket number')
                self.ticket()
                print('Now adding other information on copyright (P275/P6216)')
                self.set_license_properties()
                print('Property set, I will need support from Wikidata for the next steps.')
        except:
            print('Something went wrong while processing the stuff for Commons.')

        # Setting the properties on Wikidata
        try:
            # Always perform this task
            print(
                'Getting _claims and other data from Wikidata before starting to work on that item & its associated stuff on Commons.')
            self.ini_wikidata()
            print(
                'Initialization done, I can now safely generate the category and link to Wikidata on Commons and tell Commons who is depicted (if you allow me to).')
            if category is True:  # Only perform these edits when the user commands them
                print(
                    "I'm now making the category on Commons. If an error occurs, it likely means that the category already existed.")
                self.make_cat()
                print(
                    'The eleventh commandment of the Lord states that we should also check whether the category is attached to the file, so doing that now')
                self.add_category()
                print('I will add the category on Commons to Wikidata.')
                self.interwiki()
                self.commons_cat()
                print('The category was placed on Commons and connected to Wikidata.')
            print('I have done all operations that should be done on Commons.')
            if data_connect is True:  # Only connect the image if ordered to do so
                print('I will now identify the person in the image, as requested.')
                print('Adding a P180-claim to Commons to list the identity of the depicted person.')
                self.depicts()
                print('I added the Wikidata item of the depicted person as P180 to the image.')
                print('Now continuing with the P18 property (connecting the image to the Wikidata item).')
                self.set_image()
                print('The image has been set. I will now look for a date.')
                # Doing one more Wikidata related thing, cause this needs the _claims on Commons
                print('I proceed with setting the date as a qualifyer for the image.')
                self.date_meta()
                print('The identity of the depicted is now properly listed on Wikidata and Commons.')

        except AssertionError:
            print(
                "I could NOT find a valid Wikidata-item. Please verify the input, and then rerun the bot. You might have to manually create the item.")

        # Last bit: add image to the Dutch Wikipedia (manually, to trigger watchlists)
        if nlwiki is True:
            print('I will now add the image to the Dutch Wikipedia.')
            self.add_image_to_article()
            print(
                'I finished the addition. Check for eventual errors above. We hope you enjoyed the flight with us and hope to see you again!')

        # Purge the cache on Wikidata, Commons and Wikipedia-nl
        print('OKay, I will now start to purge the cache of the various items.')
        self.purge()

        # And now, the short url as final touch
        print('I will now just generate two short url-links, which look nicer in the ticket of the customer.')
        k = self.short_urls()
        print(f'The short url for the Commons file is {k[0]}')
        print(f'The short url for the article on nlwiki is {k[1]}')
        confirmation = self.generate_confirmation(k)  # pass the short urls as arguments, reduce the amount of API calls
        print('I generated the confirmation')
        if conf is True:  # Default is False (for interaction with the other parts of the interface)
            print(confirmation)
        return self.name, k, confirmation


# Use this code to run the bot
if __name__ == '__main__':  # Do not run this code when we are using the interface
    a = Image('Tonie ehlen-1668888766.jpeg.jpeg', "Tonie Ehlen")
    a(False, False, False, True, False)  # Still keep the standard confirmation
    # a.ticket()
    # a.set_licence_properties()
