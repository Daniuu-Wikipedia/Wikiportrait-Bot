# -*- coding: utf-8 -*-
"""
Created on Wed May  5 18:28:28 2021

@author: Daniuu

This script will convert the Python code into an executable
"""
import PyInstaller.__main__

PyInstaller.__main__.run([
    'Wikiportret_CMD_interface.py',
    '--onefile',
    '--console',
    '--clean'
    #Console for I/O is required
])
