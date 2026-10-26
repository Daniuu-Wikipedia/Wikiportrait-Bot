#!/bin/bash
# Starts the whole tool from scratch: latest code, webservice and background jobs
# Run as the tool account on the bastion (become <tool> first). Works from both the repo and ~/Shell:
#     bash ~/Wikiportrait-Bot/GUI/Shell_scripts/Startup.sh     (very first time, before Copy.sh filled ~/Shell)
#     bash ~/Shell/Startup.sh                                  (afterwards)
# Prerequisites (not done here): the venv in ~/www/python/venv, built in a shell of the SAME image as below
# (toolforge webservice <image> shell, then webservice-python-bootstrap --fresh), and the WPOR_ envvars
# Nothing may be running yet: webservice start and toolforge jobs run both refuse what already exists

# The Python image of the webservice AND the jobs: they share the venv, so they must always be the same version
PYTHON_IMAGE=python3.11
# Python 3.13: rebuild the venv in a python3.13 shell first, then use this line instead of the one above
# PYTHON_IMAGE=python3.13
export PYTHON_IMAGE  # Read by Run_background.sh

cd "$(dirname "$0")"  # The other scripts are called by name: they sit in the same directory as this one

# 1. Get the latest code from GitHub & copy it into place (webservice directory, ~/Shell)
# Their exit codes are not checked: Copy.sh ends with removing files that are often not there (harmless)
bash Pull.sh
bash Copy.sh

# 2. Start the webservice (no point in starting the jobs if this does not work)
if ! webservice --backend=kubernetes $PYTHON_IMAGE start; then
    echo "The webservice did not start (already running? see: webservice status). Background jobs NOT started."
    exit 1
fi

# 3. Start the background jobs (continuous loading/uploading job & the maxlag handler)
bash Run_background.sh

echo "Started: webservice ($PYTHON_IMAGE) and background jobs. Check with: toolforge jobs list / webservice status"
