from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from ..database import get_db
from ..utils.validators import validate_date, validate_time, safe_int

appointment_routes = Blueprint('appointments', __name__, url_prefix='/appointments')

def _ok(): return 'user_id' in session and 'hospital_id' in session
def _hid(): return session.get('hospital_id',1)
def _rw(): return session.get('role') in ('admin','doctor')

VALID_STATUSES = ('scheduled', 'completed', 'cancelled', 'no_show')

@appointment_routes.route('/')
def appointments():
    if not _ok(): return redirect(url_for('auth.login'))
    db = get_db(); hid = _hid()
    rows = db.execute('''SELECT a.*,p.name AS patient_name FROM appointments a
        LEFT JOIN patients p ON a.patient_id=p.id WHERE a.hospital_id=? ORDER BY a.appt_date DESC, a.id DESC''',(hid,)).fetchall()
    return render_template('appointments.html', appts=[dict(r) for r in rows])

@appointment_routes.route('/api')
def api():
    if not _ok(): return jsonify([])
    hid = _hid(); db = get_db()
    rows = db.execute('''SELECT a.*,p.name AS patient_name FROM appointments a
        LEFT JOIN patients p ON a.patient_id=p.id WHERE a.hospital_id=?''',(hid,)).fetchall()
    return jsonify([{'id':r['id'],'title':f"{r['patient_name'] or 'Unknown'}",
                     'start':r['appt_date'],'color':'#1a6fad'} for r in rows])

@appointment_routes.route('/', methods=['POST'])
def create():
    if not _ok(): return jsonify({'error':'unauthorized'}),401
    hid = _hid(); data = request.json or request.form; db = get_db()
    appt_date = data.get('date') or data.get('appt_date')
    if not appt_date or not validate_date(appt_date):
        return jsonify({'error':'Valid date is required (YYYY-MM-DD)'}),400
    appt_time = data.get('time') or data.get('appt_time') or ''
    if appt_time and not validate_time(appt_time):
        return jsonify({'error':'Invalid time format (HH:MM)'}),400
    pid = safe_int(data.get('patient_id'), default=None, min_val=1)
    if pid:
        ok = db.execute('SELECT 1 FROM patients WHERE id=? AND hospital_id=?',(pid,hid)).fetchone()
        if not ok:
            return jsonify({'error':'Patient not found in this hospital'}),400
    reason = (data.get('reason') or '').strip()[:120]  # Max 120 chars
    db.execute('INSERT INTO appointments (hospital_id,patient_id,appt_date,appt_time,reason,status) VALUES (?,?,?,?,?,?)',
               (hid,pid,appt_date,appt_time,reason,'scheduled'))
    db.commit()
    return jsonify({'status':'created'})

@appointment_routes.route('/<int:appt_id>/status', methods=['POST'])
def update_status(appt_id):
    if not _ok(): return jsonify({'error':'unauthorized'}),401
    if not _rw(): return jsonify({'error':'No permission'}),403
    hid = _hid(); db = get_db()
    status = request.form.get('status','').strip()
    if status not in VALID_STATUSES:
        return jsonify({'error':'Invalid status'}),400
    # Check appointment belongs to this hospital
    appt = db.execute('SELECT id FROM appointments WHERE id=? AND hospital_id=?',(appt_id,hid)).fetchone()
    if not appt:
        return jsonify({'error':'Appointment not found'}),404
    db.execute('UPDATE appointments SET status=? WHERE id=? AND hospital_id=?',(status,appt_id,hid))
    db.commit()
    return jsonify({'status':'updated'})

@appointment_routes.route('/<int:appt_id>/delete', methods=['POST'])
def delete_appointment(appt_id):
    if not _ok(): return redirect(url_for('auth.login'))
    if not _rw():
        flash('No permission.','danger')
        return redirect(url_for('appointments.appointments'))
    hid = _hid(); db = get_db()
    db.execute('DELETE FROM appointments WHERE id=? AND hospital_id=?',(appt_id,hid))
    db.commit()
    flash('Appointment deleted.','success')
    return redirect(url_for('appointments.appointments'))

