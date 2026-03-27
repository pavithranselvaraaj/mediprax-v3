from ..database import get_db

def get_all_patients():
    return get_db().execute('SELECT * FROM patients ORDER BY name').fetchall()

def get_patient(pid):
    return get_db().execute('SELECT * FROM patients WHERE id=?', (pid,)).fetchone()

def add_patient(data):
    db = get_db()
    db.execute('''INSERT INTO patients
        (name,age,gender,phone,address,blood_group,comorbidity)
        VALUES (?,?,?,?,?,?,?)''', (
        data.get('name'), data.get('age'), data.get('gender'),
        data.get('phone'), data.get('address'),
        data.get('blood_group'), data.get('comorbidity')
    ))
    db.commit()
