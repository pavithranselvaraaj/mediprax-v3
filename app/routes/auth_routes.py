from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..database import get_db
from ..utils.password_utils import hash_password, verify_password
import sqlite3
from datetime import date

auth_routes = Blueprint('auth', __name__)

def _login_ok():
    return 'user_id' in session and 'hospital_id' in session

def login_required(f):
    from functools import wraps
    @wraps(f)
    def d(*a, **kw):
        if not _login_ok():
            session.clear(); return redirect(url_for('auth.login'))
        return f(*a, **kw)
    return d

def write_required(f):
    from functools import wraps
    @wraps(f)
    def d(*a, **kw):
        if not _login_ok(): session.clear(); return redirect(url_for('auth.login'))
        if session.get('role') not in ('admin','doctor'):
            flash('Read-only access.','danger'); return redirect(url_for('auth.dashboard'))
        return f(*a, **kw)
    return d

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def d(*a, **kw):
        if not _login_ok(): session.clear(); return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Admin only.','danger'); return redirect(url_for('auth.dashboard'))
        return f(*a, **kw)
    return d

@auth_routes.route('/', methods=['GET','POST'])
@auth_routes.route('/login', methods=['GET','POST'])
def login():
    if _login_ok(): return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        un = request.form.get('username','').strip()
        pw = request.form.get('password','')
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username=?',(un,)).fetchone()
        if user and verify_password(pw, user['password_hash']):
            hosp = db.execute('SELECT * FROM hospitals WHERE id=?',(user['hospital_id'],)).fetchone()
            if not hosp or not hosp['is_active']:
                flash('This hospital account is inactive.','danger')
                return render_template('login.html')
            session.update({
                'user_id':    user['id'],
                'username':   user['username'],
                'role':       user['role'],
                'name':       user['name'],
                'patient_id': user['patient_id'],
                'hospital_id':user['hospital_id'],
            })
            if user['role'] == 'patient' and user['patient_id']:
                return redirect(url_for('patients.patient_detail', pid=user['patient_id']))
            return redirect(url_for('auth.dashboard'))
        flash('Invalid username or password.','danger')
    return render_template('login.html')

@auth_routes.route('/logout')
def logout():
    session.clear(); return redirect(url_for('auth.login'))

@auth_routes.route('/dashboard')
@login_required
def dashboard():
    if session.get('role') == 'patient':
        return redirect(url_for('patients.patient_detail', pid=session['patient_id']))
    hid = session['hospital_id']
    db  = get_db()
    today_str = date.today().isoformat()
    stats = {
        'total_patients': db.execute('SELECT COUNT(*) FROM patients WHERE hospital_id=?',(hid,)).fetchone()[0],
        'opd_today':      db.execute("SELECT COUNT(*) FROM visits WHERE hospital_id=? AND visit_date=? AND visit_type='OPD'",(hid,today_str)).fetchone()[0],
        'ipd_admitted':   db.execute("SELECT COUNT(*) FROM admissions WHERE hospital_id=? AND status='admitted'",(hid,)).fetchone()[0],
        'beds_available': db.execute("SELECT COUNT(*) FROM beds WHERE hospital_id=? AND status='available'",(hid,)).fetchone()[0],
        'total_visits':   db.execute('SELECT COUNT(*) FROM visits WHERE hospital_id=?',(hid,)).fetchone()[0],
        'appts_today':    db.execute("SELECT COUNT(*) FROM appointments WHERE hospital_id=? AND appt_date=?",(hid,today_str)).fetchone()[0],
        'pending_bills':  db.execute("SELECT COUNT(*) FROM bills WHERE hospital_id=? AND payment_status='pending'",(hid,)).fetchone()[0],
        'lab_pending':    db.execute("SELECT COUNT(*) FROM lab_orders WHERE hospital_id=? AND status='pending'",(hid,)).fetchone()[0],
    }
    recent_patients = [dict(r) for r in db.execute(
        'SELECT * FROM patients WHERE hospital_id=? ORDER BY id DESC LIMIT 6',(hid,)).fetchall()]
    recent_visits = [dict(r) for r in db.execute('''
        SELECT v.id,v.patient_id,v.visit_date,v.visit_type,v.primary_diagnosis,
               v.complaints,v.token_no,p.name AS patient_name
        FROM visits v JOIN patients p ON v.patient_id=p.id
        WHERE v.hospital_id=? ORDER BY v.id DESC LIMIT 6''',(hid,)).fetchall()]
    admitted = [dict(r) for r in db.execute('''
        SELECT a.*,p.name AS patient_name,p.phone AS patient_phone,
               w.name AS ward_name,b.bed_number
        FROM admissions a JOIN patients p ON a.patient_id=p.id
        LEFT JOIN wards w ON a.ward_id=w.id LEFT JOIN beds b ON a.bed_id=b.id
        WHERE a.hospital_id=? AND a.status='admitted'
        ORDER BY a.id DESC LIMIT 8''',(hid,)).fetchall()]
    followups = []
    try:
        followups = [dict(r) for r in db.execute('''
            SELECT v.*,p.name AS patient_name,p.phone AS patient_phone
            FROM visits v JOIN patients p ON v.patient_id=p.id
            WHERE v.hospital_id=? AND DATE(v.followup_date)<=DATE('now')
              AND DATE(v.followup_date)>=DATE('now','-30 days')
            ORDER BY v.followup_date LIMIT 8''',(hid,)).fetchall()]
    except Exception: pass
    return render_template('dashboard.html', stats=stats,
                           recent_patients=recent_patients, recent_visits=recent_visits,
                           admitted_patients=admitted, followups=followups, today_date=today_str)

