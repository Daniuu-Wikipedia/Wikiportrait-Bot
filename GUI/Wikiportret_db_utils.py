"""
Module containing some handy auxiliary functions for communicating with the database behind the bot.
Note: Database is hosted on Toolforge (MariaDB)

Auxliary functions are listed separately to keep the code of the main app clean
"""

import toolforge
import tomllib
import os


def query_db(query, need_all=False):
    """
    Query information from the database.
    (details on arguments & output to be added)
    """
    if not isinstance(query, str):
        return None
    with open(os.path.join(os.path.dirname(__file__), 'config.toml'), 'rb') as f:
        data = tomllib.load(f)
    connection = toolforge.toolsdb(data['DB_NAME'])
    with connection.cursor() as cursor:
        cursor.execute(query)
        if need_all is True:
            info = cursor.fetchall()
        else:
            info = cursor.fetchone()
        cursor.close()
    connection.close()
    return info  # Return the relevant info & process it elsewhere


def get_user_id(username):
    data = query_db(f"SELECT `user_id` from `users` where `username`='{username}'",
                    need_all=False)  # '' are required to get a proper query
    if isinstance(data, tuple):
        return data[0]
    return None  # No valid user


def adjust_db(query, retrieve_id=False):
    if not isinstance(query, str):
        return None
    with open(os.path.join(os.path.dirname(__file__), 'config.toml'), 'rb') as f:
        data = tomllib.load(f)
    connection = toolforge.toolsdb(data['DB_NAME'])
    with connection.cursor() as cursor:
        cursor.execute(query)
        connection.commit()
        if retrieve_id is True:
            new_row_id = cursor.lastrowid
        cursor.close()
    connection.close()
    return new_row_id if retrieve_id is True else True  # Just to indicate that everything worked out fine
