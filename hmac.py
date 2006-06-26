"""HMAC -- keyed hashing for message authentication, as described in rfc2104."""

import sha

BLEN = 64
ipad = map(ord, "\x36" * BLEN)
opad = map(ord, "\x5C" * BLEN)

def hash(s):
    return sha.new(s).digest()

def hmac(key, text):

    """Given strings 'key' and 'text', produce an HMAC digest."""

    # If the key is longer than BLEN, hash it first.  The result must
    # be less than BLEN bytes.  This depends on the hash function used;
    # sha1 and md5 are both OK.

    l = len(key)
    if l > BLEN:
	key = hash(key)
	l = len(key)

    # Pad the key with zeros to BLEN bytes.

    key = key + '\0' * (BLEN - l)
    key = map(ord, key)

    # Now compute the HMAC.

    l = map(lambda x, y: x ^ y, key, ipad)
    s = reduce(lambda x, y: x + chr(y), l, '')
    s = hash(s + text)
    l = map(lambda x, y: x ^ y, key, opad)
    t = reduce(lambda x, y: x + chr(y), l, '')
    s = hash(t + s)

    return s
