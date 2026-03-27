from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..database import get_db

settings_routes = Blueprint('settings', __name__, url_prefix='/settings')

def _doctor_only():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if session.get('role') != 'doctor':
        flash('Access denied — Doctor only.', 'danger')
        return redirect(url_for('auth.dashboard'))
    return None

@settings_routes.route('/', methods=['GET', 'POST'])
def hospital_settings():
    redir = _doctor_only()
    if redir:
        return redir
    db = get_db()
    if request.method == 'POST':
        f = request.form
        db.execute('''UPDATE settings SET
            hospital_name=?, hospital_tagline=?, doctor_name=?,
            doctor_degree=?, address=?, phone=?, email=?,
            logo_color1=?, logo_color2=?
            WHERE id=1''', [
            f.get('hospital_name','').strip(),
            f.get('hospital_tagline','').strip(),
            f.get('doctor_name','').strip(),
            f.get('doctor_degree','').strip(),
            f.get('address','').strip(),
            f.get('phone','').strip(),
            f.get('email','').strip(),
            f.get('logo_color1','#1a6fad').strip(),
            f.get('logo_color2','#0e9f8b').strip(),
        ])
        db.commit()
        flash('Hospital settings saved successfully!', 'success')
        return redirect(url_for('settings.hospital_settings'))
    s = db.execute('SELECT * FROM settings WHERE id=1').fetchone()
    return render_template('settings.html', s=s)
