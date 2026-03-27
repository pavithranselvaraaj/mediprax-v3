from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from ..database import get_db
from datetime import date, datetime

ipd_routes = Blueprint('ipd', __name__, url_prefix='/ipd')

def _hid(): return session.get('hospital_id', 1)
def _login(): return 'user_id' in session and 'hospital_id' in session
def _can_write(): return session.get('role') in ('admin','doctor')

def _next_admission_no(db, hid):
    count = db.execute('SELECT COUNT(*) FROM admissions WHERE hospital_id=?', (hid,)).fetchone()[0]
    return f"ADM-{hid:02d}-{count+1:05d}"

# ── Admit patient ─────────────────────────────────────────────

@ipd_routes.route('/admit/<int:pid>', methods=['GET','POST'])
def admit_patient(pid):
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    hid = _hid()
    db  = get_db()
    patient = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid, hid)).fetchone()
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patients.patients'))

    wards = db.execute('SELECT * FROM wards WHERE hospital_id=? ORDER BY name', (hid,)).fetchall()
    available_beds = db.execute('''
        SELECT b.*, w.name AS ward_name FROM beds b
        JOIN wards w ON b.ward_id=w.id
        WHERE b.hospital_id=? AND b.status='available'
        ORDER BY w.name, b.bed_number
    ''', (hid,)).fetchall()
    doctors = db.execute("SELECT id,name FROM users WHERE hospital_id=? AND role IN ('admin','doctor') ORDER BY name", (hid,)).fetchall()

    if request.method == 'POST':
        f = request.form
        bed_id  = f.get('bed_id', type=int)
        ward_id = f.get('ward_id', type=int)
        adm_no  = _next_admission_no(db, hid)

        db.execute('''INSERT INTO admissions
            (hospital_id,patient_id,admission_no,admission_type,ward_id,bed_id,
             admitting_doctor_id,diagnosis_at_admission,
             attendant_name,attendant_phone,attendant_relation,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'admitted')''', [
            hid, pid, adm_no,
            f.get('admission_type','Elective'),
            ward_id, bed_id,
            f.get('doctor_id', type=int),
            f.get('diagnosis_at_admission','').strip(),
            f.get('attendant_name','').strip(),
            f.get('attendant_phone','').strip(),
            f.get('attendant_relation','').strip(),
        ])
        # Mark bed as occupied
        if bed_id:
            db.execute("UPDATE beds SET status='occupied' WHERE id=?", (bed_id,))
        # Update patient type
        db.execute("UPDATE patients SET patient_type='IPD' WHERE id=?", (pid,))
        db.commit()
        from silent_backup import backup; backup()
        flash(f'Patient admitted successfully! Admission No: {adm_no}', 'success')
        return redirect(url_for('patients.patient_detail', pid=pid))

    return render_template('ipd/admit_form.html',
                           patient=dict(patient),
                           wards=[dict(w) for w in wards],
                           available_beds=[dict(b) for b in available_beds],
                           doctors=[dict(d) for d in doctors],
                           today=datetime.now().strftime('%Y-%m-%dT%H:%M'))


# ── Discharge patient ─────────────────────────────────────────

@ipd_routes.route('/discharge/<int:adm_id>', methods=['GET','POST'])
def discharge_patient(adm_id):
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('auth.dashboard'))
    hid = _hid()
    db  = get_db()
    adm = db.execute('''
        SELECT a.*, p.name AS patient_name, p.id AS patient_id,
               w.name AS ward_name, b.bed_number
        FROM admissions a
        JOIN patients p ON a.patient_id=p.id
        LEFT JOIN wards w ON a.ward_id=w.id
        LEFT JOIN beds  b ON a.bed_id=b.id
        WHERE a.id=? AND a.hospital_id=?
    ''', (adm_id, hid)).fetchone()
    if not adm:
        flash('Admission not found.', 'danger')
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        f = request.form
        db.execute('''UPDATE admissions SET
            status=?, discharge_date=CURRENT_TIMESTAMP,
            discharge_type=?, discharge_summary=?,
            final_diagnosis=?, discharge_instructions=?,
            condition_at_discharge=?
            WHERE id=? AND hospital_id=?''', [
            'discharged',
            f.get('discharge_type','Recovered'),
            f.get('discharge_summary','').strip(),
            f.get('final_diagnosis','').strip(),
            f.get('discharge_instructions','').strip(),
            f.get('condition_at_discharge','Stable'),
            adm_id, hid
        ])
        # Free the bed
        if adm['bed_id']:
            db.execute("UPDATE beds SET status='available' WHERE id=?", (adm['bed_id'],))
        # Update patient type back to OPD
        db.execute("UPDATE patients SET patient_type='OPD' WHERE id=?", (adm['patient_id'],))
        db.commit()
        from silent_backup import backup; backup()
        flash('Patient discharged successfully.', 'success')
        return redirect(url_for('patients.patient_detail', pid=adm['patient_id']))

    return render_template('ipd/discharge_form.html', adm=dict(adm))


