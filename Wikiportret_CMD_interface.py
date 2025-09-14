# -*- coding: utf-8 -*-
"""
Created on Sun Jun 27 13:02:59 2021

This is the interface that allows Wikiportret to operate through the command line

@author: Daniuu
"""
from time import sleep
from Wikiportret_core import *  #Import all modules from the Wikiportret core in this interface

class Interface:
    """This class will contain all code for the cmd I/O"""

    def __init__(self):
        self()

    def __str__(self):
        return str(self._the_ones)

    def ask_n(self):
        """This function will ask a given amount of images"""
        print("I am now preparing to process the file. Please pass the file name on Commons and the nlwiki article "
              "below.")
        print('For devs or people who accidentally (re)started me: just type exit to stop the bot.')
        file = input("Please enter the name (NOT THE URL) of the file that should be processed. ").strip()
        if file.strip().lower() in {'exit', 'stop', 'quit'}:
            return None
        name = input("Please enter the corresponding name of the article on the Dutch Wikipedia. ").strip()
        if name.lower().startswith('file'):
            # This is a safeguard against possible errors
            print(
                '\nWARNING: You asked me to edit the page "FILE" - THIS SEEMS WEIRD TO ME - Please re-enter what you '
                'wished to enter\n')
            sleep(5)  # Give the user a 5 second time period to rethink their input
            name = input("Please enter the corresponding name of the article on the Dutch Wikipedia. ").strip()
        # try:
        _, _, confmes = Image(file, name)()  # Discard filename and short urls, the confirmation message will be printed
        #except:
        #    print('\nBOT ERROR! Please check output above\n')
        #    sleep(5)
        #    exit()
        self.print_confirmation_message(confmes)
        del name, file  # Remove these variables from memory, we don't need them any longer
        print(
            'I will now restart the cyle, simply close this window to stop. No computers will be harmed in due course.')
        return self.ask_n()

    def print_confirmation_message(self, message):
        "Prints the confirmation message in an accentuated way"
        assert isinstance(message, str), "Though shall provide a string as confirmation message!"
        print('-' * 10)  #Print a line to do some further accentuation
        print('\n')
        print(message)
        print('\n')  #Leave a further blank
        print('-' * 10)
        #A final newline is not required and inserted by the ask_n method

    def __call__(self):
        "This function is used to start the bot"
        print(
            'Welcome at WikiportraitBot! I will be your humble assistant on your quest to process images from Wikiportret')
        print('I will now prepare the first file for you!')
        return self.ask_n()  #Calls the method that does the processing


#Code used to run the bot
z = Interface()
