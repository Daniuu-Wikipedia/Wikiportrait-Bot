"""
Module to deal with those images that were previously stalled due to Wikidata maxlag-issues

Only Wikidata calls can trigger maxlag, so what is finished here is limited to the Wikidata edits and the creation &
addition of the category on Commons. Edits on the Dutch Wikipedia and the other Commons edits were made by the
operator during the first attempt, and are not made by this script.
Who makes the edits: the operator if their tokens are still stored, otherwise the bot account (bot_tokens below).
"""


import toolforge
import os
import sys
import Wikiportret_db_utils as dbutil
import Wikiportret_config
from Wikiportret_background import upload_in_background
from Wikiportret_core import MaxlagError, ImageAlreadyError


# First job: read config of the app
__dir__ = os.path.dirname(__file__)
config = Wikiportret_config.load_config()

# Reset the user agent per Toolforge policy
toolforge.set_user_agent('Wikiportret-updater-bg',
                         email='wikiportret@wikimedia.org')  # Just setting up a custom user agent

# Second job: prepare a connection for the db
connection = toolforge.toolsdb(config['DB_NAME'])
connection.autocommit(True)

dbname = config['DB_NAME']

# Guard against overlapping runs (the job is scheduled every 5 minutes, but a run may take longer, e.g. through the
# rate limits of the API). Two runs would pick up the same maxlagged sessions and make every edit twice.
# GET_LOCK is an advisory lock that belongs to this db connection: it is released the moment the connection ends,
# so a crashed or killed run can never leave a stale lock behind. Lock names are server-wide, hence the db name.
# The second argument (0) means: do not wait, just report whether the lock is taken.
lock_name = f'wikiportret_maxlag_handler_{dbname}'
got_lock = dbutil.query_db("SELECT GET_LOCK(%s, 0)", dbname, connection=connection, params=(lock_name,))
if got_lock is None or got_lock[0] != 1:  # 0: held by another run; NULL/None: could not be determined
    print('Another run of the maxlag handler is still busy (or the lock could not be taken): stopping')
    connection.close()
    sys.exit(0)

# OAuth tokens of the bot account: the 4 WPOR_BOT_* environment variables if they are set, otherwise the token file
# (same file & format as used by Wikiportret Core, owner-only readable)
BOT_TOKEN_SETTINGS = ('BOT_CONSUMER_TOKEN', 'BOT_CONSUMER_SECRET', 'BOT_ACCESS_TOKEN', 'BOT_ACCESS_SECRET')
if all(config.get(name) for name in BOT_TOKEN_SETTINGS):
    bot_tokens = tuple(config[name] for name in BOT_TOKEN_SETTINGS)
else:
    bot_tokens = os.path.join(__dir__, 'Tokens_Wikiportraitbot.txt')

# Script is supposed to be connected to the internal database
query_select = """SELECT * from sessions where status='maxlag';"""

# Not ideal, but printing debug statements is only working tool rn
print('Starting main loop')
for i in dbutil.query_db(query_select, dbname, need_all=True, connection=connection):
    print(i)
    # Structure of sessions table
    # session, operator, page, file, status, created, locked, locked_at
    try:  # Try to restart the background processing - see whether it gets through this time
        # Status updates are dealt with in the background module
        update_query = """
                    UPDATE sessions
                    SET locked = 1, locked_at = CURRENT_TIMESTAMP, status = 'up'
                    WHERE session_id = %d;
                    """ % i[0]
        print(update_query)
        dbutil.adjust_db(update_query, dbname, connection=connection)
        print(f'Processing maxlagged image {i[3]!r} to {i[2]!r}')
        # Edits are made by the operator, but their tokens may be gone by now (removed at logout):
        # then the bot account finishes the (Wikidata-dependent) rest of the job
        upload_in_background(i[0], config, i[1], True, bot_credentials=bot_tokens)
    except MaxlagError:
        # Stop the script
        # API is overloaded, no point in trying more
        break
    except ImageAlreadyError:
        # No need to throw an error, just logging is completely fine
        print(f'Image {i[3]!r} already uploaded to {i[2]!r}')

del config, dbname, query_select  # Delete variables that are no longer needed (not i: undefined if nothing to do)
dbutil.query_db("SELECT RELEASE_LOCK(%s)", None, connection=connection, params=(lock_name,))  # Closing also does it
connection.close()  # Close connection by default
print('DONE')
