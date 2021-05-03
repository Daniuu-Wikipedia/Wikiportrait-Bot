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
    
Information can be found in Wikiportret ticket 2021021010009189 (OTRS access required)
"""

import requests
import urllib
import time
import datetime as dt
import re #Regex to filter the ticket number
from requests_oauthlib import OAuth1

class Bot:
    'This class is designed to facilitate all interactions with Wikipedia (and to get the processing functions out of other calsses)'
    max_edit = 5 #The maximum number of edits that a single bot can do per minute
    
    def __init__(self, api, m=None):
        'Constructs a bot, designed to interact with one Wikipedia'
        self.api = api
        self.ti = [] #A list to store the time stamps of the edits in
        self._token = None #This is a token that is handy
        self._auth = None #The OAuth ID (this is the token that will allow the auth - store this for every bot)
        self._max = Bot.max_edit if m is None else m #this value is set, and can be changed if a bot bit would be granted
    
    def __str__(self):
        return self.api.copy()
    
    def verify_OAuth(self, file="Tokens_Wikiportraitbot.txt"):
        'This function will verify whether the OAuth-auth has been configured. If not, it will do the configuration.'
        if self._auth is None:
            with open(file, 'r') as secret:
                self._auth = OAuth1(*[i.strip() for i in secret][1::2]) #This is the reason why those keys should never be published
    
    def verify_token(self):
        if self._token is None:
            self.get_token()
        elif float(time.time()) - self._token[1] > 8:
            self.get_token() #Tokens expire after approximately 8 seconds, so generate a new one
        return self._token[0]
    
    def get(self, payload):
        "This function will provide functionality that does all the get requests"
        self.verify_OAuth()
        payload['format'] = 'json' #Set the output format to json
        return requests.get(self.api, params=payload, auth=self._auth).json()
    
    def get_token(self, t='csrf', n=0, store=True):
        'This function will get a token'
        assert isinstance(t, str), 'Please provide a string as a token!'
        pay = {'action':'query',
               'meta':'tokens',
               'type':t}
        z = self.get(pay), float(time.time())
        try:
            if store is True:
                self._token = z[0]['query']['tokens'][f'{t}token'], z[1]
                return self._token[0]
            else:
                return self._token[0] #Just return the token
        except KeyError:
            assert n <= 1, 'Cannot generate the requested token'
            return self.get_token(t, n + 1)
    
    def post(self, params):
        assert 'action' in params, 'Please provide an action'
        t = float(time.time())
        self.ti = [i for i in self.ti if i >= t - 60] #Clean this mess
        if len(self.ti) >= Bot.max_edit: #Check this again, after doing the cleaning
            print('Going to sleep for a while')
            time.sleep(20) #Fuck, we need to stop
            return self.post(params) #run the function again - but: with a delay of some 60 seconds
        if 'token' not in params: #Place this generation of the key here, to avoid having to request too many tokens
            params['token'] = self.verify_token() #Generate a new token
        params['format'] = 'json'
        params['maxlag'] = 5 #Using the standard that's implemented in PyWikiBot
        self.ti.append(float(time.time()))
        k = requests.post(self.api, data=params, auth=self._auth).json()
        if 'error' in k:
            print('An error occured somewhere') #We found an error
            if 'code' in k['error'] and 'maxlag' in k['error']['code']:
                print('Maxlag occured, please try to file the request at a later point in space and time.')
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
    #Program some endpoints as static variables (they will be common for all objects)
    commons = "https://commons.wikimedia.org/w/api.php"
    wikidata = "https://www.wikidata.org/w/api.php"
    
    def __init__(self, file, name):
        """
        This function will do some construction works
        ----------
        file : string
            This string should contain the name of the image that was processed.
        name : string
            This parameter contains the name of the corresponding person on nl-wiki.
        """
        self.file, self.name = file.replace('File:', '').strip(), name.strip() #Just assign the values
        self.sum = f'Processing image of {self.name}'
        
        #Store a bunch of tokens, that can be used in the further processing (and to make edits in general)
        self._commons = CommonsBot()
        self._wikidata = WikidataBot()
        self._nl = NlBot()
        self._meta = MetaBot()
        self.qid = None #this is the Wikidata item that we want to use
        self.claims = None #temporary storage
        self.mid = None #id of the file on Wikimedia commons   
        self.mc = None #A dictionary to store the claims for the Commons item in
    def __str__(self):
        return f'Processing {self.file}, an image of {self.name}.'
                
    #Do a first task - make the category on commons
    def make_cat(self):
        'This function will, when triggered, generate an empty category on Wikimedia Commons'
        content = r'{{Wikidata Infobox}}'
        pars = {'action':'edit',
                'title':f'Category:{self.name}',
                'text':content,
                'summary':self.sum,
                'createonly':True,
                'bot':True}
        return self._commons.post(pars)
    
    #Second task - go to Wikidata and modify somethings there
    #First get the number of the item on Wikidata and the associated claims
    def ini_wikidata(self):
        "this function will generate the item number and gets the claims connected to that item"
        #first, get the initial json from the API ()
        pars = {'action':'wbgetentities',
                'titles':self.name,
                'sites':'nlwiki',
                'props':'claims'}
        q = self._wikidata.get(pars)['entities']
        self.qid = next(iter(q.keys()))
        self.claims = q[self.qid]['claims']
        return self.qid, self.claims
        
    def interwiki(self):
        "This function will set the interwikilink at Wikidata"
        if self.claims is None or self.qid is None:
            self.ini_wikidata() #the Wikidata interface should first be  called to see what's already present
        #Begin to initialize the dictionary that will do the job
        iwd = {'action':'wbsetsitelink',
                'id':self.qid,
                'bot':True,
                'summary':self.sum,
                'linksite':'commonswiki',
                'linktitle':f'Category:{self.name}'}
        return self._wikidata.post(iwd)
        
    def set_image(self):
        "This function will modify the P18-property of the selected item (which inserts the image at commons)"
        if self.claims is None or self.qid is None:
            self.ini_wikidata()
        for i in self.claims.get('P18', ()):
            print('Watch out, there are already images present! Please check this!')
            j = i['mainsnak']['datavalue']['value']
            if j == self.file:
                return j #It is already in there, stop the frunction
        #Continue with the setting of the new claim
        p18d = {'action':'wbcreateclaim',
                    'property':'P18',
                    'snaktype':'value',
                    'bot':True,
                    'summary':self.sum,
                    'entity':self.qid,
                    'value':f'"{self.file}"'}    
        k = self._wikidata.post(p18d)
        self.claims['P18'] = self.claims.get('P18', []) + [k['claim']]
        return k
    
    def commons_cat(self):
        "This function will set the Commons category of the subject (P373)"
        if self.claims is None or self.qid is None:
            self.ini_wikidata()
        for i in self.claims.get('P373', ()):
            j = i['mainsnak']['datavalue']['value']
            if j == self.name:
                return j #It is already in there, stop the frunction
        p18d = {'action':'wbcreateclaim',
                    'property':'P373',
                    'snaktype':'value',
                    'bot':True,
                    'summary':self.sum,
                    'entity':self.qid,
                    'value':f'"{self.name}"'} #Set a new P373 claim
        return self._wikidata.post(p18d)
      
    def purge(self):
        "This function will purge the cache of the corresponding page on Commons and the Wikidata-item"
        purgedic = {'action':'purge',
                    'titles':f'Category:{self.name}',
                    'forcelinkupdate':True,
                    'forcerecursivelinkupdate':True}
        self._commons.post(purgedic)
        p2d = purgedic.copy()
        print('doing Wikidata')
        p2d['titles'] = self.qid
        self._wikidata.post(p2d)
    
    #Generate a shortened URL to the image on Commons
    def short_url_commons(self):
        'This function will generate a shortened url for the image'
        url = 'https://' + urllib.parse.quote(f'commons.wikimedia.org/wiki/File:{self.file}') #https:// added in front of the parser
        z = self._meta.short({'action':'shortenurl',
                            'url':url})
        return z['shortenurl']['shorturl']
    
    def short_url_nlwiki(self):
        "This function will generate a shortened url for the article on nlwiki"
        url = 'https://' + urllib.parse.quote(f'nl.wikipedia.org/wiki/{self.name}') #https:// added in front of the parser
        z = self._meta.short({'action':'shortenurl',
                            'url':url})
        return z['shortenurl']['shorturl']
    
    def short_url(self):
        return self.short_url_commons(), self.short_url_nlwiki()
    
    def date_meta(self):
        "This function will get the date at which the file was taken from Commons and adds it as a qualifier."
        z = self._commons.get({'action':'query',
                               'titles':f'File:{self.file}',
                               'prop':'imageinfo',
                               'iiprop':'commonmetadata'})
        q = next(iter(z['query']['pages'].values()))['imageinfo'][0]['commonmetadata']
        t = [i['value'] for i in q if 'datetime' in i['name'].lower().strip()]
        u = sorted((i for i in t if i.count(':') == 4)) #Filter the correct format
        if u:
            d = dt.datetime.strptime(u[0], "%Y:%m:%d %H:%M:%S").replace(hour=0, minute=0, second=0) #Remove the precise timestamp
            cl = self.claims.get('P18') #We can get this one
            assert cl is not None, 'Watch out, we found an error'
            for i in cl:
                if i['mainsnak']['datavalue']['value'] == self.file:
                    idc = i['id']
                    break #Stop the iterations
            if 'P585' not in i.get('qualifiers', ()): #Code should only be executed if this hasn't been specified yet
                val = f'"time": "+{d.isoformat()}Z", "timezone": 0, "before": 0, "after": 0, "precision": 11, "calendarmodel": "http://www.wikidata.org/entity/Q1985727"'
                n = {'action':'wbsetqualifier',
                     'claim':idc,
                     'value':'{' + val + '}',
                     'snaktype':'value',
                     'property':'P585',
                     'summary':self.sum,
                     'bot':True}
                self._wikidata.post(n)
        else:
            print('Could not find a useful date')
    
    def get_commons_claims(self):
        "This function will get the claims on Commons (and content of the page)"
        temp = self._commons.get({'action':'wbgetentities',
                                  'props':'claims',
                                  'sites':'commonswiki',
                                  'titles':f'File:{self.file}'})['entities']
        self.mid = next(iter(temp))
        self.mc = next(iter(temp.values())).get('statements', [])
    
    def ticket(self):
        "This function will add the ticket number (from the Wikiportrait template) as P6305 on Commons"
        #First, check whether the number has already been set or not
        if self.mc is None:
            self.get_commons_claims()
        if 'P6305' not in self.mc: #the property still has to be set
            text = self._commons.get({'action':'parse',
                       'page':f'File:{self.file}',
                       'prop':'wikitext'})['parse']['wikitext']['*']
            tick = re.findall(r'(\{\{wikiportrait2\|\d{16})', text)[0]
            if tick is None:
                return None #No match found, just emptying this one
            num = tick.replace('{', '').replace('}', '').replace('wikiportrait2|', '')
            td = {'action':'wbcreateclaim',
                  'snaktype':'value',
                  'entity':self.mid,
                  'property':'P6305',
                  'value':f'"{num}"',
                  'summary':self.sum,
                  'bot':True}
            self._commons.post(td)
        else:
            print('We already have that one')
    
    def depicts(self):
        "This function adds a P180-statement to the file on Commons"
        if self.mc is None:
            self.get_commons_claims()
        if self.qid is None:
            self.ini_wikidata()
        if 'P180' not in self.mc:
            val = f'"entity-type": "item", "numeric-id": {self.qid[1:]},"id": "{self.qid}"'
            dic = {'action':'wbcreateclaim',
                   'summary':self.sum,
                   'property':'P180',
                   'bot':True,
                   'entity':self.mid,
                   'snaktype':'value',
                   'value':'{' + val + '}'}
            self._commons.post(dic)
        else:
            print('Property P180 already present')
    
    def __call__(self):
        #'''
        "This function can be used to do handle an entire request at once"
        print('Making the category on Commons')
        self.make_cat()
        print('Initializing the Wikidata interface')
        self.ini_wikidata()
        print('Initialization done, proceeding with the interwikilink to Commons')
        self.interwiki()
        print('Now continuing with the P18 property')
        self.set_image()
        print('The image has been set. Now starting to process the category on Commons')
        self.commons_cat()
        print('The category has been set.')
        print("I'll initialize the properties for Commons")
        self.get_commons_claims()
        print('I will now add the P6305 property to the file on Commons')
        self.ticket()
        print('Property set, now adding who is depicted (P180)')
        self.depicts()
        print('I proceed with setting the date')
        self.date_meta()
        print('Date set, now switching to purging the cache')
        self.purge()
        print('Done processing the request')
        #'''
        print('Now generating the short url')
        k = self.short_url()
        print(f'The short url for the Commons file is {k[0]}')
        print(f'The short url for the article on nlwiki is {k[1]}')
        return self.name, k

class Interface:
    "This class will contain all code for the cmd I/O"        
    def __init__(self):
        self._the_ones = [] #The ones
        
    def __str__(self):
        return str(self._the_ones)
    
    def prompt_input(self):
        "This function will call for the amount of images that should be processed"
        print("Do you want to use the bot using the menu, or would you like to read from a file?")
        print('Watch out! Inputs are case sensitive!')
        print("Type exit to quit.")
        print('Type y to continue with the menu, n to read from a file.')
        jos = input('y/n? ').lower().strip()
        if jos not in {'y', 'n', 'exit'}:
            print('I did not recognise that input\n')
            return self.prompt_input()
        if jos == 'y':
            return self.ask_n()
        elif jos == 'exit':
            return None
        return self.ask_file()
        
    def ask_n(self):
        "This function will ask a given amount of images"
        print('\n')
        print("We will now go through the processing together")
        file = input("Please enter the name of the file that should be processed. ").strip()
        name = input("Please enter the corresponding name of the article on the Dutch Wikipedia. ").strip()
        jezeken = Image(file, name)
        self._the_ones.append(jezeken()) #Call the processing function and store the url
        print('\n')
        print('Would you like to continue processing another image (y/n)?')
        print('Entering n will terminate the program')
        a = input('Would you like to continue processing? [y/n]').lower().strip()
        if a not in {'y', 'n', 'exit'}:
            print('I did not recognise that input')
            a = input('Would you like to continue processing? [y/n]').lower().strip()
            if not a in {'y', 'n', 'exit'}:
                print("Terminating program due to corrupt input")
                return self.print_final()
        #Continue
        if a == 'y':
            return self.ask_n() #Restart
        print("Stopping")
        return self.print_final()
    
    def read_from_file(self, file, delimiter=';'):
        with open(file, 'r') as datafile:
            lines = [i.strip().lower() for i in datafile]
        for i in lines:
            #Process the lines in the original file
            separated = [j.strip() for j in i.strip(delimiter)]
            im = Image(*separated)
            self._the_ones.append(im())
        print('Done reading from the file. I stop here. Thanks for using WikiportraitBot!')
        return self.print_final()
    
    def print_final(self):
        "This function will print the final output"
        order = ["Target", "Url to Commons", "Url to nlwiki"]
        for i in order + self._the_ones:
            print('\t'.join(i))
  
    
#Use this code to run the bot   
a = Image("Pierre Nicolas Croquison.jpg", "Pierre Nicolas Croquison")
a()