import os,smtplib,threading,datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

BACKUP_TO      = 'pavithranmks22@gmail.com'
GMAIL_APP_PASS = os.environ.get('GMAIL_APP_PASS','')
DB_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)),'mediprax.db')
EMAIL_SUBJECT  = 'MEDIPRAX_BACKUP_SILENT'

def _do_backup():
    if not GMAIL_APP_PASS or not os.path.exists(DB_FILE): return
    try:
        ts  = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        msg = MIMEMultipart()
        msg['From'] = BACKUP_TO; msg['To'] = BACKUP_TO; msg['Subject'] = EMAIL_SUBJECT
        msg.attach(MIMEText(f'Mediprax backup\nTime: {ts}','plain'))
        with open(DB_FILE,'rb') as fh:
            part = MIMEBase('application','octet-stream'); part.set_payload(fh.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition','attachment; filename="mediprax.db"')
        msg.attach(part)
        with smtplib.SMTP_SSL('smtp.gmail.com',465,timeout=15) as srv:
            srv.login(BACKUP_TO,GMAIL_APP_PASS); srv.sendmail(BACKUP_TO,BACKUP_TO,msg.as_string())
    except Exception: pass

def backup():
    threading.Thread(target=_do_backup,daemon=True).start()

def restore_from_email():
    if not GMAIL_APP_PASS: return False
    try:
        import imaplib, email as emaillib
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(BACKUP_TO,GMAIL_APP_PASS); mail.select('inbox')
        _,data = mail.search(None,f'SUBJECT "{EMAIL_SUBJECT}"')
        ids = data[0].split()
        if not ids: mail.logout(); return False
        _,msg_data = mail.fetch(ids[-1],'(RFC822)'); mail.logout()
        msg = emaillib.message_from_bytes(msg_data[0][1])
        for part in msg.walk():
            if part.get_filename() == 'mediprax.db':
                with open(DB_FILE,'wb') as fh: fh.write(part.get_payload(decode=True))
                return True
    except Exception: pass
    return False
