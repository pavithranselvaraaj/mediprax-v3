from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from ..database import get_db
from datetime import date

lab_routes = Blueprint('lab', __name__, url_prefix='/lab')
def _ok():  return 'user_id' in session and 'hospital_id' in session
def _hid(): return session.get('hospital_id',1)
def _rw():  return session.get('role') in ('admin','doctor')

COMMON = {
    'Haematology':  ['CBC','Haemoglobin','WBC Count','Platelet Count','ESR'],
    'Biochemistry': ['Blood Glucose Fasting','Blood Glucose PP','HbA1c','Urea','Creatinine',
                     'SGOT','SGPT','Total Bilirubin','Sodium','Potassium','Calcium'],
    'Lipid':        ['Total Cholesterol','Triglycerides','HDL','LDL','VLDL'],
    'Thyroid':      ['TSH','T3','T4','Free T3','Free T4'],
    'Urine':        ['Urine Routine','Urine Culture','Urine Pregnancy Test'],
    'Microbiology': ['Blood Culture','Sputum Culture','Widal','MP Malaria'],
    'Radiology':    ['X-Ray Chest','X-Ray KUB','Ultrasound Abdomen','ECG'],
    'Other':        ['COVID-19 Antigen','COVID-19 RT-PCR','Dengue NS1','HBsAg','HIV Screening'],
}

@lab_routes.route('/')
def lab_list():
    if not _ok(): return redirect(url_for('auth.login'))
    hid = _hid(); db = get_db(); pg = max(1,request.args.get('page',1,type=int)); pp = 15
    total = db.execute('SELECT COUNT(*) FROM lab_orders WHERE hospital_id=?',(hid,)).fetchone()[0]
    rows  = db.execute('''SELECT o.*,p.name AS patient_name,p.uhid,
        GROUP_CONCAT(t.test_name," · ") AS tests
        FROM lab_orders o JOIN patients p ON o.patient_id=p.id
        LEFT JOIN lab_tests t ON t.lab_order_id=o.id
        WHERE o.hospital_id=? GROUP BY o.id ORDER BY o.id DESC LIMIT ? OFFSET ?''',
        (hid,pp,(pg-1)*pp)).fetchall()
    return render_template('lab/lab_list.html', orders=[dict(r) for r in rows],
                           page=pg, total_pages=max(1,(total+pp-1)//pp), total=total)

@lab_routes.route('/order/<int:pid>', methods=['GET','POST'])
def order_tests(pid):
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw(): flash('Read-only.','danger'); return redirect(url_for('patients.patient_detail',pid=pid))
    hid = _hid(); db = get_db()
    patient = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?',(pid,hid)).fetchone()
    if not patient: flash('Not found.','danger'); return redirect(url_for('patients.patients'))
    if request.method == 'POST':
        oid = db.execute('INSERT INTO lab_orders (hospital_id,patient_id,ordered_by,order_date,status,notes) VALUES (?,?,?,?,?,?)',
            [hid,pid,session['user_id'],date.today().isoformat(),'pending',request.form.get('notes','')]).lastrowid
        for test,cat in zip(request.form.getlist('tests[]'),request.form.getlist('test_cats[]')):
            if test.strip():
                db.execute("INSERT INTO lab_tests (lab_order_id,test_name,test_category,status) VALUES (?,?,?,'pending')",
                           [oid,test.strip(),cat or 'General'])
        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception: pass
        flash('Lab order created.','success'); return redirect(url_for('patients.patient_detail',pid=pid))
    lv = db.execute('SELECT id FROM visits WHERE patient_id=? AND hospital_id=? ORDER BY id DESC LIMIT 1',(pid,hid)).fetchone()
    return render_template('lab/order_form.html', patient=dict(patient), common_tests=COMMON,
                           last_visit_id=lv['id'] if lv else None)

@lab_routes.route('/result/<int:oid>', methods=['GET','POST'])
def enter_results(oid):
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw(): flash('Read-only.','danger'); return redirect(url_for('lab.lab_list'))
    hid = _hid(); db = get_db()
    order = db.execute('SELECT o.*,p.name AS patient_name,p.uhid,p.age,p.gender FROM lab_orders o JOIN patients p ON o.patient_id=p.id WHERE o.id=? AND o.hospital_id=?',(oid,hid)).fetchone()
    if not order: flash('Not found.','danger'); return redirect(url_for('lab.lab_list'))
    tests = db.execute('SELECT * FROM lab_tests WHERE lab_order_id=? ORDER BY id',(oid,)).fetchall()
    if request.method == 'POST':
        for t in tests:
            result = request.form.get(f'result_{t["id"]}','').strip()
            db.execute('UPDATE lab_tests SET result=?,unit=?,reference_range=?,remarks=?,status=?,result_date=? WHERE id=?',
                [result,request.form.get(f'unit_{t["id"]}',''),request.form.get(f'ref_{t["id"]}',''),
                 request.form.get(f'remarks_{t["id"]}',''),
                 'completed' if result else 'pending',
                 date.today().isoformat() if result else None, t['id']])
        pending = db.execute("SELECT COUNT(*) FROM lab_tests WHERE lab_order_id=? AND status='pending'",(oid,)).fetchone()[0]
        db.execute("UPDATE lab_orders SET status=? WHERE id=?",('completed' if pending==0 else 'in_progress',oid))
        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception: pass
        flash('Results saved.','success'); return redirect(url_for('lab.view_report',order_id=oid))
    return render_template('lab/result_form.html', order=dict(order), tests=[dict(t) for t in tests])

@lab_routes.route('/report/<int:order_id>')
def view_report(order_id):
    if not _ok(): return redirect(url_for('auth.login'))
    hid = _hid(); db = get_db()
    order = db.execute('''SELECT o.*,p.name AS patient_name,p.uhid,p.age,p.gender,p.blood_group,
        u.name AS ordered_by_name FROM lab_orders o JOIN patients p ON o.patient_id=p.id
        LEFT JOIN users u ON o.ordered_by=u.id WHERE o.id=? AND o.hospital_id=?''',(order_id,hid)).fetchone()
    if not order: flash('Not found.','danger'); return redirect(url_for('lab.lab_list'))
    tests = db.execute('SELECT * FROM lab_tests WHERE lab_order_id=? ORDER BY test_category,id',(order_id,)).fetchall()
    return render_template('lab/report.html', order=dict(order), tests=[dict(t) for t in tests],
                           today=date.today().strftime('%d %b %Y'))
