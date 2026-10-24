#!/bin/bash

# Run background job key to loading and uploading
toolforge jobs run background --command "./www/python/venv/bin/python3.11 ./www/python/src/Wikiportret_background.py" --image python3.11 --continuous
# Key rotation (Wikiportret_key_regen.py) is not a job: it needs the toolforge command, run it from the bastion

# Addition: deal with maxlagged images
toolforge jobs run maxlaghandler --command "./www/python/venv/bin/python3.11 ./www/python/src/Wikiportret_maxlag_handler.py" --image python3.11 --schedule "*/5 * * * *"