# ── IPD ward view ─────────────────────────────────────────────

@ipd_routes.route('/ward')
def ward_view():
    if not _login(): return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    wards = db.execute('SELECT * FROM wards WHERE hospital_id=? ORDER BY name', (hid,)).fetchall()
    bed_data = []
    for w in wards:
        beds = db.execute('''
            SELECT b.*,
                   a.id AS adm_id, a.admission_date, a.diagnosis_at_admission,
                   p.name AS patient_name, p.id AS patient_id, p.uhid, p.age, p.gender
            FROM beds b
            LEFT JOIN admissions a ON b.id=a.bed_id AND a.status='admitted' AND a.hospital_id=?
            LEFT JOIN patients p ON a.patient_id=p.id
            WHERE b.ward_id=? AND b.hospital_id=?
            ORDER BY b.bed_number
        ''', (hid, w['id'], hid)).fetchall()
        available = sum(1 for b in beds if b['status'] == 'available')
        occupied  = sum(1 for b in beds if b['status'] == 'occupied')
        bed_data.append({
            'ward': dict(w),
            'beds': [dict(b) for b in beds],
            'available': available,
            'occupied':  occupied,
        })
    stats = {
        'total_beds':     db.execute('SELECT COUNT(*) FROM beds WHERE hospital_id=?', (hid,)).fetchone()[0],
        'available_beds': db.execute("SELECT COUNT(*) FROM beds WHERE hospital_id=? AND status='available'", (hid,)).fetchone()[0],
        'occupied_beds':  db.execute("SELECT COUNT(*) FROM beds WHERE hospital_id=? AND status='occupied'", (hid,)).fetchone()[0],
        'total_admitted': db.execute("SELECT COUNT(*) FROM admissions WHERE hospital_id=? AND status='admitted'", (hid,)).fetchone()[0],
    }
    return render_template('ipd/ward_view.html', bed_data=bed_data, stats=stats)


# ── Manage wards + beds ───────────────────────────────────────

@ipd_routes.route('/beds/manage', methods=['GET','POST'])
def manage_beds():
    if not _login(): return redirect(url_for('auth.login'))
    if session.get('role') != 'admin':
        flash('Admin only.', 'danger')
        return redirect(url_for('ipd.ward_view'))
    hid = _hid()
    db  = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_ward':
            db.execute('INSERT INTO wards (hospital_id,name,ward_type,total_beds) VALUES (?,?,?,?)', [
                hid, request.form['name'].strip(),
                request.form.get('ward_type','General'),
                request.form.get('total_beds', type=int) or 0
            ])
            db.commit()
            flash('Ward added.', 'success')
        elif action == 'add_bed':
            wid = request.form.get('ward_id', type=int)
            db.execute('INSERT INTO beds (hospital_id,ward_id,bed_number,status) VALUES (?,?,?,?)', [
                hid, wid, request.form['bed_number'].strip(), 'available'
            ])
            db.commit()
            flash('Bed added.', 'success')
        elif action == 'update_bed_status':
            bid    = request.form.get('bed_id', type=int)
            status = request.form.get('status','available')
            db.execute('UPDATE beds SET status=? WHERE id=? AND hospital_id=?', (status, bid, hid))
            db.commit()
            flash('Bed status updated.', 'success')
        return redirect(url_for('ipd.manage_beds'))

    wards = db.execute('SELECT * FROM wards WHERE hospital_id=? ORDER BY name', (hid,)).fetchall()
    beds  = db.execute('''
        SELECT b.*, w.name AS ward_name FROM beds b
        JOIN wards w ON b.ward_id=w.id
        WHERE b.hospital_id=? ORDER BY w.name, b.bed_number
    ''', (hid,)).fetchall()
    return render_template('ipd/manage_beds.html',
                           wards=[dict(w) for w in wards],
                           beds=[dict(b) for b in beds])


# ── Beds API for AJAX ────────────────────────────────────────

@ipd_routes.route('/api/beds')
def api_beds():
    if not _login(): return jsonify([])
    hid     = _hid()
    ward_id = request.args.get('ward_id', type=int)
    db      = get_db()
    q = 'SELECT b.*,w.name AS ward_name FROM beds b JOIN wards w ON b.ward_id=w.id WHERE b.hospital_id=? AND b.status="available"'
    params = [hid]
    if ward_id:
        q += ' AND b.ward_id=?'
        params.append(ward_id)
    return jsonify([dict(b) for b in db.execute(q, params).fetchall()])
