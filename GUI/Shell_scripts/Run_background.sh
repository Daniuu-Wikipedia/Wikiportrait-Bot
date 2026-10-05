#!/bin/bash

# Run background job key to loading and uploading
toolforge jobs run background --command "./www/python/venv/bin/python3.11 ./www/python/src/Wikiportret_background.py" --image python3.11 --continuous
# Problem with script, solve later
#toolforge jobs run regenkey --command "./www/python/venv/bin/python3.11 ./www/python/src/Wikiportret_key_regen.py" --image python3.11 --schedule "* * 1 */3 *"

# Addition: deal with maxlagged images
toolforge jobs run maxlaghandler --command "./www/python/venv/bin/python3.11 ./www/python/src/Wikiportret_background.py" --image python3.11 --schedule "*/5 * * * *"