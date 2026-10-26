#!/bin/bash

# Image of the jobs: must be the same Python version as the webservice and the venv (~/www/python/venv)
# Startup.sh passes its own PYTHON_IMAGE, so both always match; on its own, this script uses the default below
# Switching versions: rebuild the venv first (webservice-python-bootstrap --fresh in a shell of the new image), and
# delete the running jobs (toolforge jobs delete background / maxlaghandler) before starting them again
PYTHON_IMAGE=${PYTHON_IMAGE:-python3.11}
# Python 3.13 (same switch as in Startup.sh): PYTHON_IMAGE=${PYTHON_IMAGE:-python3.13}

# Run background job key to loading and uploading
toolforge jobs run background --command "./www/python/venv/bin/python3 ./www/python/src/Wikiportret_background.py" --image $PYTHON_IMAGE --continuous
# Key rotation (Wikiportret_key_regen.py) is not a job: it needs the toolforge command, run it from the bastion

# Addition: deal with maxlagged images
toolforge jobs run maxlaghandler --command "./www/python/venv/bin/python3 ./www/python/src/Wikiportret_maxlag_handler.py" --image $PYTHON_IMAGE --schedule "*/5 * * * *"
