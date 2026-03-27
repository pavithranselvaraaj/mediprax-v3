"""
Super Admin routes — /admin/*
Only accessible by super_admin login (you).
Lists all hospitals, creates new hospitals + their admin accounts.
"""
from flask import (Blueprint, render_template, request,
                   redirect, url_for, session, flash)
from ..database import get_db
import hashlib

super_admin_routes = Blueprint('super_admin', __name__, url_prefix='/admin')

def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()

def _sa_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'super_admin':
            return redirect(url_for('super_admin.sa_login'))
        return f(*args, **kwargs)
    return decorated

# ── Super admin login ─────────────────────────────────────────
@super_admin_routes.route('/login', methods=['GET', 'POST'])
def sa_login():
    if session.get('role') == 'super_admin':
        return redirect(url_for('super_admin.hospital_list'))
    if request.method == 'POST':
        un = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        db = get_db()
        row = db.execute(
            'SELECT * FROM super_admins WHERE username=? AND password_hash=?',
            (un, _hash(pw))
        ).fetchone()
        if row:
            session.clear()
            session['role']     = 'super_admin'
            session['name']     = 'Super Admin'
            session['username'] = un
            return redirect(url_for('super_admin.hospital_list'))
        flash('Invalid credentials.', 'danger')
    return render_template('admin/sa_login.html')

@super_admin_routes.route('/logout')
def sa_logout():
    session.clear()
    return redirect(url_for('super_admin.sa_login'))

# ── Hospital list with search + pagination ────────────────────
@super_admin_routes.route('/')
@_sa_required
def hospital_list():
    from flask import request as req
    db       = get_db()
    q        = req.args.get('q', '').strip()
    page     = max(1, req.args.get('page', 1, type=int))
    per_page = 10

    base_sql = (
        "SELECT h.*, "
        "(SELECT COUNT(*) FROM users u WHERE u.hospital_id=h.id AND u.role!='patient') AS staff_count, "
        "(SELECT COUNT(*) FROM patients p WHERE p.hospital_id=h.id) AS patient_count, "
        "(SELECT COUNT(*) FROM visits v WHERE v.hospital_id=h.id) AS visit_count "
        "FROM hospitals h "
    )
    if q:
        where  = "WHERE h.name LIKE ? OR h.phone LIKE ? OR h.email LIKE ? OR h.address LIKE ? "
        params = (f'%{q}%',) * 4
        total  = db.execute("SELECT COUNT(*) FROM hospitals h " + where, params).fetchone()[0]
        rows   = db.execute(base_sql + where + "ORDER BY h.id DESC LIMIT ? OFFSET ?",
                            params + (per_page, (page-1)*per_page)).fetchall()
    else:
        params = ()
        total  = db.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
        rows   = db.execute(base_sql + "ORDER BY h.id DESC LIMIT ? OFFSET ?",
                            (per_page, (page-1)*per_page)).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('admin/hospital_list.html',
                           hospitals=rows, search=q,
                           page=page, total_pages=total_pages, total=total)

# ── Create hospital ───────────────────────────────────────────
@super_admin_routes.route('/hospitals/create', methods=['GET', 'POST'])
@_sa_required
def create_hospital():
    if request.method == 'POST':
        f  = request.form
        db = get_db()

        # 1. Create hospital record
        cur = db.execute('''INSERT INTO hospitals
            (name, tagline, address, phone, email, color1, color2)
            VALUES (?,?,?,?,?,?,?)''', [
            f.get('name','').strip(),
            f.get('tagline','Quality Healthcare').strip(),
            f.get('address','').strip(),
            f.get('phone','').strip(),
            f.get('email','').strip(),
            f.get('color1','#1a6fad').strip(),
            f.get('color2','#0e9f8b').strip(),
        ])
        hosp_id = cur.lastrowid

        # 2. Create settings row for this hospital
        db.execute('''INSERT INTO settings (hospital_id, doctor_name, doctor_degree)
            VALUES (?,?,?)''', [
            hosp_id,
            f.get('doctor_name','').strip(),
            f.get('doctor_degree','MBBS, MD').strip(),
        ])

        # 3. Create admin login for this hospital
        admin_un = f.get('admin_username','').strip()
        admin_pw = f.get('admin_password','').strip()
        admin_name = f.get('admin_name','').strip()
        if admin_un and admin_pw:
            try:
                db.execute('''INSERT INTO users
                    (hospital_id, username, password_hash, role, name)
                    VALUES (?,?,?,'admin',?)''',
                    [hosp_id, admin_un, _hash(admin_pw), admin_name or 'Hospital Admin'])
            except Exception as e:
                db.rollback()
                flash(f'Username "{admin_un}" already taken. Choose another.', 'danger')
                return redirect(url_for('super_admin.create_hospital'))

        db.commit()
        flash(f'Hospital "{f.get("name")}" created successfully!', 'success')
        return redirect(url_for('super_admin.hospital_list'))

    return render_template('admin/create_hospital.html')