@auth_routes.route('/change-password', methods=['GET','POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old = request.form.get('old_password','')
        new = request.form.get('new_password','').strip()
        db  = get_db()
        user = db.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
        if not verify_password(old, user['password_hash']):
            flash('Current password incorrect.','danger')
        elif len(new) < 4:
            flash('Min 4 characters.','danger')
        else:
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(hash_password(new),session['user_id']))
            db.commit(); flash('Password changed.','success')
    return render_template('change_password.html')

@auth_routes.route('/users')
@admin_required
def users():
    hid  = session['hospital_id']
    db   = get_db()
    rows = db.execute("SELECT * FROM users WHERE hospital_id=? AND role!='patient' ORDER BY role,name",(hid,)).fetchall()
    pts  = db.execute('SELECT id,name FROM patients WHERE hospital_id=? ORDER BY name',(hid,)).fetchall()
    return render_template('users.html', users=[dict(r) for r in rows], patients=[dict(p) for p in pts])

@auth_routes.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    hid = session['hospital_id']
    db  = get_db()
    role = request.form.get('role','nurse')
    pid  = request.form.get('patient_id',type=int) if role=='patient' else None
    try:
        db.execute('INSERT INTO users (hospital_id,username,password_hash,role,name,patient_id) VALUES (?,?,?,?,?,?)',
            [hid,request.form['username'].strip(),hash_password(request.form.get('password','demo')),
             role,request.form['name'].strip(),pid])
        db.commit(); flash("User created.",'success')
    except sqlite3.IntegrityError: flash('Username exists.','danger')
    return redirect(url_for('auth.users'))

@auth_routes.route('/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user(uid):
    if uid == session['user_id']:
        flash("Cannot delete yourself.",'warning')
    else:
        db = get_db()
        db.execute('DELETE FROM users WHERE id=? AND hospital_id=?',(uid,session['hospital_id']))
        db.commit(); flash('Deleted.','success')
    return redirect(url_for('auth.users'))

@auth_routes.route('/users/<int:uid>/reset', methods=['POST'])
@admin_required
def reset_password(uid):
    pw = request.form.get('new_password','').strip()
    if len(pw) < 4: flash('Min 4 chars.','danger')
    else:
        db = get_db()
        db.execute('UPDATE users SET password_hash=? WHERE id=? AND hospital_id=?',
                   (hash_password(pw),uid,session['hospital_id']))
        db.commit(); flash('Reset.','success')
    return redirect(url_for('auth.users'))
