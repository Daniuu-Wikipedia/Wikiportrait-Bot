# -*- coding: utf-8 -*-
"""
Created on Wed May  5 18:28:28 2021

@author: Daniuu

This script will convert the Python code into an executable
"""
import PyInstaller.__main__

PyInstaller.__main__.run([
    'Wikiportret_interface.py',
    '--onefile',
    '--console',
    '--clean'
    #r'--add-data <C:\Users\Student Daniel\Anaconda3\Lib\site-packages\pip\_vendor\certifi;cacert.pem>'
    #Console for I/O is required
])
