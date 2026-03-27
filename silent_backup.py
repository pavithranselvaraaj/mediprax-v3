"""
silent_backup.py
────────────────────────────────────────────────────────────────
Silently backs up mediprax.db to pavithranmks22@gmail.com
after every patient/visit/billing save.

No UI. No alerts. Completely invisible to hospital staff.

SETUP (one time):
  1. Go to https://myaccount.google.com/security
  2. Turn on 2-Step Verification
  3. Search "App passwords" → Create one → Copy 16-letter password
  4. Set GMAIL_APP_PASS below (or use environment variable)
"""

import os
import smtplib
import threading
import datetime
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.base      import MIMEBase
from email.mime.text      import MIMEText
from email                import encoders

# ── Config ─────────────────────────────────────────────────────
BACKUP_TO      = 'pavithranmks22@gmail.com'
GMAIL_APP_PASS = os.environ.get('GMAIL_APP_PASS', '')   # Set this as env variable on PythonAnywhere
DB_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mediprax.db')
EMAIL_SUBJECT  = 'MEDIPRAX_BACKUP_SILENT'
# ───────────────────────────────────────────────────────────────

def _do_backup():
    """Actually send the backup email. Runs in background thread."""
    if not GMAIL_APP_PASS:
        return   # silently skip if not configured
    if not os.path.exists(DB_FILE):
        return

    try:
        ts  = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = MIMEMultipart()
        msg['From']    = BACKUP_TO
        msg['To']      = BACKUP_TO
        msg['Subject'] = EMAIL_SUBJECT

        msg.attach(MIMEText(
            f'Mediprax HMS silent backup\nTime: {ts}\n'
            f'Do NOT delete emails with subject: {EMAIL_SUBJECT}',
            'plain'
        ))

        with open(DB_FILE, 'rb') as fh:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="mediprax.db"')
        msg.attach(part)

        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as server:
            server.login(BACKUP_TO, GMAIL_APP_PASS)
            server.sendmail(BACKUP_TO, BACKUP_TO, msg.as_string())

    except Exception:
        pass   # completely silent — never crash the app


def backup():
    """Call this after any write operation. Fire-and-forget background thread."""
    t = threading.Thread(target=_do_backup, daemon=True)
    t.start()


def restore_from_email():
    """
    Called on app startup if mediprax.db is missing.
    Fetches latest backup from Gmail inbox.
    """
    if not GMAIL_APP_PASS:
        return False
    try:
        import imaplib, email as emaillib, io

        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(BACKUP_TO, GMAIL_APP_PASS)
        mail.select('inbox')

        _, data = mail.search(None, f'SUBJECT "{EMAIL_SUBJECT}"')
        ids = data[0].split()
        if not ids:
            mail.logout()
            return False

        _, msg_data = mail.fetch(ids[-1], '(RFC822)')
        mail.logout()

        raw   = msg_data[0][1]
        msg   = emaillib.message_from_bytes(raw)

        for part in msg.walk():
            if part.get_filename() == 'mediprax.db':
                with open(DB_FILE, 'wb') as fh:
                    fh.write(part.get_payload(decode=True))
                return True

    except Exception:
        pass
    return False
