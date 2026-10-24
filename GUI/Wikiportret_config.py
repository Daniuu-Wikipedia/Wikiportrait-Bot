"""
Module that loads the configuration of the tool (the web app, the background jobs and the scripts)

Two sources, in this order:
1. config.toml next to this file (optional). Handy for local development and for settings that are not secret.
2. Environment variables starting with WPOR_ (on Toolforge: toolforge envvars). WPOR_<NAME> sets the setting <NAME>,
   e.g. WPOR_CONSUMER_SECRET sets CONSUMER_SECRET. An environment variable wins over config.toml.

Environment variables only hold text, so the settings in BOOLEAN_SETTINGS and INTEGER_SETTINGS are converted.
Toolforge only passes envvars to a webservice or job when it starts: restart them after changing an envvar.
"""

import os
import tomllib

ENV_PREFIX = 'WPOR_'
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.toml')

BOOLEAN_SETTINGS = {'SESSION_COOKIE_SECURE', 'SESSION_REFRESH_EACH_REQUEST', 'LOCAL_DEV'}
INTEGER_SETTINGS = {'ENC_KEY_CURRENT_VERSION', 'ENC_KEY_PREVIOUS_VERSION'}


def _convert(name, value):
    value = value.strip()  # A value piped into toolforge envvars create easily ends with a newline
    if name in BOOLEAN_SETTINGS:
        if value.lower() in {'1', 'true', 'yes'}:
            return True
        if value.lower() in {'0', 'false', 'no', ''}:
            return False
        raise ValueError(f'{ENV_PREFIX}{name} should be true or false, not {value!r}')
    if name in INTEGER_SETTINGS:
        return int(value)
    return value


def load_config():
    """The settings as a dict: config.toml (if it exists), overruled by the WPOR_ environment variables"""
    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'rb') as f:
            config.update(tomllib.load(f))
    for env_name, value in os.environ.items():
        if env_name.startswith(ENV_PREFIX) and len(env_name) > len(ENV_PREFIX):
            name = env_name[len(ENV_PREFIX):]
            config[name] = _convert(name, value)
    return config
