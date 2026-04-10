from flask import Blueprint, request, render_template, redirect, url_for, session, flash, current_app
from ..database import get_db
from datetime import date, datetime
from ..utils.validators import safe_int, safe_float, validate_date, validate_time
from werkzeug.utils import secure_filename
import os, uuid

visit_routes = Blueprint('visits', __name__, url_prefix='/visits')

def _hid(): return session.get('hospital_id',1)
def _ok():  return 'user_id' in session and 'hospital_id' in session
def _rw():  return session.get('role') in ('admin','doctor')

ALLOWED_EXT = {'png','jpg','jpeg','webp'}

def _save_prescription_image(file_obj, hid, pid):
    """Save an uploaded prescription image; returns the filename or None."""
    if not file_obj or not file_obj.filename:
        return None
    ext = file_obj.filename.rsplit('.', 1)[-1].lower() if '.' in file_obj.filename else ''
    if ext not in ALLOWED_EXT:
        return None
    fname = f'{hid}_{pid}_{uuid.uuid4().hex[:8]}.{ext}'
    upload_dir = current_app.config.get('UPLOAD_FOLDER', 'static/uploads/prescriptions')
    os.makedirs(upload_dir, exist_ok=True)
    file_obj.save(os.path.join(upload_dir, fname))
    return fname

def _delete_prescription_image(filename):
    """Delete an old prescription image file from disk."""
    if not filename:
        return
    try:
        upload_dir = current_app.config.get('UPLOAD_FOLDER', 'static/uploads/prescriptions')
        path = os.path.join(upload_dir, filename)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def _sv(v):
    keys=['id','patient_id','hospital_id','visit_type','token_no','visit_date','visit_time',
          'doctor_id','complaints','history_of_illness','examination_findings',
          'primary_diagnosis','secondary_diagnosis','investigation','prescription',
          'advice','notes','bp_systolic','bp_diastolic','pulse','temperature',
          'weight','height','spo2','rr','blood_sugar','followup_date','followup_notes',
          'prescription_image']
    d = {}
    for k in keys:
        try: d[k] = v[k]
        except: d[k] = None
    return d

def _next_token(db, hid):
    today = date.today().isoformat()
    r = db.execute("SELECT MAX(token_no) FROM visits WHERE hospital_id=? AND visit_date=? AND visit_type='OPD'",(hid,today)).fetchone()
    return (r[0] or 0)+1

