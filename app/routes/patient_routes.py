from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from ..database import get_db
from datetime import date, datetime

patient_routes = Blueprint('patients', __name__, url_prefix='/patients')

def _hid(): return session.get('hospital_id', 1)
def _ok():  return 'user_id' in session and 'hospital_id' in session
def _rw():  return session.get('role') in ('admin','doctor')

def _age(dob):
    if not dob: return None
    try:
        d = datetime.strptime(dob,'%Y-%m-%d').date(); t = date.today()
        return t.year-d.year-((t.month,t.day)<(d.month,d.day))
    except: return None

def _safe(row, keys):
    if not row: return {k:None for k in keys}
    d = {}
    for k in keys:
        try: d[k] = row[k]
        except: d[k] = None
    return d

def _next_uhid(db, hid):
    n = db.execute('SELECT COUNT(*) FROM patients WHERE hospital_id=?',(hid,)).fetchone()[0]
    return f'PT-{hid:02d}-{n+1:05d}'

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
         'height','spo2','rr','blood_sugar','followup_date','followup_notes']

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
        dob = f.get('dob','').strip() or None
        age = _age(dob) or f.get('age',type=int)
        uhid = _next_uhid(db, hid)
        org_id = db.execute('SELECT org_id FROM hospitals WHERE id=?',(hid,)).fetchone()['org_id']
        db.execute('''INSERT INTO patients
            (hospital_id,org_id,uhid,name,dob,age,gender,guardian_name,guardian_relation,
             emergency_contact,emergency_phone,insurance,insurance_no,blood_group,height_cm,
             address,city,state,phone,email,individual_number,occupation,marital_status,
             nationality,comorbidity,known_allergies,past_medical_history,past_surgical_history,
             family_history,habits,patient_type)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
            hid,org_id,uhid,f.get('name','').strip(),dob,age,f.get('gender'),
            f.get('guardian_name','').strip(),f.get('guardian_relation','').strip(),
            f.get('emergency_contact','').strip(),f.get('emergency_phone','').strip(),
            f.get('insurance','').strip(),f.get('insurance_no','').strip(),
            f.get('blood_group'),f.get('height_cm',type=int),
            f.get('address','').strip(),f.get('city','').strip(),f.get('state','').strip(),
            f.get('phone','').strip(),f.get('email','').strip(),
            f.get('individual_number','').strip(),f.get('occupation','').strip(),
            f.get('marital_status',''),f.get('nationality','Indian').strip(),
            f.get('comorbidity','').strip(),f.get('known_allergies','').strip(),
            f.get('past_medical_history','').strip(),f.get('past_surgical_history','').strip(),
            f.get('family_history','').strip(),f.get('habits','').strip(),
            f.get('patient_type','OPD')
        ])
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
        dob = f.get('dob','').strip() or None
        age = _age(dob) or f.get('age',type=int)
        db.execute('''UPDATE patients SET
            name=?,dob=?,age=?,gender=?,guardian_name=?,guardian_relation=?,
            emergency_contact=?,emergency_phone=?,insurance=?,insurance_no=?,
            blood_group=?,height_cm=?,address=?,city=?,state=?,phone=?,email=?,
            individual_number=?,occupation=?,marital_status=?,nationality=?,
            comorbidity=?,known_allergies=?,past_medical_history=?,
            past_surgical_history=?,family_history=?,habits=?,patient_type=?,
            updated_at=CURRENT_TIMESTAMP WHERE id=? AND hospital_id=?''', [
            f.get('name','').strip(),dob,age,f.get('gender'),
            f.get('guardian_name','').strip(),f.get('guardian_relation','').strip(),
            f.get('emergency_contact','').strip(),f.get('emergency_phone','').strip(),
            f.get('insurance','').strip(),f.get('insurance_no','').strip(),
            f.get('blood_group'),f.get('height_cm',type=int),
            f.get('address','').strip(),f.get('city','').strip(),f.get('state','').strip(),
            f.get('phone','').strip(),f.get('email','').strip(),
            f.get('individual_number','').strip(),f.get('occupation','').strip(),
            f.get('marital_status',''),f.get('nationality','Indian').strip(),
            f.get('comorbidity','').strip(),f.get('known_allergies','').strip(),
            f.get('past_medical_history','').strip(),f.get('past_surgical_history','').strip(),
            f.get('family_history','').strip(),f.get('habits','').strip(),
            f.get('patient_type','OPD'),pid,hid])
        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception: pass
        flash('Updated.','success'); return redirect(url_for('patients.patient_detail',pid=pid))
    return render_template('patient_form.html', patient=patient, action='Edit')

@patient_routes.route('/api')
def patients_api():
    if not _ok(): return jsonify([])
    hid = _hid(); q = request.args.get('q','').strip(); db = get_db()
    if q:
        rows = db.execute('SELECT id,name,uhid,phone,blood_group,age,gender FROM patients WHERE hospital_id=? AND (name LIKE ? OR uhid LIKE ? OR phone LIKE ?) ORDER BY name LIMIT 20',
                          (hid,f'%{q}%',f'%{q}%',f'%{q}%')).fetchall()
    else:
        rows = db.execute('SELECT id,name,uhid,phone,blood_group,age,gender FROM patients WHERE hospital_id=? ORDER BY name',(hid,)).fetchall()
    return jsonify([dict(r) for r in rows])
