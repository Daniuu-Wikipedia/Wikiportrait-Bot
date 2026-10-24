# Script that will run continuously in the background of the webservice


import toolforge
import threading
import time
import os
import traceback
import Wikiportret_core_web_link as wcl  # Dealing with the db & getting info from the UI
import Wikiportret_db_utils as dbutil
import Wikiportret_config
from Wikiportret_core import ImageAlreadyError, MaxlagError

# First job: read config of the app
__dir__ = os.path.dirname(__file__)
config = Wikiportret_config.load_config()

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

# Message for the operator (stored after an upload, or provisionally when the upload hit maxlag)
MESSAGE_INSERT = """
INSERT INTO messages
(session_id, user_id, message, file_url, wiki_url, qid) values (%s, %s, %s, %s, %s, %s);"""


# The list of uploads of an operator (shown on the "Mijn uploads" page)
# Adds a file only if the operator does not have it in the list yet: a job can reach this point more than once (it is
# added when the job first hits maxlag, and again by the retries), and a file can only be uploaded to Commons once
UPLOAD_INSERT = """
INSERT INTO user_uploads (operator_id, file_uploaded)
SELECT %s, %s FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM user_uploads WHERE operator_id = %s AND file_uploaded = %s);"""


def add_to_uploads(config, conn, user_id, file):
    """Adds the file to the list of uploads of the operator (once, however often this is called)"""
    dbutil.adjust_db(UPLOAD_INSERT, config['DB_NAME'], connection=conn, params=(user_id, file, user_id, file))


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
    bot, failure = None, None  # failure: the error that stopped the loading (shown to the operator on /review)
    try:
        bot = wcl.create_from_db(session_id,
                                 config,
                                 retrieve_claims=False,
                                 adjust_input_data=False,
                                 check_status=False,
                                 any_user=True)  # We still need to write stuff to the db, so silent
        bot.prepare_image_data()  # Load stuff in the background
        bot.get_commons_claims()
        bot.ini_wikidata()
        # We need to clearly communicate with the db !!!
        bot.write_to_db(session_id, conn)
        bot.input_data_to_db(session_id, conn)
        success = True
    except MaxlagError:
        # Wikidata is overloaded: the session still ends up 'failed', but this is no error of the job, so it is not
        # stored in error_log (failure stays None)
        print(f'Session {session_id}: maxlag while loading the data')
    except Exception as error:  # E.g. a ProcessingError of the core: a typo in the name of the file, ...
        failure = error
        traceback.print_exc()
    finally:
        status = 'completed' if success else 'failed'
        dbutil.adjust_db(
            "UPDATE sessions SET locked = 0, locked_at = NULL, status = %s WHERE session_id=%s",
            config['DB_NAME'],
            connection=conn,
            params=(status, session_id))
        log_errors(session_id, config, conn, bot, failure)
        conn.close()
        print(f'SUCCESS in getting data & writing db stuff for {session_id:d}')


def log_errors(session_id, config, conn, bot, failure):
    """Stores the warnings of the job & the error that stopped it (if any) in error_log, for the operator"""
    if bot is not None:
        bot.log_errors(session_id, failure, conn)
    elif failure is not None:  # The job could not even be loaded from the db (so no file & page to log either)
        dbutil.log_errors([(500, repr(failure))], config['DB_NAME'], session_id, connection=conn)


def log_failed_bot_job(session_id, config, conn, bot_credentials):
    """Lists a failed job of the bot account on the wiki. Logging must never get in the way: errors are only printed"""
    try:
        row = dbutil.query_db("SELECT page, file, signature FROM sessions WHERE session_id=%s",
                              config['DB_NAME'], connection=conn, params=(session_id,))
        wcl.log_failed_job(bot_credentials, session_id, *row)
    except Exception as error:  # Includes MaxlagError: the job itself is already marked as failed in the db
        print(f'Could not log failed job {session_id}: {error!r}')


# Codes of ImageAlreadyError (Wikiportret_core.ERROR_MESSAGES): the image itself / another image was in the article
IMAGE_ALREADY_CODES = (201, 202)