@visit_routes.route('/<int:pid>/add', methods=['GET','POST'])
def add_visit(pid):
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw(): flash('Read-only.','danger'); return redirect(url_for('patients.patient_detail',pid=pid))
    hid = _hid(); db = get_db()
    patient = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?',(pid,hid)).fetchone()
    if not patient: flash('Not found.','danger'); return redirect(url_for('patients.patients'))
    doctors = db.execute("SELECT id,name FROM users WHERE hospital_id=? AND role IN ('admin','doctor') ORDER BY name",(hid,)).fetchall()
    if request.method == 'POST':
        f = request.form
        vtype = f.get('visit_type','OPD')
        token = _next_token(db,hid) if vtype=='OPD' else None
        vdate = f.get('visit_date') or date.today().isoformat()
        vtime = f.get('visit_time') or datetime.now().strftime('%H:%M')
        if not validate_date(vdate):
            flash('Invalid visit date.','danger'); return render_template('visit_form.html', patient=patient, visit=None, doctors=[dict(d) for d in doctors], today=date.today().isoformat(), now_time=datetime.now().strftime('%H:%M'), next_token=_next_token(db,hid))
        if not validate_time(vtime):
            flash('Invalid visit time.','danger'); return render_template('visit_form.html', patient=patient, visit=None, doctors=[dict(d) for d in doctors], today=date.today().isoformat(), now_time=datetime.now().strftime('%H:%M'), next_token=_next_token(db,hid))
        doc_id = safe_int(f.get('doctor_id'), default=None, min_val=1)
        if doc_id:
            ok = db.execute("SELECT 1 FROM users WHERE id=? AND hospital_id=? AND role IN ('admin','doctor')",(doc_id,hid)).fetchone()
            if not ok:
                flash('Invalid doctor selected.','danger'); return render_template('visit_form.html', patient=patient, visit=None, doctors=[dict(d) for d in doctors], today=date.today().isoformat(), now_time=datetime.now().strftime('%H:%M'), next_token=_next_token(db,hid))
        def _i(k, mn=None, mx=None): return safe_int(f.get(k), default=None, min_val=mn, max_val=mx)
        def _r(k, mn=None, mx=None): return safe_float(f.get(k), default=None, min_val=mn, max_val=mx)
        def _s(k): v=(f.get(k) or '').strip(); return v if v else None
        # Handle prescription image upload
        rx_image = _save_prescription_image(request.files.get('prescription_image'), hid, pid)
        db.execute('''INSERT INTO visits
            (hospital_id,patient_id,visit_type,token_no,visit_date,visit_time,doctor_id,
             complaints,history_of_illness,examination_findings,
             primary_diagnosis,secondary_diagnosis,investigation,prescription,advice,notes,
             bp_systolic,bp_diastolic,pulse,temperature,weight,height,spo2,rr,blood_sugar,
             followup_date,followup_notes,created_by,prescription_image)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
            hid,pid,vtype,token,
            vdate,vtime,
            doc_id,_s('complaints'),_s('history_of_illness'),_s('examination_findings'),
            _s('primary_diagnosis'),_s('secondary_diagnosis'),_s('investigation'),
            _s('prescription'),_s('advice'),_s('notes'),
            _i('bp_systolic',60,250),_i('bp_diastolic',30,150),_i('pulse',20,220),
            _r('temperature',20,50),_r('weight',0,500),_i('height',50,250),_i('spo2',50,100),_i('rr',5,60),_r('blood_sugar',0,1000),
            _s('followup_date'),_s('followup_notes'),session['user_id'],
            rx_image
        ])
        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception: pass
        flash(f'Visit recorded.{" Token #"+str(token) if token else ""}','success')
        return redirect(url_for('patients.patient_detail',pid=pid))
    pt = {k:(patient[k] if k in patient.keys() else None)
          for k in ['id','name','age','gender','blood_group','comorbidity','dob','known_allergies']}
    return render_template('visit_form.html', patient=pt, visit=None,
                           doctors=[dict(d) for d in doctors],
                           today=date.today().isoformat(),
                           now_time=datetime.now().strftime('%H:%M'),
                           next_token=_next_token(db,hid))

@visit_routes.route('/<int:pid>/<int:vid>/edit', methods=['GET','POST'])
def edit_visit(pid, vid):
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw(): flash('Read-only.','danger'); return redirect(url_for('patients.patient_detail',pid=pid))
    hid = _hid(); db = get_db()
    patient   = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?',(pid,hid)).fetchone()
    raw_visit = db.execute('SELECT * FROM visits WHERE id=? AND patient_id=? AND hospital_id=?',(vid,pid,hid)).fetchone()
    if not raw_visit: flash('Not found.','danger'); return redirect(url_for('patients.patient_detail',pid=pid))
    doctors = db.execute("SELECT id,name FROM users WHERE hospital_id=? AND role IN ('admin','doctor') ORDER BY name",(hid,)).fetchall()
    if request.method == 'POST':
        f = request.form
        vdate = f.get('visit_date') or date.today().isoformat()
        vtime = f.get('visit_time') or ''
        if not validate_date(vdate):
            flash('Invalid visit date.','danger'); return render_template('visit_form.html', patient=patient, visit=_sv(raw_visit), doctors=[dict(d) for d in doctors], today=date.today().isoformat(), now_time=datetime.now().strftime('%H:%M'))
        if vtime and not validate_time(vtime):
            flash('Invalid visit time.','danger'); return render_template('visit_form.html', patient=patient, visit=_sv(raw_visit), doctors=[dict(d) for d in doctors], today=date.today().isoformat(), now_time=datetime.now().strftime('%H:%M'))
        doc_id = safe_int(f.get('doctor_id'), default=None, min_val=1)
        if doc_id:
            ok = db.execute("SELECT 1 FROM users WHERE id=? AND hospital_id=? AND role IN ('admin','doctor')",(doc_id,hid)).fetchone()
            if not ok:
                flash('Invalid doctor selected.','danger'); return render_template('visit_form.html', patient=patient, visit=_sv(raw_visit), doctors=[dict(d) for d in doctors], today=date.today().isoformat(), now_time=datetime.now().strftime('%H:%M'))
        def _i(k, mn=None, mx=None): return safe_int(f.get(k), default=None, min_val=mn, max_val=mx)
        def _r(k, mn=None, mx=None): return safe_float(f.get(k), default=None, min_val=mn, max_val=mx)
        def _s(k): v=(f.get(k) or '').strip(); return v if v else None
        # Handle prescription image
        old_image = raw_visit['prescription_image'] if 'prescription_image' in raw_visit.keys() else None
        new_image_file = request.files.get('prescription_image')
        remove_image = f.get('remove_prescription_image') == '1'
        rx_image = old_image   # keep old by default
        if new_image_file and new_image_file.filename:
            _delete_prescription_image(old_image)
            rx_image = _save_prescription_image(new_image_file, hid, pid)
        elif remove_image:
            _delete_prescription_image(old_image)
            rx_image = None
        db.execute('''UPDATE visits SET
            visit_date=?,visit_time=?,doctor_id=?,
            complaints=?,history_of_illness=?,examination_findings=?,
            primary_diagnosis=?,secondary_diagnosis=?,investigation=?,prescription=?,advice=?,notes=?,
            bp_systolic=?,bp_diastolic=?,pulse=?,temperature=?,weight=?,height=?,spo2=?,rr=?,blood_sugar=?,
            followup_date=?,followup_notes=?,prescription_image=? WHERE id=? AND hospital_id=?''', [
            vdate, vtime, doc_id,
            _s('complaints'),_s('history_of_illness'),_s('examination_findings'),
            _s('primary_diagnosis'),_s('secondary_diagnosis'),_s('investigation'),
            _s('prescription'),_s('advice'),_s('notes'),
            _i('bp_systolic',60,250),_i('bp_diastolic',30,150),_i('pulse',20,220),
            _r('temperature',20,50),_r('weight',0,500),_i('height',50,250),_i('spo2',50,100),_i('rr',5,60),_r('blood_sugar',0,1000),
            _s('followup_date'),_s('followup_notes'),rx_image,vid,hid])
        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception: pass
        flash('Updated.','success'); return redirect(url_for('patients.patient_detail',pid=pid))
    pt = {k:(patient[k] if k in patient.keys() else None)
          for k in ['id','name','age','gender','blood_group','comorbidity','dob','known_allergies']}
    return render_template('visit_form.html', patient=pt, visit=_sv(raw_visit),
                           doctors=[dict(d) for d in doctors],
                           today=date.today().isoformat(),
                           now_time=datetime.now().strftime('%H:%M'))

@visit_routes.route('/<int:pid>/<int:vid>/delete', methods=['POST'])
def delete_visit(pid, vid):
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw(): flash('Read-only.','danger'); return redirect(url_for('patients.patient_detail',pid=pid))
    hid = _hid(); db = get_db()
    db.execute('DELETE FROM visits WHERE id=? AND patient_id=? AND hospital_id=?',(vid,pid,hid))
    db.commit()
    try:
        from silent_backup import backup; backup()
    except Exception: pass
    flash('Deleted.','warning'); return redirect(url_for('patients.patient_detail',pid=pid))

@visit_routes.route('/<int:pid>/<int:vid>/print')
def print_prescription(pid, vid):
    if not _ok(): return redirect(url_for('auth.login'))
    hid = _hid(); db = get_db()
    patient   = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?',(pid,hid)).fetchone()
    raw_visit = db.execute('SELECT * FROM visits WHERE id=? AND patient_id=? AND hospital_id=?',(vid,pid,hid)).fetchone()
    if not raw_visit: flash('Not found.','danger'); return redirect(url_for('patients.patient_detail',pid=pid))
    doctor = db.execute("SELECT name FROM users WHERE hospital_id=? AND role IN ('admin','doctor') LIMIT 1",(hid,)).fetchone()
    from datetime import datetime as dt
    def calc_age(dob):
        if not dob: return None
        try:
            d = dt.strptime(dob,'%Y-%m-%d').date(); t = date.today()
            return t.year-d.year-((t.month,t.day)<(d.month,d.day))
        except: return None
    pt = {k:(patient[k] if k in patient.keys() else None)
          for k in ['id','name','age','gender','blood_group','comorbidity',
                    'dob','known_allergies','uhid','org_id','individual_number','phone']}
    keys=['id','patient_id','visit_type','token_no','visit_date','visit_time',
          'complaints','history_of_illness','examination_findings',
          'primary_diagnosis','secondary_diagnosis','investigation','prescription',
          'advice','notes','bp_systolic','bp_diastolic','pulse','temperature',
          'weight','height','spo2','rr','blood_sugar','followup_date','followup_notes',
          'prescription_image']
    visit = {k:(raw_visit[k] if k in raw_visit.keys() else None) for k in keys}
    return render_template('prescription.html', patient=pt,
                           display_age=calc_age(pt['dob']) or pt['age'],
                           visit=visit, doctor=doctor,
                           today=date.today().strftime('%d %b %Y'))
