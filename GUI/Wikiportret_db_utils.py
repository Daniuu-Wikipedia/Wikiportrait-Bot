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
        if "SELECT status FROM sessions" in query:
            return ("uploaded",)
        if "SELECT * FROM messages" in query:
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


def get_user_id(username, dbname, connection=None):
    if LOCAL_DEV:
        return 1
    if isinstance(username, int):
        return username  # To avoid getting into trouble again with me messing up usernames & ids again
    data = query_db("SELECT `user_id` from `users` where `username`=%s",
                    dbname,
                    need_all=False,
                    connection=connection,
                    params=(username,))
    if isinstance(data, tuple):
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
        cursor.execute(query, params)
        connection.commit()
        if retrieve_id is True:
            new_row_id = cursor.lastrowid
        cursor.close()
    if connection_passed is False:
        connection.close()  # Keep connection alive if passed externally
    return new_row_id if retrieve_id is True else True  # Just to indicate that everything worked out fine


def get_tokens_from_db(dbname, operator_name, connection=None):  # To do: extend with encryption stuff
    if not isinstance(operator_name, (str, int)):
        raise TypeError('operator_name must be str or int!')
    query = "select * from tokens where operator_id=%s;"
    coded = json.loads(query_db(query, dbname, connection=connection,
                                params=(get_user_id(operator_name, dbname, connection),))[1])  # Automatically

    # 20260314 - HACKATHON - decrypt tokens
    # Encrypted stuff is stored in the db (so we need to get some stuff stored in the same table)
    sec = {}
    for i, j in coded.items():
        query = "select * from secret_stuff where `ciphertext`=%s"
        obtained = query_db(query, dbname, connection=connection, params=(j,))
        sec[i] = crypto.decrypt_token(j, obtained[2], obtained[3])
        del obtained, query  # No longer needed
    return sec  # Be careful with this dictionary!
