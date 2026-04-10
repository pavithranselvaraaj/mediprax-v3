# Simple reusable validators and normalizers for forms
import re
from datetime import datetime, date

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
# Indian phone: 10 digits starting with 6-9, optionally prefixed with +91 or 91
INDIAN_PHONE_RE = re.compile(r'^[6-9]\d{9}$')
NAME_RE = re.compile(r'^[a-zA-Z\s.\'-]+$')
AADHAR_RE = re.compile(r'^\d{12}$')


def validate_nonempty(val: str, min_len: int = 1, max_len: int | None = None) -> bool:
    if val is None:
        return False
    v = str(val).strip()
    if len(v) < min_len:
        return False
    if max_len is not None and len(v) > max_len:
        return False
    return True


def validate_name(name: str | None, min_len: int = 2, max_len: int = 100) -> bool:
    """Validate person name: letters, spaces, dots, hyphens, apostrophes only."""
    if not name:
        return False
    n = name.strip()
    if len(n) < min_len or len(n) > max_len:
        return False
    return bool(NAME_RE.match(n))


def validate_email(email: str | None) -> bool:
    if not email:
        return True  # optional by default
    e = email.strip().lower()
    if len(e) > 254:
        return False
    return bool(EMAIL_RE.match(e))


def normalize_phone(phone: str | None) -> str | None:
    """Normalize Indian phone number to 10-digit format."""
    if not phone:
        return None
    p = re.sub(r'[^0-9]', '', phone)
    # Strip leading 91 country code if present (results in 10 digits)
    if len(p) == 12 and p.startswith('91'):
        p = p[2:]
    elif len(p) == 11 and p.startswith('0'):
        p = p[1:]
    return p if p else None


def validate_phone(phone: str | None) -> bool:
    """Validate Indian mobile number: 10 digits starting with 6-9."""
    if not phone:
        return True  # optional by default
    p = normalize_phone(phone)
    if not p:
        return False
    return bool(INDIAN_PHONE_RE.match(p))


def validate_aadhar(aadhar: str | None) -> bool:
    """Validate Aadhar number: exactly 12 digits."""
    if not aadhar:
        return True  # optional
    a = re.sub(r'[^0-9]', '', aadhar)
    return bool(AADHAR_RE.match(a))


def safe_int(val, default=None, min_val=None, max_val=None):
    try:
        v = int(val)
        if min_val is not None and v < min_val:
            return default
        if max_val is not None and v > max_val:
            return default
        return v
    except Exception:
        return default


def safe_float(val, default=None, min_val=None, max_val=None):
    try:
        v = float(val)
        if min_val is not None and v < min_val:
            return default
        if max_val is not None and v > max_val:
            return default
        return v
    except Exception:
        return default


def validate_date(val: str | None, fmt: str = '%Y-%m-%d', allow_future: bool = True) -> bool:
    if not val:
        return True
    try:
        d = datetime.strptime(val, fmt).date()
        if not allow_future and d > date.today():
            return False
        return True
    except Exception:
        return False


def validate_dob(val: str | None) -> bool:
    """Validate date of birth: must be valid date and not in the future."""
    if not val:
        return True
    return validate_date(val, allow_future=False)


def validate_time(val: str | None, fmt: str = '%H:%M') -> bool:
    if not val:
        return True
    try:
        datetime.strptime(val, fmt)
        return True
    except Exception:
        return False


def validate_gender(g: str | None) -> bool:
    if not g:
        return True
    return g in ('Male', 'Female', 'Other')


def validate_role(role: str | None) -> bool:
    return role in ('admin', 'doctor', 'nurse', 'reception', 'lab', 'billing', 'patient')


def validate_age(age) -> bool:
    v = safe_int(age, default=None)
    return v is not None and 0 < v < 120


def validate_password(password: str | None, min_len: int = 4) -> bool:
    """Validate password has minimum length"""
    if not password:
        return False
    return len(password.strip()) >= min_len


def sanitize_string(val: str | None, max_len: int = 500) -> str:
    """Remove dangerous characters and limit length"""
    if not val:
        return ''
    # Strip and limit length
    return val.strip()[:max_len]

