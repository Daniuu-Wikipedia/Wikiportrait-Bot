"""
Module containing some handy auxiliary functions for communicating with the database behind the bot.
Note: Database is hosted on Toolforge (MariaDB)

Auxliary functions are listed separately to keep the code of the main app clean
"""

import toolforge
import json
import Wikiportret_crypto as crypto
import Wikiportret_config
import os

# Load config for local dev check
__dir__ = os.path.dirname(__file__)
try:
    config = Wikiportret_config.load_config()
except Exception:
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
        if "FROM user_uploads" in query:
            import datetime as dt  # Real timestamps, like the db returns
            return [("VuilTestertje.jpg", dt.datetime(2026, 10, 24, 12, 0)),
                    ("Jan Jansen 2024.jpg", dt.datetime(2026, 9, 30, 9, 15)),
                    ("Oude upload.jpg", dt.datetime(2025, 1, 2, 10, 0))]
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


# Problems found while processing an image (codes: Wikiportret_core.ERROR_MESSAGES), one row per problem
# session_id is a foreign key with ON DELETE RESTRICT: a session cannot be deleted (directly, or through the cascade
# from users) as long as errors are logged for it. The type must be identical to sessions.session_id (int unsigned)
#
# CREATE TABLE `error_log` (
#   `error_id` int unsigned NOT NULL AUTO_INCREMENT,
#   `session_id` int unsigned DEFAULT NULL,
#   `file` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
#   `page` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
#   `qid` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
#   `error_code` smallint unsigned NOT NULL,
#   `details` text COLLATE utf8mb4_unicode_ci,
#   `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
#   PRIMARY KEY (`error_id`),
#   KEY `session_id` (`session_id`),
#   CONSTRAINT `error_log_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `sessions` (`session_id`)
#     ON DELETE RESTRICT ON UPDATE RESTRICT
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
ERROR_INSERT = """
INSERT INTO error_log (session_id, file, page, qid, error_code, details) VALUES (%s, %s, %s, %s, %s, %s)"""


def log_errors(errors, dbname, session_id, file=None, page=None, qid=None, connection=None):
    """
    Stores problems, given as (code, details) pairs, in error_log. Never raises: the logging must not get in the way
    of the job itself (the problems are printed by the core anyway).
    """
    for code, details in errors:
        try:
            adjust_db(ERROR_INSERT, dbname, connection=connection,
                      params=(session_id, file, page, qid, code, None if details is None else str(details)[:2000]))
        except Exception as error:
            print(f'Could not log error {code} of session {session_id}: {error!r}')


def get_errors(session_id, dbname, connection=None):
    """(code, details) of every problem logged for a session, oldest first"""
    return query_db("SELECT error_code, details FROM error_log WHERE session_id=%s ORDER BY error_id;", dbname,
                    need_all=True, connection=connection, params=(session_id,)) or ()


class TokensMissingError(LookupError):
    """
    The OAuth tokens of an operator are not (or no longer completely) in the db. The db removes them automatically
    after an hour, and at logout. The web app sends the user to the 'renew your login' page when this is raised.
    """


def has_tokens(operator_id, dbname, connection=None):
    """True if tokens are stored for this operator (cheap check, nothing is decrypted)"""
    if LOCAL_DEV:
        return True
    return query_db("SELECT 1 FROM tokens WHERE operator_id=%s;", dbname, connection=connection,
                    params=(operator_id,)) is not None


def store_secret(value, dbname, connection=None):
    """
    Encrypts value (fresh random nonce for every call, see Wikiportret_crypto) and stores it in secret_stuff.
    Returns the ciphertext: that is what other tables store to refer to the secret.
    """
    information = crypto.encrypt_token(value)
    adjust_db("INSERT INTO secret_stuff (ciphertext, nonce, version) VALUE (%s, %s, %s)", dbname,
              connection=connection, params=(information['ciphertext'], information['nonce'], information['version']))
    return information['ciphertext']


def get_stored_wikiportret_key(dbname, operator, connection=None):
    """
    The bare key for the Wikiportret API that is stored for an operator (user id or username), decrypted on the go.
    Only the key itself is encrypted in the db (tokens.wikiportrait_token holds its ciphertext, like oauth_token).
    Returns None if there is no (usable) key: no tokens, or a row from before the key was encrypted.
    Wikiportret_API_utils.get_wikiportret_key adds what is needed to get the key and to pass it to the API.
    """
    operator_id = get_user_id(operator, dbname, connection)
    row = query_db("SELECT wikiportrait_token FROM tokens WHERE operator_id=%s;", dbname, connection=connection,
                   params=(operator_id,))
    if row is None:
        return None
    secret = query_db("SELECT nonce, version FROM secret_stuff WHERE ciphertext=%s", dbname, connection=connection,
                      params=(row[0],))
    if secret is None:  # Nothing to decrypt with (e.g. a plain key from before the encryption was introduced)
        return None
    return crypto.decrypt_token(row[0], secret[0], secret[1])


def store_wikiportret_key(key, dbname, operator, connection=None):
    """
    Encrypts a bare Wikiportret key and links it to the tokens of the operator. Returns False if that is impossible
    because the operator has no tokens (anymore): tokens are only created at login (and removed at logout), and this
    function never creates or extends them.
    """
    operator_id = get_user_id(operator, dbname, connection)
    if query_db("SELECT 1 FROM tokens WHERE operator_id=%s;", dbname, connection=connection,
                params=(operator_id,)) is None:
        return False  # Do not even encrypt: that would only leave an orphan in secret_stuff
    adjust_db("UPDATE tokens SET wikiportrait_token=%s WHERE operator_id=%s;", dbname, connection=connection,
              params=(store_secret(key, dbname, connection), operator_id))
    return True


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
        raise TokensMissingError('No tokens stored for this user')
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
            raise TokensMissingError('Stored tokens are incomplete')
        _, nonce, version = obtained[j]
        sec[i] = crypto.decrypt_token(j, nonce, version)
    return sec  # Be careful with this dictionary!
