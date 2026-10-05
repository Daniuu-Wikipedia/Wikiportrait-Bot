"""
Module to deal with those images that were previously stalled due to (mostly) Wikidata maxlag-issues
"""


import toolforge
import os
import tomllib
import Wikiportret_db_utils as dbutil
import Wikiportret_background as bg
from Wikiportret_core import MaxlagError, ImageAlreadyError


# First job: read config of the app
__dir__ = os.path.dirname(__file__)
with open(os.path.join(__dir__, 'config.toml'), 'rb') as f:
    config = tomllib.load(f)

# Reset the user agent per Toolforge policy
toolforge.set_user_agent('Wikiportret-updater-bg',
                         email='wikiportret@wikimedia.org')  # Just setting up a custom user agent

# Second job: prepare a connection for the db
connection = toolforge.toolsdb(config['DB_NAME'])
connection.autocommit(True)

dbname = config['DB_NAME']

# Script is supposed to be connected to the internal database
query_select = """SELECT * from sessions where status='maxlag';"""

for i in dbutil.query_db(query_select, dbname, need_all=True, connection=connection):
    # Structure of sessions table
    # session, operator, page, file, status, created, locked, locked_at
    try:  # Try to restart the background processing - see whether it gets through this time
        # Status updates are dealt with in the background module
        bg.upload_in_background(i[0], config, i[1], True)
    except MaxlagError:
        # Stop the script
        # API is overloaded, no point in trying more
        break
    except ImageAlreadyError:
        # No need to throw an error, just logging is completely fine
        print(f'Image {i[2]!s} already uploaded to {i[3]!s}')

del i, config, dbname, query_select  # Delete variables that are no longer needed
connection.close()  # Close connection by default
