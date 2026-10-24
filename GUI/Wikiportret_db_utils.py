"""
Module containing some handy auxiliary functions for communicating with the database behind the bot.
Note: Database is hosted on Toolforge (MariaDB)

Auxliary functions are listed separately to keep the code of the main app clean
"""

import toolforge
import json
import Wikiportret_crypto as crypto
import tomllib
import os

# Load config for local dev check
__dir__ = os.path.dirname(__file__)
try:
    with open(os.path.join(__dir__, 'config.toml'), 'rb') as f:
        config = tomllib.load(f)
except:
    config = {}

LOCAL_DEV = config.get('LOCAL_DEV', False)


def query_db(query, dbname, need_all=False, connection=None, params=None):
    """
    Query information from the database.
    Values should be passed through params (with %s placeholders in the query), never formatted into the query,
    so pymysql escapes them (names like "Jeanne d'Arc" would otherwise break the query).
    """
    if LOCAL_DEV:
        if "SELECT s.status FROM sessions" in query:
            return ("uploaded",)
        if "SELECT m.* FROM messages" in query:
            return (0, 0, "Als je dit leest, zit je op de pagina /uploaddone ")
        if "SELECT `user_id`" in query:
            return (1,)
        return None

    if not isinstance(query, str):
        return None
    connection_passed = connection is not None
    if connection is None:
        connection = toolforge.toolsdb(dbname)
    connection.autocommit(True)
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        if need_all is True:
            info = cursor.fetchall()
        else:
            info = cursor.fetchone()
        cursor.close()
    if connection_passed is False:  # Obviously, we want to keep our connection alive if it is provided
        connection.close()
    return info  # Return the relevant info & process it elsewhere


def get_user_id(username, dbname, connection=None, cache=None):
    """
    Look up the id of a user. If a dict-like cache (e.g. the flask session) is passed, the id is read from and
    stored in it under 'user_id', so the db is only hit once per login.
    """
    if LOCAL_DEV:
        return 1
    if isinstance(username, int):
        return username  # To avoid getting into trouble again with me messing up usernames & ids again
    if cache is not None and cache.get('user_id') is not None:
        return cache['user_id']
    data = query_db("SELECT `user_id` from `users` where `username`=%s",
                    dbname,
                    need_all=False,
                    connection=connection,
                    params=(username,))
    if isinstance(data, tuple):
        if cache is not None:
            cache['user_id'] = data[0]
        return data[0]
    return None  # No valid user


def adjust_db(query, dbname, retrieve_id=False, connection=None, params=None):
    if LOCAL_DEV:
        return 1 if retrieve_id else True
    if not isinstance(query, str):
        return None
    connection_passed = connection is not None
    if connection is None:
        connection = toolforge.toolsdb(dbname)
    connection.autocommit(True)  # Force autocommit
    with connection.cursor() as cursor:
        cursor.execute(query, params)  # Autocommit is on, so no separate COMMIT round trip is needed
        if retrieve_id is True:
            new_row_id = cursor.lastrowid
        cursor.close()
    if connection_passed is False:
        connection.close()  # Keep connection alive if passed externally
    return new_row_id if retrieve_id is True else True  # Just to indicate that everything worked out fine


def get_tokens_from_db(dbname, operator_name, connection=None):  # To do: extend with encryption stuff
    if not isinstance(operator_name, (str, int)):
        raise TypeError('operator_name must be str or int!')
    # Ids are used directly; names are resolved in the same query through a join
    if isinstance(operator_name, int):
        query = "SELECT oauth_token FROM tokens WHERE operator_id=%s;"
    else:
        query = ("SELECT t.oauth_token FROM tokens t "
                 "JOIN users u ON u.user_id = t.operator_id "
                 "WHERE u.username=%s;")
    row = query_db(query, dbname, connection=connection, params=(operator_name,))
    if row is None:
        raise LookupError('No tokens stored for this user')
    coded = json.loads(row[0])

    # 20260314 - HACKATHON - decrypt tokens
    # Encrypted stuff is stored in the db (so we need to get some stuff stored in the same table)
    # All secrets are fetched in a single query
    if not coded:
        return {}
    placeholders = ', '.join(['%s'] * len(coded))
    query = f"SELECT ciphertext, nonce, version FROM secret_stuff WHERE ciphertext IN ({placeholders})"
    obtained = {row[0]: row for row in query_db(query, dbname, need_all=True, connection=connection,
                                                params=tuple(coded.values()))}
    sec = {}
    for i, j in coded.items():
        if j not in obtained:
            raise LookupError('Stored tokens are incomplete')
        _, nonce, version = obtained[j]
        sec[i] = crypto.decrypt_token(j, nonce, version)
    return sec  # Be careful with this dictionary!
