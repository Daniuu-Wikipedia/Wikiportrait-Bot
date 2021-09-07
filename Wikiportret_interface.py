# -*- coding: utf-8 -*-
"""
Created on Sun Jun 27 13:02:59 2021

This is the interface that allows Wikiportret to operate through the command line

@author: Daniuu
"""

from Wikiportret_core import * #Import all modules from the Wikiportret core in this interface

class Interface:
    "This class will contain all code for the cmd I/O"        
    def __init__(self):
        self()
        
    def __str__(self):
        return str(self._the_ones)
        
    def ask_n(self):
        "This function will ask a given amount of images"
        print('\n')
        print("I am now preparing to process the file. Please pass the file name on Commons and the nlwiki article below.")
        print('For devs or people who accidentally (re)started me: just type exit to stop the bot.')
        file = input("Please enter the name (NOT THE URL) of the file that should be processed. ").strip()
        if file.strip() == 'exit':
            return None
        name = input("Please enter the corresponding name of the article on the Dutch Wikipedia. ").strip()
        Image(file, name)() #The required text will be printed
        print('\n')
        del name, file #Remove these variables from memory, we don't need them any longer
        print('I will now restart the cyle, simply close this window to stop. No computers will be harmed in due course.')
        return self.ask_n()
            
    def __call__(self):
        "This function is used to start the bot"
        print('Welcome at WikiportraitBot! I will be your humble assistant on your quest to process images from Wikiportret')
        print('I will now prepare the first file for you!')
        return self.ask_n() #Calls the method that does the processing 

#Code used to run the bot
z = Interface()