# ── View/Edit hospital ────────────────────────────────────────
@super_admin_routes.route('/hospitals/<int:hid>', methods=['GET', 'POST'])
@_sa_required
def hospital_detail(hid):
    db   = get_db()
    hosp = db.execute('SELECT * FROM hospitals WHERE id=?', (hid,)).fetchone()
    if not hosp:
        flash('Hospital not found.', 'danger')
        return redirect(url_for('super_admin.hospital_list'))

    if request.method == 'POST':
        action = request.form.get('action')
        f = request.form

        if action == 'update_hospital':
            db.execute('''UPDATE hospitals SET
                name=?,tagline=?,address=?,phone=?,email=?,
                color1=?,color2=?,is_active=? WHERE id=?''', [
                f.get('name','').strip(),
                f.get('tagline','').strip(),
                f.get('address','').strip(),
                f.get('phone','').strip(),
                f.get('email','').strip(),
                f.get('color1','#1a6fad'),
                f.get('color2','#0e9f8b'),
                1 if f.get('is_active') else 0,
                hid
            ])
            db.commit()
            flash('Hospital updated.', 'success')

        elif action == 'add_user':
            try:
                db.execute('''INSERT INTO users
                    (hospital_id,username,password_hash,role,name)
                    VALUES (?,?,?,?,?)''', [
                    hid,
                    f.get('username','').strip(),
                    _hash(f.get('password','')),
                    f.get('role','nurse'),
                    f.get('name','').strip(),
                ])
                db.commit()
                flash('User created.', 'success')
            except Exception:
                flash('Username already exists.', 'danger')

        elif action == 'toggle_active':
            cur = db.execute('SELECT is_active FROM hospitals WHERE id=?', (hid,)).fetchone()
            db.execute('UPDATE hospitals SET is_active=? WHERE id=?',
                       (0 if cur['is_active'] else 1, hid))
            db.commit()
            flash('Status updated.', 'success')

        elif action == 'reset_user_pw':
            uid = f.get('user_id', type=int)
            new_pw = f.get('new_password','').strip()
            if uid and len(new_pw) >= 6:
                db.execute('UPDATE users SET password_hash=? WHERE id=? AND hospital_id=?',
                           (_hash(new_pw), uid, hid))
                db.commit()
                flash('Password reset.', 'success')

        return redirect(url_for('super_admin.hospital_detail', hid=hid))

    users = db.execute(
        'SELECT * FROM users WHERE hospital_id=? ORDER BY role, name', (hid,)
    ).fetchall()
    stats = {
        'patients': db.execute('SELECT COUNT(*) FROM patients WHERE hospital_id=?', (hid,)).fetchone()[0],
        'visits':   db.execute('SELECT COUNT(*) FROM visits WHERE hospital_id=?', (hid,)).fetchone()[0],
        'staff':    db.execute("SELECT COUNT(*) FROM users WHERE hospital_id=? AND role!='patient'", (hid,)).fetchone()[0],
    }
    return render_template('admin/hospital_detail.html', hosp=hosp, users=users, stats=stats)

# ── Visit hospital as admin (impersonate) ─────────────────────
@super_admin_routes.route('/hospitals/<int:hid>/visit')
@_sa_required
def visit_hospital(hid):
    """Enter a hospital as its admin — super admin can return via /admin/return."""
    db   = get_db()
    hosp = db.execute('SELECT * FROM hospitals WHERE id=?', (hid,)).fetchone()
    if not hosp:
        flash('Hospital not found.', 'danger')
        return redirect(url_for('super_admin.hospital_list'))
    # Find the admin user for this hospital
    admin_user = db.execute(
        "SELECT * FROM users WHERE hospital_id=? AND role='admin' LIMIT 1", (hid,)
    ).fetchone()
    if not admin_user:
        flash('No admin user found for this hospital. Create one first.', 'warning')
        return redirect(url_for('super_admin.hospital_detail', hid=hid))
    # Store super admin marker so they can return
    session['_sa_return'] = True
    session['user_id']    = admin_user['id']
    session['username']   = admin_user['username']
    session['role']       = admin_user['role']
    session['name']       = admin_user['name']
    session['patient_id'] = None
    hid = session.get('hospital_id', 1)
    flash(f'Now viewing <strong>{hosp["name"]}</strong> as admin. <a href="/admin/return" class="alert-link">Return to Admin Panel</a>', 'info')
    return redirect(url_for('auth.dashboard'))

# ── Return to super admin panel ───────────────────────────────
@super_admin_routes.route('/return')
def return_to_admin():
    """Return from hospital view back to super admin panel."""
    session.clear()
    session['role']     = 'super_admin'
    session['name']     = 'Super Admin'
    session['username'] = 'superadmin'
    return redirect(url_for('super_admin.hospital_list'))
