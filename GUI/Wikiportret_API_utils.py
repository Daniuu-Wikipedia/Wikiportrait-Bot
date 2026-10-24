"""
Module that contains all functionalities to communicate with the Wikiportret API

Import direction: this module imports Wikiportret_db_utils (to reuse and store keys), never the other way around.
Wikiportret_db_utils only knows about the database & encryption, so no import cycle is possible. Everything that
requests a key at the API or puts it in the form that the API expects lives here.
"""

import os
import tomllib

import requests

import Wikiportret_db_utils as db_utils

API_URL = 'https://www.wikiportret.nl/api'
TIMEOUT = 15  # Seconds: a hanging API must never freeze the web app or the background jobs

# Every call to the Wikiportret API passes the key as 'Bearer <key>'. The prefix is the same for everybody, so only
# the actual key is a secret (and only that part is encrypted in the db, see Wikiportret_db_utils)
BEARER_PREFIX = 'Bearer '

# Reference of an image (not a secret), used as the default example for pull_data
EXAMPLE_TICKET_KEY = '2ebec06c3dbbcec2493e859c3799308f65e6624d'


def _config():
    with open(os.path.join(os.path.dirname(__file__), 'config.toml'), 'rb') as f:
        return tomllib.load(f)


def add_bearer(key):
    """The value to pass to the Wikiportret API for a bare key"""
    return BEARER_PREFIX + key


def request_wikiportret_key():
    """
    Logs in at the Wikiportret API (with the account of the tool) and returns a new bare key, as it is stored in the db.
    Use get_wikiportret_key to get a key that can be passed to the API (reusing the stored one).
    """
    data = _config()
    headers = {'User': data['WIKIPORTRET_USERNAME'],
               'Pass': data['WIKIPORTRET_PASS'],
               'Authentication': data['WIKIPORTRET_API_KEY']}
    response = requests.post(f'{API_URL}/login/', headers=headers, timeout=TIMEOUT)
    response.raise_for_status()  # An error page must not end up in the db as if it were a key
    return response.text  # The API is written in PHP: the key is the plain body of the response


def generate_wikiportret_key():
    """A fresh key, ready to pass to the Wikiportret API ('Bearer <key>'). Not stored anywhere."""
    return add_bearer(request_wikiportret_key())


def get_wikiportret_key(dbname, operator, connection=None):
    """
    The key for the Wikiportret API of an operator (user id or username), ready to pass to the API ('Bearer <key>').

    * There is a key stored in the db: it is reused (and decrypted on the go).
    * There is none yet: a new one is requested and stored (encrypted) for the next time.
    * The operator has no tokens at all (not logged in): a new key is requested, but it cannot be stored.
    """
    key = db_utils.get_stored_wikiportret_key(dbname, operator, connection=connection)
    if key is None:
        key = request_wikiportret_key()
        db_utils.store_wikiportret_key(key, dbname, operator, connection=connection)
    return add_bearer(key)


def pull_data(dbname, operator, ticket_key=EXAMPLE_TICKET_KEY, connection=None):
    """
    Asks the Wikiportret API for the data of a ticket on behalf of an operator (user id or username) and returns the
    answer (text). The key of the operator is reused if it is in the db, otherwise it is created (get_wikiportret_key).
    """
    headers = {'User': _config()['WIKIPORTRET_USERNAME'],
               'Authentication': get_wikiportret_key(dbname, operator, connection=connection)}
    response = requests.post(f'{API_URL}/ticket/', data={'key': ticket_key}, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text
