from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from ..database import get_db
from ..utils.validators import safe_float
from datetime import date

pharmacy_routes = Blueprint('pharmacy', __name__, url_prefix='/pharmacy')

def _hid(): return session.get('hospital_id', 1)
def _login(): return 'user_id' in session and 'hospital_id' in session
def _can_write(): return session.get('role') in ('admin', 'doctor', 'nurse')

@pharmacy_routes.route('/')
def pharmacy_list():
    """List all dispensed medicines"""
    if not _login(): return redirect(url_for('auth.login'))
    hid = _hid(); db = get_db()
    page = max(1, request.args.get('page', 1, type=int))
    per_page = 20
    q = request.args.get('q', '').strip()

    where = 'WHERE ph.hospital_id=?'
    params = [hid]
    if q:
        where += ' AND (p.name LIKE ? OR ph.medicine LIKE ?)'
        params += [f'%{q}%', f'%{q}%']

    total = db.execute(f'''SELECT COUNT(*) FROM pharmacy ph 
        JOIN patients p ON ph.patient_id=p.id {where}''', params).fetchone()[0]

    rows = db.execute(f'''SELECT ph.*, p.name AS patient_name, p.uhid
        FROM pharmacy ph JOIN patients p ON ph.patient_id=p.id
        {where} ORDER BY ph.id DESC LIMIT ? OFFSET ?''',
        params + [per_page, (page-1)*per_page]).fetchall()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template('pharmacy_list.html',
                           items=[dict(r) for r in rows],
                           search=q, page=page, total_pages=total_pages, total=total)

@pharmacy_routes.route('/dispense/<int:pid>', methods=['GET', 'POST'])
def dispense(pid):
    """Dispense medicine to patient"""
    if not _login(): return redirect(url_for('auth.login'))
    if not _can_write():
        flash('No permission.', 'danger')
        return redirect(url_for('patients.patient_detail', pid=pid))

    hid = _hid(); db = get_db()
    patient = db.execute('SELECT * FROM patients WHERE id=? AND hospital_id=?', (pid, hid)).fetchone()
    if not patient:
        flash('Patient not found.', 'danger')
        return redirect(url_for('patients.patients'))

    if request.method == 'POST':
        medicines = request.form.getlist('medicine[]')
        quantities = request.form.getlist('quantity[]')
        units = request.form.getlist('unit[]')
        prices = request.form.getlist('price[]')
        visit_id = request.form.get('visit_id', type=int)

        for i, med in enumerate(medicines):
            if not med.strip(): continue
            qty   = safe_float(quantities[i] if i < len(quantities) else None, default=1.0, min_val=0)
            unit  = units[i] if i < len(units) else 'Tablets'
            price = safe_float(prices[i] if i < len(prices) else None, default=0.0, min_val=0)

            db.execute('''INSERT INTO pharmacy 
                (hospital_id, patient_id, visit_id, medicine, quantity, unit, price)
                VALUES (?,?,?,?,?,?,?)''',
                [hid, pid, visit_id, med.strip(), qty, unit, price])

        db.commit()
        try:
            from silent_backup import backup; backup()
        except Exception:
            pass
        flash('Medicines dispensed.', 'success')
        return redirect(url_for('patients.patient_detail', pid=pid))

    # Get last visit for linking
    last_visit = db.execute(
        'SELECT id, visit_date, primary_diagnosis FROM visits WHERE patient_id=? AND hospital_id=? ORDER BY id DESC LIMIT 1',
        (pid, hid)).fetchone()

    return render_template('pharmacy_dispense.html',
                           patient=dict(patient),
                           last_visit=dict(last_visit) if last_visit else None)

