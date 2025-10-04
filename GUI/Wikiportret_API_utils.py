"""
Module that contains all functionalities to communicate with the Wikiportret API
"""

import requests
import tomllib
import os


def generate_wikiportret_key():
    with open(os.path.join(os.path.dirname(__file__), 'config.toml'), 'rb') as f:
        data = tomllib.load(f)
    payload = {'User': data['WIKIPORTRET_USERNAME'],
               'Pass': data['WIKIPORTRET_PASS'],
               'Authentication': data['WIKIPORTRET_API_KEY']}
    response = requests.post('https://wikiportret.nl/api/login/',
                             headers=payload).text
    # Note: API end is written in PHP, so it returns a bytestring
    #
    return f'Bearer {response}'


def pull_data(key='2ebec06c3dbbcec2493e859c3799308f65e6624d'):
    with open(os.path.join(os.path.dirname(__file__), 'config.toml'), 'rb') as f:
        data = tomllib.load(f)
    payload = {'User': data['WIKIPORTRET_USERNAME'],
               'Authentication': generate_wikiportret_key()}
    data = {'key': key}
    print(requests.post('https://www.wikiportret.nl/api/ticket/',
                        data=data,
                        headers=payload).text)
