import os
import sys
import secrets

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_secret_key():
    """Use SECRET_KEY from env. If unset, fall back to a per-process random
    key in development and print a loud warning. In production
    (FLASK_ENV=production), refuse to start without an explicit SECRET_KEY.
    """
    k = os.environ.get('SECRET_KEY', '').strip()
    if k:
        return k
    env = os.environ.get('FLASK_ENV', '').strip().lower()
    if env == 'production':
        raise RuntimeError(
            'SECRET_KEY environment variable is required in production. '
            'Set a long, random value (e.g. `python -c "import secrets;print(secrets.token_hex(32))"`).'
        )
    print('[CONFIG] WARNING: SECRET_KEY not set; using an ephemeral key. '
          'Sessions will be invalidated on restart.', file=sys.stderr)
    return secrets.token_hex(32)


class Config:
    SECRET_KEY = _resolve_secret_key()
    DATABASE   = os.path.join(_BASE_DIR, 'mediprax.db')
    UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'static', 'uploads', 'prescriptions')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024   # 5 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    # Make session cookies stricter by default
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '').strip() in ('1', 'true', 'yes', 'on')
