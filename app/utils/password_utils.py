"""Password hashing.

New hashes use bcrypt. Legacy SHA-256 hashes (64 hex chars) are still accepted
on verify so existing accounts continue to work, and callers can detect a legacy
hash via `needs_rehash()` and re-hash with bcrypt on next successful login.
"""
import hashlib
import bcrypt


def hash_password(pw: str) -> str:
    if pw is None:
        pw = ''
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _is_legacy_sha256(h: str) -> bool:
    return isinstance(h, str) and len(h) == 64 and all(c in '0123456789abcdef' for c in h.lower())


def verify_password(pw: str, hashed: str) -> bool:
    if not hashed:
        return False
    if pw is None:
        pw = ''
    # Legacy unsalted SHA-256 fallback
    if _is_legacy_sha256(hashed):
        return hashlib.sha256(pw.encode('utf-8')).hexdigest() == hashed
    try:
        return bcrypt.checkpw(pw.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the stored hash should be upgraded to bcrypt."""
    return _is_legacy_sha256(hashed)
