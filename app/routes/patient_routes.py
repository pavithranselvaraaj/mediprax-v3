from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from ..database import get_db
from datetime import date, datetime

patient_routes = Blueprint('patients', __name__, url_prefix='/patients')

def _hid(): return session.get('hospital_id', 1)
def _can_write(): return session.get('role') in ('admin','doctor')

def _calc_age(dob_str):
    if not dob_str: return None
    try:
        dob = datetime.strptime(dob_str,'%Y-%m-%d').date()
        t   = date.today()
        return t.year - dob.year - ((t.month,t.day) < (dob.month,dob.day))
    except: return None

def _safe(row, keys):
    if row is None: return {k: None for k in keys}
    d = {}
    for k in keys:
        try: d[k] = row[k]
        except: d[k] = None
    return d

def _next_uhid(db, hid):
    count = db.execute('SELECT COUNT(*) FROM patients WHERE hospital_id=?', (hid,)).fetchone()[0]
    return f"PT-{hid:02d}-{count+1:05d}"

PATIENT_KEYS = [
    'id','hospital_id','uhid','name','dob','age','gender',
    'guardian_name','guardian_relation','emergency_contact','emergency_phone',
    'insurance','insurance_no','blood_group','rh_factor','height_cm',
    'address','city','state','phone','email','individual_number',
    'occupation','marital_status','religion','nationality',
    'comorbidity','known_allergies','past_medical_history',
    'past_surgical_history','family_history','habits',
    'patient_type','created_at','updated_at'
]

VISIT_KEYS = [
    'id','patient_id','hospital_id','admission_id','visit_type','token_no',
    'visit_date','visit_time','doctor_id','complaints','history_of_illness',
    'examination_findings','primary_diagnosis','secondary_diagnosis',
    'investigation','prescription','notes','advice',
    'bp_systolic','bp_diastolic','pulse','temperature','weight',
    'height','spo2','rr','blood_sugar','followup_date','followup_notes','created_at'
]

@patient_routes.route('/')
def patients():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    if 'hospital_id' not in session: session.clear(); return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    q   = request.args.get('q','').strip()
    ptype = request.args.get('type','')
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 15

    where = "WHERE p.hospital_id=?"
    params = [hid]
    if q:
        where += " AND (p.name LIKE ? OR p.phone LIKE ? OR p.uhid LIKE ? OR p.individual_number LIKE ? OR CAST(p.id AS TEXT) LIKE ?)"
        params += [f'%{q}%']*5
    if ptype:
        where += " AND p.patient_type=?"
        params.append(ptype)

    total = db.execute(f"SELECT COUNT(*) FROM patients p {where}", params).fetchone()[0]
    rows  = db.execute(
        f"SELECT p.* FROM patients p {where} ORDER BY p.id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page-1)*per_page]
    ).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('patients.html',
                           patients=[_safe(r, PATIENT_KEYS) for r in rows],
                           search=q, ptype=ptype,
                           page=page, total_pages=total_pages, total=total)


