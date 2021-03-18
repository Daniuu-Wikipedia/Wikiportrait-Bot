# -*- coding: utf-8 -*-
"""
Created on Wed Feb 10 19:38:55 2021

@author: Daniuu

This is a script that should make it easier to process requests done through Wikiportret.

The bot will do a couple of tasks:
    1) It will create a new category for the name of the person on the image
    2) It will post the image and category created in 1 to a Wikidata-item

"""

import requests
import urllib
import time
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
        return self._token
    
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
            params['token'] = self.verify_token()[0] #Generate a new token
        params['format'] = 'json'
        params['maxlag'] = 5 #Using the standard that's implemented in PyWikiBot
        self.ti.append(float(time.time()))
        k = requests.post(self.api, data=params, auth=self._auth).json()
        
        if 'error' in k:
            print('An error occured somewhere') #We found an error
            if 'code' in k['error'] and 'maxlag' in k['error']['code']:
                print('Maxlag occured, please try to file the request at a later point in space and time.')
        
class WikidataBot(Bot):
    def __init__(self):
        super().__init__('https://www.wikidata.org/w/api.php')

class CommonsBot(Bot):
    def __init__(self):
        super().__init__('https://commons.wikimedia.org/w/api.php')

class MetaBot(Bot):
    def __init__(self):
        super().__init__('https://meta.wikimedia.org/w/api.php')

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
        self.file, self.name = file, name #Just assign the values
        self.sum = f'Processing image of {self.name}'
        
        #Store a bunch of tokens, that can be used in the further processing (and to make edits in general)
        self._commons = CommonsBot()
        self._wikidata = WikidataBot()
        self._nl = NlBot()
        self._meta = MetaBot()
        self.qid = None #this is the Wikidata item that we want to use
        self.claims = None #temporary storage
        
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
        pars['token'] = self.commons_token()
        return self.post(Image.commons, pars)
    
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
        return self._wikidata.post(p18d)
    
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
        "This function will purge the cache of the corresponding page on Commons"
        purgedic = {'action':'purge',
                    'titles':f'Category:{self.name}',
                    'forcelinkupdate':True,
                    'forcerecursivelinkupdate':True}
        self._commons.post(purgedic)
    
    #Generate a shortened URL to the image
    def short_url(self):
        'This function will generate a shortened url for the image'
        url = 'https://' + urllib.parse.quote(f'commons.wikimedia.org/wiki/File:{self.file}') #https:// added in front of the parser
        z = self._meta.post({'action':'shortenurl',
                            'url':url})
        return z['shortenurl']['shorturl']
    
     #This handy function will assure that all actions can be done at once
    def __call__(self):
        "This function can be used to do handle an entire request at once"
        print('Initializing the Wikidata interface')
        self.ini_wikidata()
        print('Initialization done, proceeding with the interwikilink to Commons')
        self.interwiki()
        print('Now continuing with the P18 property')
        self.set_image()
        print('The image has been set. Now starting to process the category on Commons')
        self.commons_cat()
        print('The category has been set. I will now switch to purge the cache on Commons')
        self.purge()
        print('Cache has been purged, now generating the short url')
        k = self.short_url()
        print(f'The generated short url is {k}')
        print('Done processing the request')
