from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..database import get_db
from ..utils.validators import validate_email, validate_phone, validate_nonempty
import re

settings_routes = Blueprint('settings', __name__, url_prefix='/settings')

def _validate_color(c):
    """Validate hex color code"""
    if not c: return False
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', c.strip()))

@settings_routes.route('/', methods=['GET','POST'])
def hospital_settings():
    if session.get('role') != 'admin': return redirect(url_for('auth.dashboard'))
    hid = session.get('hospital_id',1); db = get_db()
    if request.method == 'POST':
        f = request.form
        # Validation
        hospital_name = (f.get('hospital_name') or '').strip()
        if not validate_nonempty(hospital_name, 2, 100):
            flash('Hospital name must be 2-100 characters.', 'danger')
            return redirect(url_for('settings.hospital_settings'))

        email = (f.get('email') or '').strip().lower()
        if email and not validate_email(email):
            flash('Invalid email format.', 'danger')
            return redirect(url_for('settings.hospital_settings'))

        phone = (f.get('phone') or '').strip()
        if phone and not validate_phone(phone):
            flash('Enter a valid 10-digit Indian mobile number (starting with 6-9).', 'danger')
            return redirect(url_for('settings.hospital_settings'))

        color1 = f.get('logo_color1','#1a6fad').strip()
        color2 = f.get('logo_color2','#0e9f8b').strip()
        if not _validate_color(color1): color1 = '#1a6fad'
        if not _validate_color(color2): color2 = '#0e9f8b'

        db.execute('UPDATE hospitals SET name=?,tagline=?,address=?,phone=?,email=?,color1=?,color2=? WHERE id=?',
            [hospital_name, (f.get('hospital_tagline') or '').strip()[:200],
             (f.get('address') or '').strip()[:500], phone, email,
             color1, color2, hid])

        # Check if settings row exists
        existing = db.execute('SELECT id FROM settings WHERE hospital_id=?', (hid,)).fetchone()
        if existing:
            db.execute('UPDATE settings SET doctor_name=?,doctor_degree=? WHERE hospital_id=?',
                [(f.get('doctor_name') or '').strip()[:100], (f.get('doctor_degree') or '').strip()[:100], hid])
        else:
            db.execute('INSERT INTO settings (hospital_id,doctor_name,doctor_degree) VALUES (?,?,?)',
                [hid, (f.get('doctor_name') or '').strip()[:100], (f.get('doctor_degree') or '').strip()[:100]])

        db.commit()
        flash('Settings saved successfully.', 'success')
        return redirect(url_for('settings.hospital_settings'))

    s = db.execute('SELECT * FROM settings WHERE hospital_id=?',(hid,)).fetchone()
    h = db.execute('SELECT * FROM hospitals WHERE id=?',(hid,)).fetchone()
    return render_template('settings.html', s=s, hosp=h)
