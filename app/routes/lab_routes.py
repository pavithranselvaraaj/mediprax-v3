from flask import Blueprint, request, render_template, redirect, url_for, session, flash, jsonify
from ..database import get_db
from datetime import date

lab_routes = Blueprint('lab', __name__, url_prefix='/lab')

def _hid(): return session.get('hospital_id', 1)
def _login(): return 'user_id' in session and 'hospital_id' in session
def _can_write(): return session.get('role') in ('admin','doctor')

COMMON_TESTS = {
    'Haematology': ['CBC (Complete Blood Count)','Haemoglobin','WBC Count','Platelet Count','ESR','Peripheral Smear'],
    'Biochemistry': ['Blood Glucose (Fasting)','Blood Glucose (PP)','HbA1c','Urea','Creatinine','Uric Acid',
                     'Total Bilirubin','Direct Bilirubin','SGOT (AST)','SGPT (ALT)','ALP','Total Protein',
                     'Albumin','Sodium','Potassium','Chloride','Calcium','Phosphorus'],
    'Lipid Profile': ['Total Cholesterol','Triglycerides','HDL Cholesterol','LDL Cholesterol','VLDL'],
    'Thyroid': ['TSH','T3','T4','Free T3','Free T4'],
    'Urine': ['Urine Routine & Microscopy','Urine Culture & Sensitivity','Urine Pregnancy Test'],
    'Microbiology': ['Blood Culture','Sputum Culture','Stool Routine','Stool Culture','Widal Test','MP (Malaria Parasite)'],
    'Cardiac': ['ECG','2D Echo','Troponin I','CK-MB','BNP'],
    'Radiology': ['X-Ray Chest PA','X-Ray KUB','Ultrasound Abdomen','CT Scan','MRI'],
    'Other': ['COVID-19 Antigen','COVID-19 RT-PCR','Dengue NS1','Dengue IgG/IgM','HIV Screening','HBsAg','HCV'],
}

@lab_routes.route('/')
def lab_list():
    if not _login(): return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    status = request.args.get('status','')
    q      = request.args.get('q','').strip()
    page   = max(1, request.args.get('page', 1, type=int))
    per_page = 15

    where  = "WHERE o.hospital_id=?"
    params = [hid]
    if q:
        where += " AND (p.name LIKE ? OR p.uhid LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    if status:
        where += " AND o.status=?"
        params.append(status)

    total  = db.execute(f"SELECT COUNT(*) FROM lab_orders o JOIN patients p ON o.patient_id=p.id {where}", params).fetchone()[0]
    orders = db.execute(f'''
        SELECT o.*, p.name AS patient_name, p.uhid,
               GROUP_CONCAT(t.test_name, ' · ') AS tests,
               u.name AS ordered_by_name
        FROM lab_orders o
        JOIN patients p ON o.patient_id=p.id
        LEFT JOIN lab_tests t ON t.lab_order_id=o.id
        LEFT JOIN users u ON o.ordered_by=u.id
        {where}
        GROUP BY o.id ORDER BY o.id DESC LIMIT ? OFFSET ?
    ''', params + [per_page, (page-1)*per_page]).fetchall()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('lab/lab_list.html',
                           orders=[dict(o) for o in orders],
                           search=q, status_filter=status,
                           page=page, total_pages=total_pages, total=total)

