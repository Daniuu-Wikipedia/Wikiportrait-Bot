# 1 file does it all: use a single shell script to do all the updating work
bash Pull.sh
bash Copy.sh

# Restart the webservice
# webservice --backend=kubernetes python3.11 restart


# EOF
