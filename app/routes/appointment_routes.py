from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from ..database import get_db

appointment_routes = Blueprint('appointments', __name__, url_prefix='/appointments')

def _ok(): return 'user_id' in session and 'hospital_id' in session
def _hid(): return session.get('hospital_id',1)

@appointment_routes.route('/')
def appointments():
    if not _ok(): return redirect(url_for('auth.login'))
    return render_template('appointments.html')

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
    db.execute('INSERT INTO appointments (hospital_id,patient_id,appt_date,appt_time,reason,status) VALUES (?,?,?,?,?,?)',
               (hid,data.get('patient_id'),data.get('date'),data.get('time'),data.get('reason'),'scheduled'))
    db.commit()
    return jsonify({'status':'created'})
