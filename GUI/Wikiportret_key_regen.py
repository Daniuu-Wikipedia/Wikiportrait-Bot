import base64
import secrets
import json
import tomllib


# To do: produce a 32-byte (256 bits, golden standard right now) encryption key
with open('config.toml', 'rb') as f:
    config = tomllib.load(f)
with open(config['SECRET_KEY_LOC'], 'r') as f:
    json_data = json.load(f)

# Delete the old key
# We will perform some rotations
del json_data[f'KEY_{json_data["PREV_KEY"]}']

json_data['PREV_KEY'] = json_data['CURR_KEY']  # Could also be just +1
json_data['CURR_KEY'] += 1

# Generate a new key
json_data[f'KEY_{json_data["CURR_KEY"]}'] = base64.b64encode(secrets.token_bytes(32)).decode()

with open(config['SECRET_KEY_LOC'], 'w') as f:
    json.dump(json_data, f, indent=4)