def article_was_skipped(session_id, config, conn):
    """
    True if an earlier attempt of this job found an image in the article (201/202 in error_log). A retry after maxlag
    skips the article step, so it can not see that by itself: without this check, the job would end as 'uploaded'
    """
    return any(code in IMAGE_ALREADY_CODES for code, _ in dbutil.get_errors(session_id, config['DB_NAME'], connection=conn))


def upload_in_background(session_id, config, user_id, from_maxlag=False, bot_credentials=None):
    """
    Processes a submitted session (status 'ready'), or retries one that was postponed (status 'maxlag').

    Who makes the edits (only Wikidata can trigger maxlag, see the two phases in Image.__call__):
        * First attempt (from_maxlag=False): the operator, with their own tokens, runs both phases. The operator
          steps (everything on the Dutch Wikipedia and Commons, except the category) need no Wikidata call, so
          they are never postponed.
        * Retry (from_maxlag=True, called by Wikiportret_maxlag_handler): only the Wikidata steps (the Wikidata
          edits and creating & adding the category on Commons) are still open. They are made by the operator if
          their tokens are still stored, otherwise by the bot account (bot_credentials, see
          WebImage.acting_as_bot), which can not edit the Dutch Wikipedia.
    """
    # 20260406 - extended to also store short urls in the messages db
    # 20260926 - extend possible statusses in db: also allow for "althere" and "maxlag", depending on error
    success, status = False, 'ufail'  # By default, assume that Daniuu is crap at coding & the bot fails
    conn, bot = toolforge.toolsdb(config['DB_NAME']), None
    failure = None  # The error that stopped the job (shown to the operator on /statussubmit)
    outsourced = False  # True if the bot account (instead of the operator) is doing this job
    try:
        bot = wcl.create_from_db(session_id, config, user=user_id, bot_credentials=bot_credentials)
        outsourced = bot.acting_as_bot
        # First attempt: both phases (operator steps on Commons & nlwiki, then the Wikidata steps)
        # Retry after maxlag: only the Wikidata steps, the operator steps were completed during the first attempt
        _, shorts, confirmation = bot(conf=False,  # Print confirmation to the terminal (not used in webservice)
                                      test=False,  # Make the actual calls to the API
                                      operator_steps=not from_maxlag)
        # 20260313 - HACKATHON - improve logging
        if not isinstance(session_id, int):
            status = 'sessioniderror'
        if bot.already_there is not None or (from_maxlag and article_was_skipped(session_id, config, conn)):
            # The image was already in the article (201) or the infobox had another one (202): the article was not
            # edited, but all other steps were made (so the upload counts as success, see below)
            # Retry after maxlag: the first attempt found it (and logged it, see the MaxlagError branch)
            status = 'althere'
            # Logged with the warnings: /uploadexists reads it to tell the operator which of the two it was
            # (on a retry it is logged already, and this attempt did not find it itself)
            if bot.already_there is not None:
                bot.warnings.append(bot.already_there)
        success = True  # Flag upload as success
        # Also store the upload messages => to make life easier for the operator
        # Replace the provisional message that was stored when a previous attempt hit maxlag
        dbutil.adjust_db("DELETE FROM messages WHERE session_id = %s;", config['DB_NAME'],
                         connection=conn, params=(session_id,))
        dbutil.adjust_db(MESSAGE_INSERT, config['DB_NAME'], connection=conn,
                         params=(session_id, user_id, confirmation, shorts[0], shorts[1], bot.qid))
        # 20260409 - explicitly set uploaded status in time
        # 'althere' right away as well: an intermediate 'uploaded' would send the operator to the wrong page
        query = """
                UPDATE sessions
                SET status = %s where session_id = %s;
                """
        dbutil.adjust_db(query, config['DB_NAME'], connection=conn,
                         params=('althere' if status == 'althere' else 'uploaded', session_id))
        # 20250314 - HACKATHON - succesfull upload => add to the list of user uploads in the db
        # A retry after maxlag may have been added to the list already (see below): add_to_uploads never adds twice
        add_to_uploads(config, conn, user_id, bot.file)
    except wcl.UnverifiedTargetError as error:
        # 20261024 - the bot account refuses jobs that the wikis do not confirm: leave them for manual review
        print(f'Session {session_id}: {error}')
        status = 'ufail'
        failure = error
        outsourced = True  # Only raised for jobs of the bot account (raised while the object was being built)
    except ImageAlreadyError as error:
        # 20260926 - separate handling of attempts to overwrite existing files
        # 20260929 - watch out for runs that previously came from maxlag
        # Assumption: operator previously inserted the image manually into the article
        # 20261024 - always 'althere' (writing True stored enum index 1 = 'pending' & restarted the whole session)
        status = 'althere'
        # Code 201 (image already in the article) or 202 (the infobox has another image): the status says it all,
        # so the error is deliberately not stored in error_log (failure stays None; warnings are still logged)
        print(f'Session {session_id}: {error}')

    except MaxlagError:
        # 20260926 - separate handling of maxlag errors
        # 20261005 - continue running, query will confirm the status later (but force unlocking anyway)
        status = 'maxlag'
        # 20261024 - a session can hit maxlag more than once: keep the message stored at the first maxlag
        # (session_id is the primary key of messages, so a second insert would fail)
        has_message = dbutil.query_db("SELECT 1 FROM messages WHERE session_id = %s;", config['DB_NAME'],
                                      connection=conn, params=(session_id,)) is not None
        if bot is not None:
            # The image is on Commons and in the article already: it counts as an upload of the operator now
            # (first, so that a failing step below cannot skip it; repeating it in a later maxlag round is harmless)
            add_to_uploads(config, conn, user_id, bot.file)
        if bot is not None and bot.already_there is not None:
            # Logged now, so the retry (which skips the article step) still ends as 'althere' (article_was_skipped)
            bot.warnings.append(bot.already_there)
        if bot is not None and not has_message:
            # Store the message for the operator already (maxlag only affects Wikidata, so shortening urls is safe)
            shorts = bot.short_urls()
            dbutil.adjust_db(MESSAGE_INSERT, config['DB_NAME'], connection=conn,
                             params=(session_id, user_id, bot.generate_confirmation(shorts),
                                     shorts[0], shorts[1], bot.qid))
    except Exception as error:  # E.g. a ProcessingError of the core: the job stays 'ufail', the error is logged below
        failure = error
        traceback.print_exc()
    finally:
        if success is True and status != 'althere':
            status = 'uploaded'
        query = """
        UPDATE sessions
        SET status = %s, locked = 0, locked_at = NULL
        WHERE session_id = %s"""
        dbutil.adjust_db(query, config['DB_NAME'], connection=conn, params=(status, session_id))
        log_errors(session_id, config, conn, bot, failure)  # Also the warnings of a job that did work out
        # 20261024 - jobs of the bot account that did not work out (and are not simply waiting for a retry)
        # are listed on the wiki, so that someone can pick them up manually
        if outsourced and status not in ('uploaded', 'althere', 'maxlag'):
            log_failed_bot_job(session_id, config, conn, bot_credentials)
        if bot is not None:  # 20260314 - HACKATHON: fix bug that caused categories to be added > 1 time
            # Store the claims that the bot works with (set_image updates them). They are not requested from Wikidata
            # again: that read could raise MaxlagError here and would skip the rest of this cleanup
            bot.write_to_db(session_id, conn)
            bot.input_data_to_db(session_id, conn)
        conn.close()


# 20261010 - protection to allow importing this script without entering a perpetual loop
if __name__ == '__main__':
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
                """ % i[0]
                dbutil.adjust_db(update_query, config['DB_NAME'], connection=connection)
                threading.Thread(target=upload_in_background,
                                 args=(i[0],
                                       config,
                                       i[1])).start()

            time.sleep(1)  # Do sampling stuff at a frequency of 1 Hz (ok, slightly less)
    finally:
        connection.close()  # Close the connection and shutdown everything

    # And what to do in the end (we'll just use a finally-construct for this purpose)
