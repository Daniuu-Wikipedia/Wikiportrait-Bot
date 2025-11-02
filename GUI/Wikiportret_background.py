# Script that will run continuously in the background of the webservice


import toolforge
import threading
import tomllib
import time
import os
import Wikiportret_core_web_link as wcl  # Dealing with the db & getting info from the UI
import Wikiportret_db_utils as dbutil

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

# Third job: compile a list of queries to be performed during each sample
queries = (  #"DELETE FROM tokens where timestamp < NOW() - INTERVAL 15 MINUTE;",
    "UPDATE sessions SET locked = 0, locked_at = NULL WHERE locked_at < NOW() - INTERVAL 1 MINUTE;")

# Fourth job: the query to run as a one-off (the one that triggers the loading of the info for the jobs)
background_trigger = "SELECT * FROM sessions WHERE locked = 0 AND status = 'pending';"

# Fifth job: upload the images that are ready
trigger_upload = "SELECT * FROM sessions WHERE status = 'ready';"


# Define some auxiliary methods
def background_load(session_id, config):
    """
    Method that allows reading a bot's claims in the background.
    Procedure: gets called through the background job...
        In the meantime, the web tool will be kept on hold for some time...
    """
    conn = toolforge.toolsdb(config['DB_NAME'])
    conn.autocommit(True)
    success = False  # By default, assume that Daniuu is crap at coding & the bot fails
    try:
        bot = wcl.create_from_db(session_id,
                                 config,
                                 retrieve_claims=False,
                                 adjust_input_data=False,
                                 check_status=False)  # We still need to write stuff to the db, so silent
        bot.prepare_image_data()  # Load stuff in the background
        bot.get_commons_claims()
        bot.ini_wikidata()
        # We need to clearly communicate with the db !!!
        bot.write_to_db(session_id, conn)
        bot.input_data_to_db(session_id, conn)
        success = True
    finally:
        status = 'completed' if success else 'failed'
        dbutil.adjust_db(
            "UPDATE sessions SET locked = 0, locked_at = NULL, status = '%s' WHERE session_id=%d" % (status,
                                                                                                     session_id),
            config['DB_NAME'],
            connection=conn)
        conn.close()
        print(f'SUCCESS in getting data & writing db stuff for {session_id:d}')


def upload_in_background(session_id, config, username):
    success = False  # By default, assume that Daniuu is crap at coding & the bot fails
    conn = toolforge.toolsdb(config['DB_NAME'])
    try:
        bot = wcl.create_from_db(session_id, config['DB_NAME'], config)
        _, _, confirmation = bot(True, True, True, True, True, False)  # Make the actual calls to the API
        query = """
        INSERT INTO messages
        (session_id, user_id, message) values (%d, %d, %r);""" % (session_id,
                                                                  dbutil.get_user_id(username,
                                                                                     config['DB_NAME'],
                                                                                     conn),
                                                                  confirmation)
        success = True
    finally:
        status = 'uploaded' if success else 'ufail'
        query = """
        UPDATE sessions
        SET status = %r, locked = 0, locked_at = NULL
        WHERE session_id = %d""" % (status, session_id)
        dbutil.adjust_db(query, config['DB_NAME'], connection=conn)
        conn.close()


# The actual continuous loop
try:
    while 1:
        connection.ping(reconnect=True)  # Avoid having this one open too long
        # To do: check if there are any locked jobs pending in the db
        # If so, launch a thread for each job to start dealing with the Wikidata stuff
        for i in dbutil.query_db(background_trigger,
                                 config['DB_NAME'],
                                 need_all=True,
                                 connection=connection):
            update_query = """
                        UPDATE sessions 
                        SET status = 'processing', locked = 1, locked_at = CURRENT_TIMESTAMP 
                        WHERE session_id=%d;""" % i[0]
            dbutil.adjust_db(update_query, config['DB_NAME'], connection=connection)
            threading.Thread(target=background_load,
                             args=(i[0],
                                   config)).start()  # Launch a background job

        for i in dbutil.query_db(trigger_upload,
                                 config['DB_NAME'],
                                 need_all=True,
                                 connection=connection):
            update_query = """
            UPDATE sessions
            SET locked = 1, locked_at = CURRENT_TIMESTAMP, status = 'up'
            WHERE session_id = %d;
            """
            dbutil.adjust_db(update_query, config['DB_NAME'], connection=connection)
            threading.Thread(target=upload_in_background,
                             args=(i[0], config, i[1])).start()

        time.sleep(1)  # Do sampling stuff at a frequency of 2 Hz (ok, slightly less)
finally:
    connection.close()  # Close the connection and shutdown everything

# And what to do in the end (we'll just use a finally-construct for this purpose)
