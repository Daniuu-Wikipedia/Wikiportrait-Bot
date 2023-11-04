# File to copy all files from the Github repo into the proper directory at Toolfore
cd ~/Wikiportrait-Bot/GUI

# Copy the new Python files to the usual directory
cp *.py ~/www/python/src

# Copy templates into new file
cp -r templates ~/www/python/src/

# Copy all static stuff to their proper Toolforge destination
cp -r static ~/www/python/src/

# Copy the novel versions of the shell scripts to our home folder
cp -r Shell_scripts ~/Shell

# Get rid of some obsolete files in the webservice's directory
cd ~/www/python/src
rm Wikiportret_CMD_interface.py  # File solely for local use
rm Installer_Wikiportraitbot.py  # Nobody should run this one from Toolforge
rm -r __pycache__  # Remove any obsolete Python cache

# Restart the webservice
# webservice --backend=kubernetes python3.11 restart
