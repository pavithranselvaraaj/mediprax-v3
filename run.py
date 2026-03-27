import os
from app import create_app

# On startup: if DB missing, try to restore from Gmail backup silently
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mediprax.db')
if not os.path.exists(DB_PATH):
    try:
        from silent_backup import restore_from_email
        restore_from_email()
    except Exception:
        pass

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
