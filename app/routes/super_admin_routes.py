from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from ..database import get_db
import hashlib, re

super_admin_routes = Blueprint('super_admin', __name__, url_prefix='/admin')

def _h(pw): return hashlib.sha256(pw.encode()).hexdigest()
def _email_ok(e): return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e.strip()))

def _sa(f):
    from functools import wraps
    @wraps(f)
    def d(*a, **kw):
        if session.get('role') != 'super_admin':
            return redirect(url_for('super_admin.sa_login'))
        return f(*a, **kw)
    return d

# ── Login ─────────────────────────────────────────────────────
@super_admin_routes.route('/login', methods=['GET','POST'])
def sa_login():
    if session.get('role') == 'super_admin':
        return redirect(url_for('super_admin.hospital_list'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        pw    = request.form.get('password','')
        if not _email_ok(email):
            flash('Enter a valid email.','danger'); return render_template('admin/sa_login.html')
        db    = get_db()
        # Support both email column and legacy username column
        cols = {r[1] for r in db.execute('PRAGMA table_info(super_admins)')}
        if 'email' in cols:
            row = db.execute('SELECT * FROM super_admins WHERE email=? AND password_hash=? AND is_active=1',
                             (email, _h(pw))).fetchone()
        else:
            row = db.execute('SELECT * FROM super_admins WHERE username=? AND password_hash=?',
                             (email, _h(pw))).fetchone()
        if row:
            session.clear()
            session['role']     = 'super_admin'
            session['sa_id']    = row['id']
            session['name']     = row['name'] if row['name'] else 'Super Admin'
            session['username'] = email
            return redirect(url_for('super_admin.hospital_list'))
        flash('Invalid email or password.', 'danger')
    return render_template('admin/sa_login.html')

@super_admin_routes.route('/logout')
def sa_logout():
    session.clear()
    return redirect(url_for('super_admin.sa_login'))

# ── Hospital list (search + pagination) ───────────────────────
@super_admin_routes.route('/')
@_sa
def hospital_list():
    db = get_db()
    q  = request.args.get('q','').strip()
    pg = max(1, request.args.get('page',1,type=int))
    pp = 10
    base = ("SELECT h.*,"
            "(SELECT COUNT(*) FROM users u WHERE u.hospital_id=h.id AND u.role!='patient') AS staff_count,"
            "(SELECT COUNT(*) FROM patients p WHERE p.hospital_id=h.id) AS patient_count,"
            "(SELECT COUNT(*) FROM visits v WHERE v.hospital_id=h.id) AS visit_count "
            "FROM hospitals h ")
    if q:
        w = "WHERE h.name LIKE ? OR h.org_id LIKE ? OR h.phone LIKE ? OR h.email LIKE ? "
        p = (f'%{q}%',)*4
        total = db.execute("SELECT COUNT(*) FROM hospitals h "+w, p).fetchone()[0]
        rows  = db.execute(base+w+"ORDER BY h.id DESC LIMIT ? OFFSET ?", p+(pp,(pg-1)*pp)).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
        rows  = db.execute(base+"ORDER BY h.id DESC LIMIT ? OFFSET ?", (pp,(pg-1)*pp)).fetchall()
    pages = max(1,(total+pp-1)//pp)
    # SA accounts for management panel
    cols = {r[1] for r in db.execute('PRAGMA table_info(super_admins)')}
    if 'email' in cols:
        sa_list = db.execute('SELECT id,email,name,is_active FROM super_admins ORDER BY id').fetchall()
    else:
        sa_list = db.execute('SELECT id,username AS email,id AS name,1 AS is_active FROM super_admins ORDER BY id').fetchall()
    return render_template('admin/hospital_list.html',
                           hospitals=[dict(r) for r in rows],
                           search=q, page=pg, total_pages=pages, total=total,
                           sa_users=[dict(s) for s in sa_list])

# ── Create hospital ───────────────────────────────────────────
@super_admin_routes.route('/hospitals/create', methods=['GET','POST'])
@_sa
def create_hospital():
    db = get_db()
    count = db.execute('SELECT COUNT(*) FROM hospitals').fetchone()[0]
    if request.method == 'POST':
        f = request.form
        org_id = f.get('org_id','').strip() or f'ORG-{count+1:03d}'
        if db.execute('SELECT id FROM hospitals WHERE org_id=?',(org_id,)).fetchone():
            org_id = f'{org_id}-{count+1}'
        hid = db.execute(
            'INSERT INTO hospitals (org_id,name,tagline,address,phone,email,color1,color2) VALUES (?,?,?,?,?,?,?,?)',
            [org_id, f.get('name','').strip(), f.get('tagline','Quality Healthcare').strip(),
             f.get('address','').strip(), f.get('phone','').strip(), f.get('email','').strip(),
             f.get('color1','#1a6fad'), f.get('color2','#0e9f8b')]
        ).lastrowid
        db.execute('INSERT INTO settings (hospital_id,doctor_name,doctor_degree) VALUES (?,?,?)',
                   [hid, f.get('doctor_name','').strip(), f.get('doctor_degree','MBBS, MD').strip()])
        wid = db.execute('INSERT INTO wards (hospital_id,name,ward_type,total_beds) VALUES (?,?,?,?)',
                         (hid,'General Ward','General',5)).lastrowid
        for i in range(1,6):
            db.execute('INSERT INTO beds (hospital_id,ward_id,bed_number,status) VALUES (?,?,?,?)',
                       (hid,wid,f'B{i:03d}','available'))
        un = f.get('admin_username','').strip()
        pw = f.get('admin_password','demo').strip() or 'demo'
        nm = f.get('admin_name','Hospital Admin').strip()
        if un:
            try:
                db.execute('INSERT INTO users (hospital_id,username,password_hash,role,name) VALUES (?,?,?,?,?)',
                           [hid,un,_h(pw),'admin',nm])
            except Exception:
                db.rollback()
                flash(f'Username "{un}" already taken.','danger')
                return redirect(url_for('super_admin.create_hospital'))
        db.commit()
        flash(f'Hospital created! Org ID: {org_id}  |  Login: {un} / {pw}','success')
        return redirect(url_for('super_admin.hospital_list'))
    return render_template('admin/create_hospital.html', next_org=f'ORG-{count+1:03d}')

# ── Hospital detail / edit ────────────────────────────────────
@super_admin_routes.route('/hospitals/<int:hid>', methods=['GET','POST'])
@_sa
def hospital_detail(hid):
    db = get_db()
    hosp = db.execute('SELECT * FROM hospitals WHERE id=?',(hid,)).fetchone()
    if not hosp: flash('Not found.','danger'); return redirect(url_for('super_admin.hospital_list'))
    if request.method == 'POST':
        action = request.form.get('action'); f = request.form
        if action == 'update_hospital':
            db.execute('UPDATE hospitals SET name=?,tagline=?,address=?,phone=?,email=?,color1=?,color2=?,is_active=? WHERE id=?',
                [f.get('name','').strip(),f.get('tagline','').strip(),f.get('address','').strip(),
                 f.get('phone','').strip(),f.get('email','').strip(),
                 f.get('color1','#1a6fad'),f.get('color2','#0e9f8b'),
                 1 if f.get('is_active') else 0,hid]); db.commit(); flash('Updated.','success')
        elif action == 'add_user':
            try:
                db.execute('INSERT INTO users (hospital_id,username,password_hash,role,name) VALUES (?,?,?,?,?)',
                    [hid,f.get('username','').strip(),_h(f.get('password','demo') or 'demo'),
                     f.get('role','nurse'),f.get('name','').strip()])
                db.commit(); flash('User created. Default password: demo','success')
            except Exception: flash('Username already exists.','danger')
        elif action == 'reset_user_pw':
            uid = f.get('user_id',type=int)
            if uid:
                db.execute('UPDATE users SET password_hash=? WHERE id=? AND hospital_id=?',
                    (_h(f.get('new_password','demo') or 'demo'),uid,hid)); db.commit(); flash('Password reset.','success')
        elif action == 'toggle_active':
            cur = db.execute('SELECT is_active FROM hospitals WHERE id=?',(hid,)).fetchone()
            db.execute('UPDATE hospitals SET is_active=? WHERE id=?',(0 if cur['is_active'] else 1,hid))
            db.commit(); flash('Status updated.','success')
        return redirect(url_for('super_admin.hospital_detail', hid=hid))
    users = db.execute("SELECT * FROM users WHERE hospital_id=? AND role!='patient' ORDER BY role,name",(hid,)).fetchall()
    stats = {
        'patients': db.execute('SELECT COUNT(*) FROM patients WHERE hospital_id=?',(hid,)).fetchone()[0],
        'visits':   db.execute('SELECT COUNT(*) FROM visits WHERE hospital_id=?',(hid,)).fetchone()[0],
        'staff':    db.execute("SELECT COUNT(*) FROM users WHERE hospital_id=? AND role!='patient'",(hid,)).fetchone()[0],
    }
    return render_template('admin/hospital_detail.html', hosp=dict(hosp), users=[dict(u) for u in users], stats=stats)

# ── Visit hospital — SEAMLESS, no re-login ────────────────────
@super_admin_routes.route('/hospitals/<int:hid>/visit')
@_sa
def visit_hospital(hid):
    db = get_db()
    hosp = db.execute('SELECT * FROM hospitals WHERE id=?',(hid,)).fetchone()
    if not hosp: flash('Not found.','danger'); return redirect(url_for('super_admin.hospital_list'))
    admin = db.execute("SELECT * FROM users WHERE hospital_id=? AND role='admin' LIMIT 1",(hid,)).fetchone()
    if not admin:
        # Auto-create a system admin user for this hospital so SA can access it
        try:
            un = f'admin_h{hid}'
            db.execute('INSERT INTO users (hospital_id,username,password_hash,role,name) VALUES (?,?,?,?,?)',
                       [hid, un, _h('demo'), 'admin', 'Hospital Admin'])
            db.commit()
            admin = db.execute("SELECT * FROM users WHERE hospital_id=? AND role='admin' LIMIT 1",(hid,)).fetchone()
        except Exception:
            flash('Could not create admin user for this hospital.','danger')
            return redirect(url_for('super_admin.hospital_detail', hid=hid))
    # Stash SA identity so "Return" works
    session['_sa_return']   = True
    session['_sa_id']       = session.get('sa_id')
    session['_sa_name']     = session.get('name')
    session['_sa_username'] = session.get('username')
    # Switch into hospital admin context
    session['user_id']    = admin['id']
    session['username']   = admin['username']
    session['role']       = admin['role']
    session['name']       = admin['name']
    session['patient_id'] = None
    session['hospital_id']= hid
    flash(f'Viewing <strong>{hosp["name"]}</strong> '
          f'<code style="background:rgba(255,255,255,.15);border-radius:4px;padding:1px 6px">{hosp["org_id"]}</code> '
          f'as Super Admin. <a href="/admin/return" class="alert-link fw-semibold">Return to Admin Panel</a>',
          'info')
    return redirect(url_for('auth.dashboard'))

# ── Return to SA panel ────────────────────────────────────────
@super_admin_routes.route('/return')
def return_to_admin():
    sa_id = session.get('_sa_id')
    sa_name = session.get('_sa_name','Super Admin')
    sa_un   = session.get('_sa_username','')
    if not sa_id:
        # Not coming from SA visit, just go to SA login
        session.clear()
        return redirect(url_for('super_admin.sa_login'))
    session.clear()
    session['role']     = 'super_admin'
    session['sa_id']    = sa_id
    session['name']     = sa_name
    session['username'] = sa_un
    return redirect(url_for('super_admin.hospital_list'))

# ── Manage super admin accounts ───────────────────────────────
@super_admin_routes.route('/sa/add', methods=['POST'])
@_sa
def add_sa():
    email = request.form.get('email','').strip().lower()
    name  = request.form.get('name','').strip() or 'Super Admin'
    if not _email_ok(email):
        flash('Invalid email.','danger')
        return redirect(url_for('super_admin.hospital_list'))
    db = get_db()
    try:
        db.execute('INSERT INTO super_admins (email,password_hash,name) VALUES (?,?,?)',
                   (email, _h('demo'), name))
        db.commit()
        flash(f'Added: {email}  |  Default password: demo','success')
    except Exception:
        flash('Email already exists.','danger')
    return redirect(url_for('super_admin.hospital_list'))

@super_admin_routes.route('/sa/<int:sid>/toggle', methods=['POST'])
@_sa
def toggle_sa(sid):
    if sid == session.get('sa_id'):
        flash('Cannot disable your own account.','warning')
        return redirect(url_for('super_admin.hospital_list'))
    db  = get_db()
    cur = db.execute('SELECT is_active FROM super_admins WHERE id=?',(sid,)).fetchone()
    if cur:
        db.execute('UPDATE super_admins SET is_active=? WHERE id=?',(0 if cur['is_active'] else 1,sid))
        db.commit(); flash('Updated.','success')
    return redirect(url_for('super_admin.hospital_list'))

@super_admin_routes.route('/sa/<int:sid>/reset', methods=['POST'])
@_sa
def reset_sa(sid):
    pw = request.form.get('new_password','demo').strip() or 'demo'
    db = get_db()
    db.execute('UPDATE super_admins SET password_hash=? WHERE id=?',(_h(pw),sid))
    db.commit(); flash('Password reset.','success')
    return redirect(url_for('super_admin.hospital_list'))

@super_admin_routes.route('/sa/<int:sid>/delete', methods=['POST'])
@_sa
def delete_sa(sid):
    if sid == session.get('sa_id'):
        flash('Cannot delete your own account.','warning')
        return redirect(url_for('super_admin.hospital_list'))
    db = get_db()
    db.execute('DELETE FROM super_admins WHERE id=?',(sid,))
    db.commit(); flash('Deleted.','success')
    return redirect(url_for('super_admin.hospital_list'))
