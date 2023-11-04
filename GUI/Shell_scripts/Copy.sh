# File to copy all files from the Github repo into the proper directory at Toolfore
cd ~/Wikiportrait-Bot/GUI

# Copy the new Python files to the usual directory
cp *.py ~/www/python/src

# Get rid of all cache in the source code folder
rm ~/www/python/src/*.pyc

# Copy templates into new file
cp -r templates ~/www/python/src/

# Copy all static stuff to their proper Toolforge destination
cp -r static ~/www/python/src/

# Copy the novel versions of the shell scripts to our home folder
cp -r Shell_scripts ~/Shell

# Restart the webservice
# webservice --backend=kubernetes python3.11 restart
