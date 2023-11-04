# File to copy all files from the Github repo into the proper directory at Toolfore
cd ~/Wikiportrait-Bot

# Copy the new Python files to the usual directory
cp *.py ~/www/python/src

# Get rid of all cache in the source code folder
rm ~/www/python/src/*.pyc

# Copy templates into new file
cp templates ~/www/python/src/

# Copy all static stuff to their proper Toolforge destination
cp static ~/www/python/src/

# Copy the novel versions of the shell scripts to our home folder
cp Shell_scripts ~/Shell

# Restart the webservice
webservice restart
