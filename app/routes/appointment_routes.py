from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from ..database import get_db

appointment_routes = Blueprint('appointments', __name__, url_prefix='/appointments')

@appointment_routes.route('/')
def appointments():
    if 'user_id' not in session: return redirect(url_for('auth.login'))
    return render_template('appointments.html')

@appointment_routes.route('/api')
def appointments_api():
    if 'user_id' not in session: return jsonify([])
    hid  = session.get('hospital_id', 1)
    db   = get_db()
    rows = db.execute('''
        SELECT a.*, p.name AS patient_name FROM appointments a
        LEFT JOIN patients p ON a.patient_id=p.id
        WHERE a.hospital_id=?
    ''', (hid,)).fetchall()
    return jsonify([{
        'id': r['id'],
        'title': f"{r['patient_name'] or 'Unknown'} — {r['doctor'] or ''}",
        'start': r['date'],
        'color': '#1a6fad' if r['status']=='scheduled' else '#6c757d'
    } for r in rows])

@appointment_routes.route('/', methods=['POST'])
def create_appointment():
    if 'user_id' not in session: return jsonify({'error':'unauthorized'}), 401
    hid  = session.get('hospital_id', 1)
    data = request.json or request.form
    db   = get_db()
    db.execute('INSERT INTO appointments (hospital_id,patient_id,doctor,date,time,reason,status) VALUES (?,?,?,?,?,?,?)', (
        hid, data.get('patient_id'), data.get('doctor'),
        data.get('date'), data.get('time'), data.get('reason'), 'scheduled'
    ))
    db.commit()
    return jsonify({'status': 'created'})
