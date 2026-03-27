from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from ..database import get_db
from datetime import date, datetime

visit_routes = Blueprint('visits', __name__, url_prefix='/visits')

def _hid(): return session.get('hospital_id', 1)
def _login(): return 'user_id' in session and 'hospital_id' in session
def _can_write(): return session.get('role') in ('admin','doctor')

def _safe_visit(v):
    keys = ['id','patient_id','hospital_id','admission_id','visit_type','token_no',
            'visit_date','visit_time','doctor_id','complaints','history_of_illness',
            'examination_findings','primary_diagnosis','secondary_diagnosis',
            'investigation','prescription','notes','advice',
            'bp_systolic','bp_diastolic','pulse','temperature','weight',
            'height','spo2','rr','blood_sugar','followup_date','followup_notes']
    d = {}
    for k in keys:
        try: d[k] = v[k]
        except: d[k] = None
    return d

def _next_token(db, hid):
    today = date.today().isoformat()
    row = db.execute(
        "SELECT MAX(token_no) FROM visits WHERE hospital_id=? AND visit_date=? AND visit_type='OPD'",
        (hid, today)
    ).fetchone()
    return (row[0] or 0) + 1


@visit_routes.route('/<int:pid>/add', methods=['GET','POST'])
def add_visit(pid):
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    hid = _hid()
    db  = get_db()
    patient = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid,hid)).fetchone()
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patients.patients'))
    doctors = db.execute("SELECT id,name FROM users WHERE hospital_id=? AND role IN ('admin','doctor') ORDER BY name", (hid,)).fetchall()

    if request.method == 'POST':
        f = request.form
        vtype = f.get('visit_type','OPD')
        token = _next_token(db, hid) if vtype == 'OPD' else None
        def _i(k): return f.get(k, type=int) or None
        def _r(k): return f.get(k, type=float) or None
        def _s(k): v=f.get(k,'').strip(); return v if v else None
        db.execute('''INSERT INTO visits
            (hospital_id,patient_id,visit_type,token_no,visit_date,visit_time,doctor_id,
             complaints,history_of_illness,examination_findings,
             primary_diagnosis,secondary_diagnosis,
             investigation,prescription,notes,advice,
             bp_systolic,bp_diastolic,pulse,temperature,weight,height,spo2,rr,blood_sugar,
             followup_date,followup_notes,created_by)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
            hid, pid, vtype, token,
            f.get('visit_date') or date.today().isoformat(),
            f.get('visit_time') or datetime.now().strftime('%H:%M'),
            _i('doctor_id'),
            _s('complaints'), _s('history_of_illness'), _s('examination_findings'),
            _s('primary_diagnosis'), _s('secondary_diagnosis'),
            _s('investigation'), _s('prescription'), _s('notes'), _s('advice'),
            _i('bp_systolic'), _i('bp_diastolic'), _i('pulse'),
            _r('temperature'), _r('weight'), _i('height'), _i('spo2'), _i('rr'),
            _r('blood_sugar'), _s('followup_date'), _s('followup_notes'),
            session['user_id']
        ])
        db.commit()
        flash(f'Visit recorded. Token: {token}' if token else 'Visit recorded.', 'success')
        return redirect(url_for('patients.patient_detail', pid=pid))
    pt = {k: (patient[k] if k in patient.keys() else None)
          for k in ['id','name','age','gender','blood_group','comorbidity','dob',
                    'known_allergies','past_medical_history']}
    return render_template('visit_form.html', patient=pt, visit=None,
                           doctors=[dict(d) for d in doctors],
                           today=date.today().isoformat(),
                           now_time=datetime.now().strftime('%H:%M'),
                           next_token=_next_token(db, hid))


@visit_routes.route('/<int:pid>/<int:vid>/edit', methods=['GET','POST'])
def edit_visit(pid, vid):
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    hid = _hid()
    db  = get_db()
    patient   = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid,hid)).fetchone()
    raw_visit = db.execute('SELECT * FROM visits WHERE id=? AND patient_id=? AND hospital_id=?', (vid,pid,hid)).fetchone()
    if not raw_visit:
        flash('Visit not found.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    doctors = db.execute("SELECT id,name FROM users WHERE hospital_id=? AND role IN ('admin','doctor') ORDER BY name", (hid,)).fetchall()

    if request.method == 'POST':
        f = request.form
        def _i(k): return f.get(k, type=int) or None
        def _r(k): return f.get(k, type=float) or None
        def _s(k): v=f.get(k,'').strip(); return v if v else None
        db.execute('''UPDATE visits SET
            visit_date=?,visit_time=?,doctor_id=?,
            complaints=?,history_of_illness=?,examination_findings=?,
            primary_diagnosis=?,secondary_diagnosis=?,
            investigation=?,prescription=?,notes=?,advice=?,
            bp_systolic=?,bp_diastolic=?,pulse=?,temperature=?,weight=?,
            height=?,spo2=?,rr=?,blood_sugar=?,
            followup_date=?,followup_notes=?
            WHERE id=? AND hospital_id=?''', [
            f.get('visit_date') or date.today().isoformat(),
            f.get('visit_time') or '',
            _i('doctor_id'),
            _s('complaints'), _s('history_of_illness'), _s('examination_findings'),
            _s('primary_diagnosis'), _s('secondary_diagnosis'),
            _s('investigation'), _s('prescription'), _s('notes'), _s('advice'),
            _i('bp_systolic'), _i('bp_diastolic'), _i('pulse'),
            _r('temperature'), _r('weight'), _i('height'), _i('spo2'), _i('rr'),
            _r('blood_sugar'), _s('followup_date'), _s('followup_notes'),
            vid, hid
        ])
        db.commit()
        from silent_backup import backup; backup()
        flash('Visit updated.', 'success')
        return redirect(url_for('patients.patient_detail', pid=pid))

    pt = {k: (patient[k] if k in patient.keys() else None)
          for k in ['id','name','age','gender','blood_group','comorbidity','dob',
                    'known_allergies','past_medical_history']}
    return render_template('visit_form.html', patient=pt, visit=_safe_visit(raw_visit),
                           doctors=[dict(d) for d in doctors],
                           today=date.today().isoformat(),
                           now_time=datetime.now().strftime('%H:%M'))


@visit_routes.route('/<int:pid>/<int:vid>/delete', methods=['POST'])
def delete_visit(pid, vid):
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    hid = _hid()
    db  = get_db()
    db.execute('DELETE FROM visits WHERE id=? AND patient_id=? AND hospital_id=?', (vid,pid,hid))
    db.commit()
    from silent_backup import backup; backup()
    flash('Visit deleted.', 'warning')
    return redirect(url_for('patients.patient_detail', pid=pid))


@visit_routes.route('/<int:pid>/<int:vid>/print')
def print_prescription(pid, vid):
    if not _login(): return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    patient   = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid,hid)).fetchone()
    raw_visit = db.execute('SELECT * FROM visits WHERE id=? AND patient_id=? AND hospital_id=?', (vid,pid,hid)).fetchone()
    if not raw_visit:
        flash('Visit not found.','danger')
        return redirect(url_for('patients.patient_detail', pid=pid))
    doctor = db.execute("SELECT name FROM users WHERE hospital_id=? AND role IN ('admin','doctor') LIMIT 1", (hid,)).fetchone()
    pt = {k: (patient[k] if k in patient.keys() else None)
          for k in ['id','name','age','gender','blood_group','comorbidity','dob',
                    'known_allergies','uhid','individual_number','phone']}
    from datetime import datetime as dt
    def calc_age(dob):
        if not dob: return pt['age']
        try:
            d = dt.strptime(dob,'%Y-%m-%d').date()
            t = date.today()
            return t.year-d.year-((t.month,t.day)<(d.month,d.day))
        except: return pt['age']
    display_age = calc_age(pt['dob'])
    return render_template('prescription.html', patient=pt,
                           display_age=display_age, visit=_safe_visit(raw_visit),
                           doctor=doctor, today=date.today().strftime('%d %b %Y'))