@patient_routes.route('/add', methods=['GET','POST'])
def add_patient_view():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    if 'hospital_id' not in session: session.clear(); return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('patients.patients'))
    hid = _hid()
    if request.method == 'POST':
        f   = request.form
        dob = f.get('dob','').strip() or None
        age = _calc_age(dob) or f.get('age', type=int)
        db  = get_db()
        uhid = _next_uhid(db, hid)
        db.execute('''INSERT INTO patients
            (hospital_id,uhid,name,dob,age,gender,guardian_name,guardian_relation,
             emergency_contact,emergency_phone,insurance,insurance_no,blood_group,rh_factor,
             height_cm,address,city,state,phone,email,individual_number,
             occupation,marital_status,religion,nationality,
             comorbidity,known_allergies,past_medical_history,
             past_surgical_history,family_history,habits,patient_type)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
            hid, uhid, f.get('name','').strip(), dob, age,
            f.get('gender'), f.get('guardian_name','').strip(),
            f.get('guardian_relation','').strip(),
            f.get('emergency_contact','').strip(),
            f.get('emergency_phone','').strip(),
            f.get('insurance','').strip(), f.get('insurance_no','').strip(),
            f.get('blood_group'), f.get('rh_factor',''),
            f.get('height_cm', type=int),
            f.get('address','').strip(), f.get('city','').strip(), f.get('state','').strip(),
            f.get('phone','').strip(), f.get('email','').strip(),
            f.get('individual_number','').strip(),
            f.get('occupation','').strip(), f.get('marital_status',''),
            f.get('religion','').strip(), f.get('nationality','Indian').strip(),
            f.get('comorbidity','').strip(), f.get('known_allergies','').strip(),
            f.get('past_medical_history','').strip(),
            f.get('past_surgical_history','').strip(),
            f.get('family_history','').strip(), f.get('habits','').strip(),
            f.get('patient_type','OPD'),
        ])
        db.commit()
        flash(f'Patient registered successfully! UHID: {uhid}', 'success')
        return redirect(url_for('patients.patients'))
    return render_template('patient_form.html', patient=None, action='Add')


@patient_routes.route('/<int:pid>')
def patient_detail(pid):
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    if 'hospital_id' not in session: session.clear(); return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    if session.get('role') == 'patient' and session.get('patient_id') != pid:
        flash('Access denied.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=session['patient_id']))
    raw_pt = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid,hid)).fetchone()
    if not raw_pt:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patients.patients'))
    patient = _safe(raw_pt, PATIENT_KEYS)

    visits = [_safe(v, VISIT_KEYS) for v in db.execute(
        'SELECT * FROM visits WHERE patient_id=? AND hospital_id=? ORDER BY visit_date DESC, id DESC', (pid,hid)
    ).fetchall()]

    admissions = db.execute('''
        SELECT a.*, w.name AS ward_name, b.bed_number,
               u.name AS doctor_name
        FROM admissions a
        LEFT JOIN wards w ON a.ward_id=w.id
        LEFT JOIN beds  b ON a.bed_id=b.id
        LEFT JOIN users u ON a.admitting_doctor_id=u.id
        WHERE a.patient_id=? AND a.hospital_id=?
        ORDER BY a.admission_date DESC
    ''', (pid,hid)).fetchall()

    lab_orders = db.execute('''
        SELECT o.*, GROUP_CONCAT(t.test_name, ', ') AS tests
        FROM lab_orders o
        LEFT JOIN lab_tests t ON t.lab_order_id=o.id
        WHERE o.patient_id=? AND o.hospital_id=?
        GROUP BY o.id ORDER BY o.order_date DESC
    ''', (pid,hid)).fetchall()

    bills = db.execute(
        'SELECT * FROM bills WHERE patient_id=? AND hospital_id=? ORDER BY bill_date DESC', (pid,hid)
    ).fetchall()

    display_age = _calc_age(patient['dob']) or patient['age']
    patient_user = db.execute(
        "SELECT * FROM users WHERE patient_id=? AND hospital_id=? AND role='patient'", (pid,hid)
    ).fetchone()

    return render_template('patient_detail.html',
                           patient=patient, display_age=display_age,
                           visits=visits, admissions=[dict(a) for a in admissions],
                           lab_orders=[dict(l) for l in lab_orders],
                           bills=[dict(b) for b in bills],
                           patient_user=patient_user)


@patient_routes.route('/<int:pid>/edit', methods=['GET','POST'])
def edit_patient(pid):
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    hid = _hid()
    db  = get_db()
    patient = _safe(db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid,hid)).fetchone(), PATIENT_KEYS)
    if request.method == 'POST':
        f   = request.form
        dob = f.get('dob','').strip() or None
        age = _calc_age(dob) or f.get('age', type=int)
        db.execute('''UPDATE patients SET
            name=?,dob=?,age=?,gender=?,guardian_name=?,guardian_relation=?,
            emergency_contact=?,emergency_phone=?,insurance=?,insurance_no=?,
            blood_group=?,rh_factor=?,height_cm=?,address=?,city=?,state=?,
            phone=?,email=?,individual_number=?,occupation=?,marital_status=?,
            religion=?,nationality=?,comorbidity=?,known_allergies=?,
            past_medical_history=?,past_surgical_history=?,family_history=?,
            habits=?,patient_type=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND hospital_id=?''', [
            f.get('name','').strip(), dob, age, f.get('gender'),
            f.get('guardian_name','').strip(), f.get('guardian_relation','').strip(),
            f.get('emergency_contact','').strip(), f.get('emergency_phone','').strip(),
            f.get('insurance','').strip(), f.get('insurance_no','').strip(),
            f.get('blood_group'), f.get('rh_factor',''),
            f.get('height_cm', type=int),
            f.get('address','').strip(), f.get('city','').strip(), f.get('state','').strip(),
            f.get('phone','').strip(), f.get('email','').strip(),
            f.get('individual_number','').strip(),
            f.get('occupation','').strip(), f.get('marital_status',''),
            f.get('religion','').strip(), f.get('nationality','Indian').strip(),
            f.get('comorbidity','').strip(), f.get('known_allergies','').strip(),
            f.get('past_medical_history','').strip(),
            f.get('past_surgical_history','').strip(),
            f.get('family_history','').strip(), f.get('habits','').strip(),
            f.get('patient_type','OPD'), pid, hid
        ])
        db.commit()
        from silent_backup import backup; backup()
        flash('Patient updated.', 'success')
        return redirect(url_for('patients.patient_detail', pid=pid))
    return render_template('patient_form.html', patient=patient, action='Edit')


@patient_routes.route('/api')
def patients_api():
    hid = session.get('hospital_id', 1)
    if not hid: return jsonify([])
    db  = get_db()
    q   = request.args.get('q','').strip()
    if q:
        rows = db.execute(
            'SELECT id,name,uhid,phone,blood_group,age,gender FROM patients '
            'WHERE hospital_id=? AND (name LIKE ? OR uhid LIKE ? OR phone LIKE ?) ORDER BY name LIMIT 20',
            (hid, f'%{q}%', f'%{q}%', f'%{q}%')
        ).fetchall()
    else:
        rows = db.execute('SELECT id,name,uhid,phone,blood_group,age,gender FROM patients WHERE hospital_id=? ORDER BY name', (hid,)).fetchall()
    return jsonify([dict(r) for r in rows])
