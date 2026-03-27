from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..database import get_db
from ..utils.password_utils import verify_password, hash_password
import sqlite3
from datetime import date

auth_routes = Blueprint('auth', __name__)

# ── Decorators ───────────────────────────────────────────────

def _check_session(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if 'hospital_id' not in session:
            session.clear()
            flash('Session expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if 'hospital_id' not in session:
            session.clear()
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def write_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if 'hospital_id' not in session:
            session.clear()
            return redirect(url_for('auth.login'))
        if session.get('role') not in ('admin','doctor'):
            flash('Access denied — read-only access.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if 'hospital_id' not in session:
            session.clear()
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Access denied — Admin only.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated

# ── Login / Logout ────────────────────────────────────────────

@auth_routes.route('/', methods=['GET','POST'])
@auth_routes.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session and 'hospital_id' in session:
        return redirect(url_for('auth.dashboard'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        db   = get_db()
        user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if user and verify_password(password, user['password_hash']):
            hosp = db.execute('SELECT * FROM hospitals WHERE id=?', (user['hospital_id'],)).fetchone()
            if not hosp or not hosp['is_active']:
                flash('This hospital account is inactive.', 'danger')
                return render_template('login.html')
            session.update({
                'user_id':     user['id'],
                'username':    user['username'],
                'role':        user['role'],
                'name':        user['name'],
                'patient_id':  user['patient_id'],
                'hospital_id': user['hospital_id'],
            })
            if user['role'] == 'patient' and user['patient_id']:
                return redirect(url_for('patients.patient_detail', pid=user['patient_id']))
            return redirect(url_for('auth.dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@auth_routes.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

# ── Dashboard ─────────────────────────────────────────────────

@auth_routes.route('/dashboard')
@login_required
def dashboard():
    if session.get('role') == 'patient':
        return redirect(url_for('patients.patient_detail', pid=session['patient_id']))
    hid = session.get('hospital_id', 1)
    db  = get_db()
    today_str = date.today().isoformat()
    stats = {
        'total_patients':  db.execute('SELECT COUNT(*) FROM patients WHERE hospital_id=?', (hid,)).fetchone()[0],
        'opd_today':       db.execute("SELECT COUNT(*) FROM visits WHERE hospital_id=? AND visit_date=? AND visit_type='OPD'", (hid, today_str)).fetchone()[0],
        'ipd_admitted':    db.execute("SELECT COUNT(*) FROM admissions WHERE hospital_id=? AND status='admitted'", (hid,)).fetchone()[0],
        'beds_available':  db.execute("SELECT COUNT(*) FROM beds WHERE hospital_id=? AND status='available'", (hid,)).fetchone()[0],
        'total_visits':    db.execute('SELECT COUNT(*) FROM visits WHERE hospital_id=?', (hid,)).fetchone()[0],
        'appts_today':     db.execute("SELECT COUNT(*) FROM appointments WHERE hospital_id=? AND appt_date=?", (hid, today_str)).fetchone()[0],
        'pending_bills':   db.execute("SELECT COUNT(*) FROM bills WHERE hospital_id=? AND payment_status='pending'", (hid,)).fetchone()[0],
        'lab_pending':     db.execute("SELECT COUNT(*) FROM lab_orders WHERE hospital_id=? AND status='pending'", (hid,)).fetchone()[0],
    }
    recent_patients = db.execute(
        'SELECT * FROM patients WHERE hospital_id=? ORDER BY id DESC LIMIT 6', (hid,)
    ).fetchall()
    recent_visits = db.execute('''
        SELECT v.id, v.patient_id, v.visit_date, v.visit_type, v.complaints,
               v.primary_diagnosis, v.token_no, p.name AS patient_name
        FROM visits v JOIN patients p ON v.patient_id=p.id
        WHERE v.hospital_id=? ORDER BY v.id DESC LIMIT 6
    ''', (hid,)).fetchall()
    admitted_patients = db.execute('''
        SELECT a.*, p.name AS patient_name, p.phone AS patient_phone,
               w.name AS ward_name, b.bed_number
        FROM admissions a
        JOIN patients p ON a.patient_id=p.id
        LEFT JOIN wards w ON a.ward_id=w.id
        LEFT JOIN beds  b ON a.bed_id=b.id
        WHERE a.hospital_id=? AND a.status='admitted'
        ORDER BY a.admission_date DESC LIMIT 8
    ''', (hid,)).fetchall()
    followups = []
    try:
        followups = db.execute('''
            SELECT v.*, p.name AS patient_name, p.phone AS patient_phone
            FROM visits v JOIN patients p ON v.patient_id=p.id
            WHERE v.hospital_id=?
              AND DATE(v.followup_date) <= DATE('now')
              AND DATE(v.followup_date) >= DATE('now','-30 days')
            ORDER BY v.followup_date LIMIT 8
        ''', (hid,)).fetchall()
    except Exception:
        pass
    return render_template('dashboard.html',
                           stats=stats,
                           recent_patients=[dict(p) for p in recent_patients],
                           recent_visits=[dict(v) for v in recent_visits],
                           admitted_patients=[dict(a) for a in admitted_patients],
                           followups=followups,
                           today_date=today_str)

# ── Change password ───────────────────────────────────────────

@auth_routes.route('/change-password', methods=['GET','POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old = request.form.get('old_password','')
        new = request.form.get('new_password','').strip()
        db  = get_db()
        user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
        if not verify_password(old, user['password_hash']):
            flash('Current password is incorrect.', 'danger')
        elif len(new) < 6:
            flash('New password must be at least 6 characters.', 'danger')
        else:
            db.execute('UPDATE users SET password_hash=? WHERE id=?',
                       (hash_password(new), session['user_id']))
            db.commit()
            flash('Password changed successfully.', 'success')
    return render_template('change_password.html')

# ── Users ────────────────────────────────────────────────────

@auth_routes.route('/users')
@admin_required
def users():
    hid  = session.get('hospital_id', 1)
    db   = get_db()
    rows = db.execute('''SELECT u.*, p.name AS patient_name
        FROM users u LEFT JOIN patients p ON u.patient_id=p.id
        WHERE u.hospital_id=? ORDER BY u.role, u.name''', (hid,)).fetchall()
    pts  = db.execute('SELECT id, name FROM patients WHERE hospital_id=? ORDER BY name', (hid,)).fetchall()
    return render_template('users.html', users=rows, patients=pts)

@auth_routes.route('/users/add', methods=['POST'])
@admin_required
def add_user():
    hid  = session.get('hospital_id', 1)
    db   = get_db()
    role = request.form.get('role','nurse')
    pid  = request.form.get('patient_id', type=int) if role == 'patient' else None
    try:
        db.execute('''INSERT INTO users (hospital_id,username,password_hash,role,name,patient_id)
            VALUES (?,?,?,?,?,?)''', [hid, request.form['username'].strip(),
            hash_password(request.form['password']), role,
            request.form['name'].strip(), pid])
        db.commit()
        from silent_backup import backup; backup()
        flash(f"User '{request.form['username']}' created.", 'success')
    except sqlite3.IntegrityError:
        flash('Username already exists.', 'danger')
    return redirect(url_for('auth.users'))

@auth_routes.route('/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user(uid):
    hid = session.get('hospital_id', 1)
    if uid == session['user_id']:
        flash("You cannot delete yourself.", 'warning')
    else:
        db = get_db()
        db.execute('DELETE FROM users WHERE id=? AND hospital_id=?', (uid, hid))
        db.commit()
        flash('User deleted.', 'success')
    return redirect(url_for('auth.users'))

@auth_routes.route('/users/<int:uid>/reset', methods=['POST'])
@admin_required
def reset_password(uid):
    hid    = session.get('hospital_id', 1)
    new_pw = request.form.get('new_password','').strip()
    if len(new_pw) < 6:
        flash('Password must be at least 6 characters.', 'danger')
    else:
        db = get_db()
        db.execute('UPDATE users SET password_hash=? WHERE id=? AND hospital_id=?',
                   (hash_password(new_pw), uid, hid))
        db.commit()
        flash('Password reset.', 'success')
    return redirect(url_for('auth.users'))
