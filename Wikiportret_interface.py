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
        jezeken = Image(file, name)()
        self._the_ones.append((jezeken[0],) + jezeken[-1]) #Call the processing function and store the url
        print('\n')
        print('Would you like to continue processing another image (y/n)? ')
        print('Entering n will terminate the program')
        a = input('Would you like to continue processing? [y/n] ').lower().strip()
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
    
    def ask_file(self):
        "Provides support for I/O to a file"
        print('The file should only contain rules in the format (file, title), and should be a .csv-like file.')
        try:
            file = input('Please provide the name of the csv-file that I should read. ').strip() #Strip immediately
            assert file.lower().endswith('.csv'), 'Please provide a .csv-file'
            print(f'Reading {file}')
            self.read_from_file(file)
        except AssertionError:
            print('Something went wrong, you did most likely not specify a .csv-file')
            return self.ask_file()
        except FileNotFoundError:
            print('That file does not exist! I will now ask you politely to provide a new file.')
            return self.ask_file()
        
        #Ask whether anything else is scheduled
        roger = input('Thanks for using WikiportraitBot. Do you want to process another file? [y/n] ')
        if roger.lower().strip() != 'y':
            return self.print_final()
        return self.ask_file()
        
    
    def read_from_file(self, file, delimiter=';'):
        with open(file, 'r') as datafile:
            lines = [i.strip().lower() for i in datafile]
        for i in lines:
            #Process the lines in the original file
            separated = [j.strip() for j in i.strip(delimiter)]
            im = Image(*separated)()
            self._the_ones.append((im[0],) + im[-1])
        print('Done reading from the file. I stop here. Thanks for using WikiportraitBot!')
        return self.print_final()
    
    def print_final(self):
        "This function will print the final output"
        order = [["\tTarget", "Url to Commons", "Url to nlwiki"]] #Adding an additional tab here, for better allignment
        for i in order + self._the_ones:
            print('\t\t\t'.join(i))
        
        print('\n')
        print('Thanks for using WikiportraitBot!')
        input('Press any key to close the program (after you copied the links). ')
            
    def __call__(self):
        return self.prompt_input()