"""
Signatures for jobs that the bot account may finish on behalf of an operator.

WHY
---
When the Wikidata API is overloaded, jobs are parked (status 'maxlag') and later finished by the maxlag handler,
possibly long after the operator logged out. If the operator's own tokens are gone, the handler falls back to the
bot account, which has more rights than a regular operator and edits under its own name.
Only Wikidata can cause maxlag, so the bot account is only meant to finish what Wikidata held up: the Wikidata edits
and the creation & addition of the category on Commons. The edits on the Dutch Wikipedia and the other Commons edits
are always made by the operator, during the first attempt.

Everything that steers that fallback lives in the database (page, file, wikidata item, caption, ...). Anybody who can
write to the database (SQL injection, a leaked db password, a rogue tool on the same server) could therefore make
the bot account edit arbitrary things: it would simply trust the rows. The live checks against the wikis (see
WebImage.verify_bot_target) confirm that the page and file exist and that the file is a Wikiportret upload, but they
cannot tell whether the *content* (caption, category, summary, wikidata item) is what the operator approved.

HOW
---
When the operator submits the job (/submit), the web app computes an HMAC-SHA256 over the fields that were just
reviewed and stores it in sessions.signature. The key (JOB_SIGNING_KEY in config.toml) is NOT in the database, so
somebody who only controls the database cannot produce a matching signature. Before the bot account is used, the
fields are read from the database again and the signature is recomputed; any difference means "tampered with, or
never approved by an operator" and the bot refuses to edit.

* The fields are serialised as JSON with sorted keys and fixed separators. Plain concatenation would be ambiguous
  ("ab"+"c" equals "a"+"bc"), JSON is not. The 'purpose' entry makes sure that a signature made here can never be
  confused with a MAC that is used for another purpose with the same key.
* The session id and the operator id are part of the signed data, so a valid signature cannot be copied to another
  row, or to another operator.
* Only fields that stay constant after submission are signed: the dates in input_data are NOT included because the
  background job (re)writes them with derived values after the first attempt, which would invalidate the signature
  on every retry. Wikidata/Commons claims are not signed for the same reason (they are refreshed after each attempt).
  The wikidata item (qid) and Commons id (mid), which decide where the bot edits, are signed.
* Comparison happens with hmac.compare_digest (constant time), never with ==.

WHAT THIS DOES NOT PROTECT AGAINST
----------------------------------
Anybody who can read config.toml can forge signatures; the key must be readable by the tool only (chmod 600), and
must not be reused as an encryption key. The signature proves "an operator approved exactly this", not that the
operator is still allowed to do so: the user screening happens up front, at submission.

SETUP
-----
1. Generate a key:  python -c "import secrets; print(secrets.token_hex(32))"
   and put it in config.toml as  JOB_SIGNING_KEY = "<the key>".
2. Add the column once:  ALTER TABLE `sessions` ADD COLUMN `signature` CHAR(64) NULL DEFAULT NULL;
Without a key no signature is made, and the bot fallback refuses every job (it fails closed).
"""

import hashlib
import hmac
import json

PURPOSE = 'wikiportret-job-v1'  # Bump the version if the signed fields ever change
MIN_KEY_LENGTH = 32  # Characters; token_hex(32) gives 64


def _key(config):
    """The signing key from the config as bytes, or None if it is missing or obviously too weak."""
    key = config.get('JOB_SIGNING_KEY')
    if not isinstance(key, str) or len(key) < MIN_KEY_LENGTH:
        return None
    return key.encode('utf8')


def _canonical(fields):
    """Unambiguous byte representation of the signed fields (see the module docstring for why JSON)."""
    data = {'purpose': PURPOSE,
            'session_id': int(fields['session_id']),
            'operator_id': int(fields['operator_id'])}
    for name in ('page', 'file', 'qid', 'mid', 'caption', 'category', 'summary'):
        value = fields[name]
        data[name] = None if value is None else str(value)
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def sign_job(config, **fields):
    """Hex HMAC-SHA256 of the job fields (see WebImage.job_fields), or None if no key is configured."""
    key = _key(config)
    if key is None:
        return None
    return hmac.new(key, _canonical(fields), hashlib.sha256).hexdigest()


def verify_job(config, signature, **fields):
    """True only if a key is configured and the stored signature matches the fields. Fails closed otherwise."""
    expected = sign_job(config, **fields)
    if expected is None or not isinstance(signature, str):
        return False
    return hmac.compare_digest(expected, signature)
