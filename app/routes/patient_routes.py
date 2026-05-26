from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from ..database import get_db
from datetime import date, datetime
from ..utils.validators import (
    validate_phone, normalize_phone, validate_email, validate_date, validate_gender,
    validate_name, validate_aadhar, validate_dob, safe_int
)

patient_routes = Blueprint('patients', __name__, url_prefix='/patients')

def _hid(): return session.get('hospital_id', 1)
def _ok():  return 'user_id' in session and 'hospital_id' in session
def _rw():  return session.get('role') in ('admin','doctor')

def _age(dob):
    if not dob: return None
    try:
        d = datetime.strptime(dob,'%Y-%m-%d').date(); t = date.today()
        return t.year-d.year-((t.month,t.day)<(d.month,d.day))
    except Exception:
        return None

def _safe(row, keys):
    if not row: return {k:None for k in keys}
    d = {}
    for k in keys:
        try:
            val = row[k]
            # Normalize legacy string 'None' values stored in DB
            if isinstance(val, str) and val.strip().lower() == 'none':
                val = None
            d[k] = val
        except Exception:
            d[k] = None
    return d

def _build_uhid(hid, pid):
    return f'PT-{hid:02d}-{pid:05d}'

PKEYS = ['id','hospital_id','org_id','uhid','name','dob','age','gender',
         'guardian_name','guardian_relation','emergency_contact','emergency_phone',
         'insurance','insurance_no','blood_group','height_cm',
         'address','city','state','phone','email','individual_number',
         'occupation','marital_status','nationality','comorbidity',
         'known_allergies','past_medical_history','past_surgical_history',
         'family_history','habits','patient_type','created_at']
VKEYS = ['id','patient_id','hospital_id','visit_type','token_no','visit_date',
         'visit_time','doctor_id','complaints','history_of_illness',
         'examination_findings','primary_diagnosis','secondary_diagnosis',
         'investigation','prescription','advice','notes',
         'bp_systolic','bp_diastolic','pulse','temperature','weight',
         'height','spo2','rr','blood_sugar','followup_date','followup_notes',
         'prescription_image']

