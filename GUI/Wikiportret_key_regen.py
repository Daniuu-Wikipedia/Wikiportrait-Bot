"""
Rotates the encryption key of the tool (AES-GCM, 32 bytes = 256 bits), stored in Toolforge envvars

    WPOR_ENC_KEY_CURRENT          the key new secrets are encrypted with (base64)
    WPOR_ENC_KEY_CURRENT_VERSION  its number, stored with every secret in secret_stuff.version
    WPOR_ENC_KEY_PREVIOUS         the key before that: still needed to decrypt what was encrypted before the rotation
    WPOR_ENC_KEY_PREVIOUS_VERSION its number

One rotation: the current key becomes the previous one, a new key with the next number becomes the current one, and
the oldest key is gone (whatever was still encrypted with it can not be decrypted anymore). Version numbers only go
up: a number that was used before must never point to another key.
Running processes only see envvars from when they started, so the webservice and the background job are restarted
afterwards (the maxlag handler starts fresh every 5 minutes, it needs no restart).

Run as the tool account where the toolforge command is available (on the bastion: become <tool> first):
    python3 Wikiportret_key_regen.py                        rotate & restart
    python3 Wikiportret_key_regen.py --no-restart           rotate only (restart yourself later)
    python3 Wikiportret_key_regen.py --import-json FILE     one-off migration: copy the keys of the old json file
                                                            (SECRET_KEY_LOC) into the envvars, no rotation
Key values are passed to toolforge through stdin, never as command line arguments (those are visible to other users
of the bastion and end up in the shell history).
"""

import argparse
import base64
import json
import secrets
import shutil
import subprocess
import sys

PREFIX = 'WPOR_ENC_KEY_'
BACKGROUND_JOB = 'background'  # Name of the continuous job, see Shell_scripts/Run_background.sh


def run(*command, value=None):
    """Runs a command (value goes to stdin) and returns its output; stops the script if it fails"""
    result = subprocess.run(command, input=value, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f'{" ".join(command)} failed: {result.stderr.strip()}')
    return result.stdout


def get_envvar(name):
    """The value of an envvar of the tool, or None if it does not exist"""
    result = subprocess.run(['toolforge', 'envvars', 'show', name, '--raw'], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def set_envvar(name, value):
    run('toolforge', 'envvars', 'create', name, value=str(value))  # No trailing newline: the value is exactly this


def new_key():
    return base64.b64encode(secrets.token_bytes(32)).decode('ascii')


def import_json(path):
    with open(path, 'r') as f:
        json_data = json.load(f)
    set_envvar(PREFIX + 'PREVIOUS', json_data[f'KEY_{json_data["PREV_KEY"]}'])
    set_envvar(PREFIX + 'PREVIOUS_VERSION', json_data['PREV_KEY'])
    set_envvar(PREFIX + 'CURRENT', json_data[f'KEY_{json_data["CURR_KEY"]}'])
    set_envvar(PREFIX + 'CURRENT_VERSION', json_data['CURR_KEY'])
    print(f'Imported key versions {json_data["PREV_KEY"]} (previous) and {json_data["CURR_KEY"]} (current)')


def rotate():
    current, version = get_envvar(PREFIX + 'CURRENT'), get_envvar(PREFIX + 'CURRENT_VERSION')
    if current is None or version is None:
        # Very first key: nothing to keep. Never silently start over when only one of the two is missing
        if current is not None or version is not None or get_envvar(PREFIX + 'PREVIOUS') is not None:
            sys.exit(f'{PREFIX}CURRENT and {PREFIX}CURRENT_VERSION are incomplete: fix them by hand first')
        set_envvar(PREFIX + 'CURRENT', new_key())
        set_envvar(PREFIX + 'CURRENT_VERSION', 0)
        print('Created the first key (version 0)')
        return
    version = int(version)
    # Order matters: if the script stops halfway, the old current key is already safe as the previous key
    set_envvar(PREFIX + 'PREVIOUS', current)
    set_envvar(PREFIX + 'PREVIOUS_VERSION', version)
    set_envvar(PREFIX + 'CURRENT', new_key())
    set_envvar(PREFIX + 'CURRENT_VERSION', version + 1)
    print(f'Rotated: version {version} is now the previous key, version {version + 1} the current one')


def restart():
    run('webservice', 'restart')
    run('toolforge', 'jobs', 'restart', BACKGROUND_JOB)
    print('Restarted the webservice and the background job')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Rotates the encryption key in the Toolforge envvars')
    parser.add_argument('--import-json', metavar='FILE', help='copy the keys from the old json key file, no rotation')
    parser.add_argument('--no-restart', action='store_true', help='do not restart the webservice & background job')
    args = parser.parse_args()

    if shutil.which('toolforge') is None:
        sys.exit('The toolforge command is not available here: run this as the tool on the Toolforge bastion')
    if args.import_json:
        import_json(args.import_json)
    else:
        rotate()
    if not args.no_restart:
        restart()