@lab_routes.route('/order/<int:pid>', methods=['GET','POST'])
def order_tests(pid):
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

    if request.method == 'POST':
        f = request.form
        cur = db.execute('''INSERT INTO lab_orders
            (hospital_id,patient_id,visit_id,ordered_by,order_date,status,notes)
            VALUES (?,?,?,?,?,'pending',?)''', [
            hid, pid,
            f.get('visit_id', type=int) or None,
            session['user_id'],
            date.today().isoformat(),
            f.get('notes','').strip()
        ])
        order_id = cur.lastrowid
        tests = request.form.getlist('tests[]')
        cats  = request.form.getlist('test_cats[]')
        for i, test in enumerate(tests):
            if test.strip():
                db.execute('''INSERT INTO lab_tests
                    (lab_order_id,test_name,test_category,status)
                    VALUES (?,?,?,'pending')''', [
                    order_id, test.strip(),
                    cats[i] if i < len(cats) else 'General'
                ])
        db.commit()
        from silent_backup import backup; backup()
        flash('Lab order created.', 'success')
        return redirect(url_for('patients.patient_detail', pid=pid))

    last_visit = db.execute(
        'SELECT id FROM visits WHERE patient_id=? AND hospital_id=? ORDER BY id DESC LIMIT 1', (pid,hid)
    ).fetchone()
    return render_template('lab/order_form.html',
                           patient=dict(patient),
                           common_tests=COMMON_TESTS,
                           last_visit_id=last_visit['id'] if last_visit else None)

@lab_routes.route('/result/<int:order_id>', methods=['GET','POST'])
def enter_results(order_id):
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('Read-only access.', 'danger')
        return redirect(url_for('lab.lab_list'))
    hid = _hid()
    db  = get_db()
    order = db.execute('''
        SELECT o.*, p.name AS patient_name, p.uhid, p.age, p.gender
        FROM lab_orders o JOIN patients p ON o.patient_id=p.id
        WHERE o.id=? AND o.hospital_id=?
    ''', (order_id, hid)).fetchone()
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('lab.lab_list'))
    tests = db.execute('SELECT * FROM lab_tests WHERE lab_order_id=? ORDER BY id', (order_id,)).fetchall()

    if request.method == 'POST':
        for t in tests:
            result  = request.form.get(f'result_{t["id"]}','').strip()
            unit    = request.form.get(f'unit_{t["id"]}','').strip()
            ref     = request.form.get(f'ref_{t["id"]}','').strip()
            remarks = request.form.get(f'remarks_{t["id"]}','').strip()
            status  = 'completed' if result else 'pending'
            db.execute('''UPDATE lab_tests SET result=?,unit=?,reference_range=?,
                remarks=?,status=?,result_date=? WHERE id=?''',
                [result, unit, ref, remarks, status,
                 date.today().isoformat() if result else None, t['id']])
        # Check if all completed
        pending = db.execute("SELECT COUNT(*) FROM lab_tests WHERE lab_order_id=? AND status='pending'", (order_id,)).fetchone()[0]
        db.execute("UPDATE lab_orders SET status=? WHERE id=?",
                   ('completed' if pending == 0 else 'in_progress', order_id))
        db.commit()
        from silent_backup import backup; backup()
        flash('Results saved.', 'success')
        return redirect(url_for('lab.view_report', order_id=order_id))

    return render_template('lab/result_form.html',
                           order=dict(order), tests=[dict(t) for t in tests])

@lab_routes.route('/report/<int:order_id>')
def view_report(order_id):
    if not _login(): return redirect(url_for('auth.login'))
    hid = _hid()
    db  = get_db()
    order = db.execute('''
        SELECT o.*, p.name AS patient_name, p.uhid, p.age, p.gender,
               p.blood_group, u.name AS ordered_by_name
        FROM lab_orders o
        JOIN patients p ON o.patient_id=p.id
        LEFT JOIN users u ON o.ordered_by=u.id
        WHERE o.id=? AND o.hospital_id=?
    ''', (order_id, hid)).fetchone()
    if not order:
        flash('Report not found.', 'danger')
        return redirect(url_for('lab.lab_list'))
    tests = db.execute('SELECT * FROM lab_tests WHERE lab_order_id=? ORDER BY test_category, id', (order_id,)).fetchall()
    return render_template('lab/report.html',
                           order=dict(order), tests=[dict(t) for t in tests],
                           today=date.today().strftime('%d %b %Y'))

@lab_routes.route('/api/tests')
def api_tests():
    return jsonify(COMMON_TESTS)
