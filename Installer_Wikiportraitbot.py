# -*- coding: utf-8 -*-
"""
Created on Wed May  5 18:28:28 2021

@author: Daniuu

This script will convert the Python code into an executable
"""
import PyInstaller.__main__
import ssl
import os
import sys

# Locate OpenSSL libs dynamically (example for Linux/Mac)
libssl_path = ssl._ssl.__file__  # Path to _ssl.so
lib_dir = os.path.dirname(libssl_path)


PyInstaller.__main__.run([
    'Wikiportret_CMD_interface.py',
    '--onefile',
    '--console',
    f'--add-binary={os.path.join(lib_dir, "libssl.so.1.1")}{os.pathsep}.',
    f'--add-binary={os.path.join(lib_dir, "libcrypto.so.1.1")}{os.pathsep}.',
    '--clean'
    #Console for I/O is required
])