@patient_routes.route('/')
def patients():
    if not _ok(): return redirect(url_for('auth.login'))
    hid = _hid(); db = get_db()
    q = request.args.get('q','').strip()
    ptype = request.args.get('type','')
    pg = max(1,request.args.get('page',1,type=int)); pp = 15
    where = 'WHERE p.hospital_id=?'; params = [hid]
    if q:
        where += ' AND (p.name LIKE ? OR p.phone LIKE ? OR p.uhid LIKE ? OR p.individual_number LIKE ? OR CAST(p.id AS TEXT) LIKE ?)'
        params += [f'%{q}%']*5
    if ptype:
        where += ' AND p.patient_type=?'; params.append(ptype)
    total = db.execute(f'SELECT COUNT(*) FROM patients p {where}',params).fetchone()[0]
    rows  = db.execute(f'SELECT p.* FROM patients p {where} ORDER BY p.id DESC LIMIT ? OFFSET ?',
                       params+[pp,(pg-1)*pp]).fetchall()
    pages = max(1,(total+pp-1)//pp)
    return render_template('patients.html', patients=[_safe(r,PKEYS) for r in rows],
                           search=q, ptype=ptype, page=pg, total_pages=pages, total=total)

@patient_routes.route('/add', methods=['GET','POST'])
def add_patient_view():
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw(): flash('Read-only access.','danger'); return redirect(url_for('patients.patients'))
    hid = _hid(); db = get_db()
    if request.method == 'POST':
        f = request.form
        name = (f.get('name') or '').strip()
        if not validate_name(name):
            flash('Name is required (2-100 letters only).','danger'); return render_template('patient_form.html', patient=f, action='Add')
        dob = (f.get('dob') or '').strip() or None
        if dob and not validate_dob(dob):
            flash('DOB must be YYYY-MM-DD and not in the future.','danger'); return render_template('patient_form.html', patient=f, action='Add')
        age = _age(dob) or safe_int(f.get('age'), default=None, min_val=0, max_val=120)
        phone = normalize_phone(f.get('phone'))
        if f.get('phone') and not validate_phone(f.get('phone')):
            flash('Enter a valid 10-digit Indian mobile number (starting with 6-9).','danger'); return render_template('patient_form.html', patient=f, action='Add')
        email = (f.get('email') or '').strip().lower()
        if email and not validate_email(email):
            flash('Invalid email format.','danger'); return render_template('patient_form.html', patient=f, action='Add')
        gender = f.get('gender')
        if gender and not validate_gender(gender):
            flash('Invalid gender.','danger'); return render_template('patient_form.html', patient=f, action='Add')
        individual_number = (f.get('individual_number') or '').strip()
        if individual_number and not validate_aadhar(individual_number):
            flash('Aadhar must be exactly 12 digits.','danger'); return render_template('patient_form.html', patient=f, action='Add')
        emergency_phone = (f.get('emergency_phone') or '').strip()
        if emergency_phone and not validate_phone(emergency_phone):
            flash('Emergency phone must be a valid 10-digit Indian mobile number.','danger'); return render_template('patient_form.html', patient=f, action='Add')
        org_id = db.execute('SELECT org_id FROM hospitals WHERE id=?',(hid,)).fetchone()['org_id']
        emergency_phone_n = normalize_phone(emergency_phone) or emergency_phone
        cur = db.execute('''INSERT INTO patients
            (hospital_id,org_id,uhid,name,dob,age,gender,guardian_name,guardian_relation,
             emergency_contact,emergency_phone,insurance,insurance_no,blood_group,height_cm,
             address,city,state,phone,email,individual_number,occupation,marital_status,
             nationality,comorbidity,known_allergies,past_medical_history,past_surgical_history,
             family_history,habits,patient_type)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
            hid,org_id,None,name,dob,age,gender,
            (f.get('guardian_name') or '').strip(),(f.get('guardian_relation') or '').strip(),
            (f.get('emergency_contact') or '').strip(), emergency_phone_n,
            (f.get('insurance') or '').strip(),(f.get('insurance_no') or '').strip(),
            f.get('blood_group'), safe_int(f.get('height_cm'), default=None, min_val=30, max_val=250),
            (f.get('address') or '').strip(),(f.get('city') or '').strip(),(f.get('state') or '').strip(),
            phone, email,
            (f.get('individual_number') or '').strip(),(f.get('occupation') or '').strip(),
            f.get('marital_status',''),(f.get('nationality') or 'Indian').strip(),
            (f.get('comorbidity') or '').strip(),(f.get('known_allergies') or '').strip(),
            (f.get('past_medical_history') or '').strip(),(f.get('past_surgical_history') or '').strip(),
            (f.get('family_history') or '').strip(),(f.get('habits') or '').strip(),
            f.get('patient_type','OPD')
        ])
        # Generate UHID from the actual row id (race-free, deletion-stable)
        uhid = _build_uhid(hid, cur.lastrowid)
        db.execute('UPDATE patients SET uhid=? WHERE id=?', (uhid, cur.lastrowid))
        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception: pass
        flash(f'Patient registered! UHID: {uhid}','success')
        return redirect(url_for('patients.patients'))
    return render_template('patient_form.html', patient=None, action='Add')

@patient_routes.route('/<int:pid>')
def patient_detail(pid):
    if not _ok(): return redirect(url_for('auth.login'))
    hid = _hid(); db = get_db()
    if session.get('role') == 'patient' and session.get('patient_id') != pid:
        return redirect(url_for('patients.patient_detail', pid=session['patient_id']))
    raw = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?',(pid,hid)).fetchone()
    if not raw: flash('Not found.','danger'); return redirect(url_for('patients.patients'))
    patient = _safe(raw, PKEYS)
    visits  = [_safe(v,VKEYS) for v in db.execute(
        'SELECT * FROM visits WHERE patient_id=? AND hospital_id=? ORDER BY visit_date DESC,id DESC',(pid,hid)).fetchall()]
    admissions = [dict(r) for r in db.execute('''
        SELECT a.*,w.name AS ward_name,b.bed_number,u.name AS doctor_name
        FROM admissions a LEFT JOIN wards w ON a.ward_id=w.id
        LEFT JOIN beds b ON a.bed_id=b.id LEFT JOIN users u ON a.admitting_doctor_id=u.id
        WHERE a.patient_id=? AND a.hospital_id=? ORDER BY a.id DESC''',(pid,hid)).fetchall()]
    display_age = _age(patient['dob']) or patient['age']
    return render_template('patient_detail.html', patient=patient, display_age=display_age,
                           visits=visits, admissions=admissions)

@patient_routes.route('/<int:pid>/edit', methods=['GET','POST'])
def edit_patient(pid):
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw(): flash('Read-only.','danger'); return redirect(url_for('patients.patient_detail',pid=pid))
    hid = _hid(); db = get_db()
    patient = _safe(db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?',(pid,hid)).fetchone(), PKEYS)
    if request.method == 'POST':
        f = request.form
        name = (f.get('name') or '').strip()
        if not validate_name(name):
            flash('Name is required (2-100 letters only).','danger'); return render_template('patient_form.html', patient=patient, action='Edit')
        dob = (f.get('dob') or '').strip() or None
        if dob and not validate_dob(dob):
            flash('DOB must be YYYY-MM-DD and not in the future.','danger'); return render_template('patient_form.html', patient=patient, action='Edit')
        age = _age(dob) or safe_int(f.get('age'), default=None, min_val=0, max_val=120)
        phone = normalize_phone(f.get('phone'))
        if f.get('phone') and not validate_phone(f.get('phone')):
            flash('Enter a valid 10-digit Indian mobile number (starting with 6-9).','danger'); return render_template('patient_form.html', patient=patient, action='Edit')
        email = (f.get('email') or '').strip().lower()
        if email and not validate_email(email):
            flash('Invalid email format.','danger'); return render_template('patient_form.html', patient=patient, action='Edit')
        gender = f.get('gender')
        if gender and not validate_gender(gender):
            flash('Invalid gender.','danger'); return render_template('patient_form.html', patient=patient, action='Edit')
        individual_number = (f.get('individual_number') or '').strip()
        if individual_number and not validate_aadhar(individual_number):
            flash('Aadhar must be exactly 12 digits.','danger'); return render_template('patient_form.html', patient=patient, action='Edit')
        emergency_phone = (f.get('emergency_phone') or '').strip()
        if emergency_phone and not validate_phone(emergency_phone):
            flash('Emergency phone must be a valid 10-digit Indian mobile number.','danger'); return render_template('patient_form.html', patient=patient, action='Edit')
        emergency_phone_n = normalize_phone(emergency_phone) or emergency_phone
        db.execute('''UPDATE patients SET
            name=?,dob=?,age=?,gender=?,guardian_name=?,guardian_relation=?,
            emergency_contact=?,emergency_phone=?,insurance=?,insurance_no=?,
            blood_group=?,height_cm=?,address=?,city=?,state=?,phone=?,email=?,
            individual_number=?,occupation=?,marital_status=?,nationality=?,
            comorbidity=?,known_allergies=?,past_medical_history=?,
            past_surgical_history=?,family_history=?,habits=?,patient_type=?,
            updated_at=CURRENT_TIMESTAMP WHERE id=? AND hospital_id=?''', [
            name,dob,age,f.get('gender'),
            (f.get('guardian_name') or '').strip(),(f.get('guardian_relation') or '').strip(),
            (f.get('emergency_contact') or '').strip(), emergency_phone_n,
            (f.get('insurance') or '').strip(),(f.get('insurance_no') or '').strip(),
            f.get('blood_group'), safe_int(f.get('height_cm'), default=None, min_val=30, max_val=250),
            (f.get('address') or '').strip(),(f.get('city') or '').strip(),(f.get('state') or '').strip(),
            phone,email,
            (f.get('individual_number') or '').strip(),(f.get('occupation') or '').strip(),
            f.get('marital_status',''),(f.get('nationality') or 'Indian').strip(),
            (f.get('comorbidity') or '').strip(),(f.get('known_allergies') or '').strip(),
            (f.get('past_medical_history') or '').strip(),(f.get('past_surgical_history') or '').strip(),
            (f.get('family_history') or '').strip(),(f.get('habits') or '').strip(),
            f.get('patient_type','OPD'),pid,hid])
        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception: pass
        flash('Updated.','success'); return redirect(url_for('patients.patient_detail',pid=pid))
    return render_template('patient_form.html', patient=patient, action='Edit')

@patient_routes.route('/api')
def patients_api():
    """Patient typeahead. Always capped at 20 rows; empty q returns most-recent."""
    if not _ok():
        return jsonify({'ok': False, 'error': 'unauthorized', 'results': []}), 401
    hid = _hid()
    q = request.args.get('q', '').strip()
    db = get_db()
    if q:
        like = f'%{q}%'
        rows = db.execute(
            'SELECT id,name,uhid,phone,blood_group,age,gender FROM patients '
            'WHERE hospital_id=? AND (name LIKE ? OR uhid LIKE ? OR phone LIKE ?) '
            'ORDER BY name LIMIT 20',
            (hid, like, like, like)).fetchall()
    else:
        rows = db.execute(
            'SELECT id,name,uhid,phone,blood_group,age,gender FROM patients '
            'WHERE hospital_id=? ORDER BY id DESC LIMIT 20',
            (hid,)).fetchall()
    return jsonify({'ok': True, 'results': [dict(r) for r in rows]})
