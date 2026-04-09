from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..database import get_db

settings_routes = Blueprint('settings', __name__, url_prefix='/settings')

@settings_routes.route('/', methods=['GET','POST'])
def hospital_settings():
    if session.get('role') != 'admin': return redirect(url_for('auth.dashboard'))
    hid = session.get('hospital_id',1); db = get_db()
    if request.method == 'POST':
        f = request.form
        db.execute('UPDATE hospitals SET name=?,tagline=?,address=?,phone=?,email=?,color1=?,color2=? WHERE id=?',
            [f.get('hospital_name','').strip(),f.get('hospital_tagline','').strip(),
             f.get('address','').strip(),f.get('phone','').strip(),f.get('email','').strip(),
             f.get('logo_color1','#1a6fad'),f.get('logo_color2','#0e9f8b'),hid])
        db.execute('UPDATE settings SET doctor_name=?,doctor_degree=? WHERE hospital_id=?',
            [f.get('doctor_name','').strip(),f.get('doctor_degree','').strip(),hid])
        db.commit(); flash('Settings saved.','success')
        return redirect(url_for('settings.hospital_settings'))
    s = db.execute('SELECT * FROM settings WHERE hospital_id=?',(hid,)).fetchone()
    h = db.execute('SELECT * FROM hospitals WHERE id=?',(hid,)).fetchone()
    return render_template('settings.html', s=s, hosp=h)
