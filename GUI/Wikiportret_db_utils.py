"""
Module containing some handy auxiliary functions for communicating with the database behind the bot.
Note: Database is hosted on Toolforge (MariaDB)

Auxliary functions are listed separately to keep the code of the main app clean
"""

import toolforge
import json


def query_db(query, dbname, need_all=False, connection=None):
    """
    Query information from the database.
    (details on arguments & output to be added)
    """
    if not isinstance(query, str):
        return None
    connection_passed = connection is not None
    if connection is None:
        connection = toolforge.toolsdb(dbname)
    with connection.cursor() as cursor:
        cursor.execute(query)
        if need_all is True:
            info = cursor.fetchall()
        else:
            info = cursor.fetchone()
        cursor.close()
    if connection_passed is False:  # Obviously, we want to keep our connection alive if it is provided
        connection.close()
    return info  # Return the relevant info & process it elsewhere


def get_user_id(username, dbname, connection=None):
    data = query_db(f"SELECT `user_id` from `users` where `username`='{username}'",
                    dbname,
                    need_all=False,
                    connection=connection)  # '' are required to get a proper query
    if isinstance(data, tuple):
        return data[0]
    return None  # No valid user


def adjust_db(query, dbname, retrieve_id=False, connection=None):
    if not isinstance(query, str):
        return None
    connection_passed = connection is not None
    if connection is None:
        connection = toolforge.toolsdb(dbname)
    with connection.cursor() as cursor:
        cursor.execute(query)
        connection.commit()
        if retrieve_id is True:
            new_row_id = cursor.lastrowid
        cursor.close()
    if connection_passed is False:
        connection.close()  # Keep connection alive if passed externally
    return new_row_id if retrieve_id is True else True  # Just to indicate that everything worked out fine


def get_tokens_from_db(dbname, operator_name, connection=None):
    if isinstance(operator_name, str):
        query = f"""
        select * from tokens where operator_id={get_user_id(operator_name, dbname)};
        """
    elif isinstance(operator_name, int):
        query = f"""
                select * from tokens where operator_id={operator_name};
                """
    else:
        raise TypeError('operator_name must be str or int!')
    return json.loads(query_db(query, dbname, connection=connection)[1])  # Automatically
