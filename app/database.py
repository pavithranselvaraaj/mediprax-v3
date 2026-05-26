import sqlite3  # noqa: F401  (used for IntegrityError catch below)
from flask import g, current_app
from .utils.password_utils import hash_password as _h

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        # Concurrent reads while a writer is active; reduces 'database is locked'
        try:
            g.db.execute('PRAGMA journal_mode = WAL')
            g.db.execute('PRAGMA synchronous = NORMAL')
        except Exception:
            pass
    return g.db

def _col(db, table, col, typ):
    try:
        cols = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
        if col not in cols:
            db.execute(f'ALTER TABLE {table} ADD COLUMN {col} {typ}')
    except Exception: pass

def init_db(app):
    @app.teardown_appcontext
    def close_db(e=None):
        db = g.pop('db', None)
        if db: db.close()
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS super_admins(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT DEFAULT 'Super Admin',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS hospitals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id TEXT UNIQUE,
            name TEXT NOT NULL,
            tagline TEXT DEFAULT 'Quality Healthcare',
            address TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            color1 TEXT DEFAULT '#1a6fad',
            color2 TEXT DEFAULT '#0e9f8b',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER UNIQUE NOT NULL,
            doctor_name TEXT DEFAULT '',
            doctor_degree TEXT DEFAULT 'MBBS, MD'
        );
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'nurse',
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            patient_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS wards(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ward_type TEXT DEFAULT 'General',
            total_beds INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS beds(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            ward_id INTEGER NOT NULL,
            bed_number TEXT NOT NULL,
            status TEXT DEFAULT 'available'
        );
        CREATE TABLE IF NOT EXISTS patients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            org_id TEXT,
            uhid TEXT,
            name TEXT NOT NULL,
            dob DATE, age INTEGER, gender TEXT,
            guardian_name TEXT DEFAULT '', guardian_relation TEXT DEFAULT '',
            emergency_contact TEXT DEFAULT '', emergency_phone TEXT DEFAULT '',
            insurance TEXT DEFAULT '', insurance_no TEXT DEFAULT '',
            blood_group TEXT DEFAULT '', height_cm INTEGER,
            address TEXT DEFAULT '', city TEXT DEFAULT '', state TEXT DEFAULT '',
            phone TEXT DEFAULT '', email TEXT DEFAULT '',
            individual_number TEXT DEFAULT '', occupation TEXT DEFAULT '',
            marital_status TEXT DEFAULT '', nationality TEXT DEFAULT 'Indian',
            comorbidity TEXT DEFAULT '', known_allergies TEXT DEFAULT '',
            past_medical_history TEXT DEFAULT '', past_surgical_history TEXT DEFAULT '',
            family_history TEXT DEFAULT '', habits TEXT DEFAULT '',
            patient_type TEXT DEFAULT 'OPD',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS admissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            admission_no TEXT,
            admission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admission_type TEXT DEFAULT 'Elective',
            ward_id INTEGER, bed_id INTEGER, admitting_doctor_id INTEGER,
            diagnosis_at_admission TEXT DEFAULT '',
            attendant_name TEXT DEFAULT '', attendant_phone TEXT DEFAULT '',
            attendant_relation TEXT DEFAULT '',
            status TEXT DEFAULT 'admitted',
            discharge_date TIMESTAMP, discharge_type TEXT DEFAULT '',
            discharge_summary TEXT DEFAULT '', final_diagnosis TEXT DEFAULT '',
            discharge_instructions TEXT DEFAULT '',
            condition_at_discharge TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS visits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            visit_type TEXT DEFAULT 'OPD',
            token_no INTEGER,
            visit_date DATE NOT NULL,
            visit_time TIME,
            doctor_id INTEGER,
            complaints TEXT DEFAULT '',
            history_of_illness TEXT DEFAULT '',
            examination_findings TEXT DEFAULT '',
            primary_diagnosis TEXT DEFAULT '',
            secondary_diagnosis TEXT DEFAULT '',
            investigation TEXT DEFAULT '',
            prescription TEXT DEFAULT '',
            advice TEXT DEFAULT '', notes TEXT DEFAULT '',
            bp_systolic INTEGER, bp_diastolic INTEGER,
            pulse INTEGER, temperature REAL, weight REAL,
            height INTEGER, spo2 INTEGER, rr INTEGER, blood_sugar REAL,
            followup_date DATE, followup_notes TEXT DEFAULT '',
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS lab_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            visit_id INTEGER, ordered_by INTEGER,
            order_date DATE NOT NULL,
            status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS lab_tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_order_id INTEGER NOT NULL,
            test_name TEXT NOT NULL,
            test_category TEXT DEFAULT 'General',
            result TEXT DEFAULT '', unit TEXT DEFAULT '',
            reference_range TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            result_date DATE, remarks TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS bills(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            visit_id INTEGER, admission_id INTEGER,
            bill_no TEXT, bill_date DATE NOT NULL,
            bill_type TEXT DEFAULT 'OPD',
            subtotal REAL DEFAULT 0, discount REAL DEFAULT 0,
            tax REAL DEFAULT 0, total REAL DEFAULT 0,
            paid_amount REAL DEFAULT 0,
            payment_mode TEXT DEFAULT 'Cash',
            payment_status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT '', created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS bill_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            category TEXT DEFAULT 'Consultation',
            description TEXT NOT NULL,
            quantity REAL DEFAULT 1,
            unit_price REAL DEFAULT 0,
            amount REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS appointments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id INTEGER, doctor_id INTEGER,
            appt_date TEXT NOT NULL, appt_time TEXT DEFAULT '',
            reason TEXT DEFAULT '', status TEXT DEFAULT 'scheduled',
            token_no INTEGER, notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS pharmacy(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id INTEGER, visit_id INTEGER,
            medicine TEXT NOT NULL, quantity REAL DEFAULT 1,
            unit TEXT DEFAULT 'Tablets', price REAL DEFAULT 0,
            dispensed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Migrate old columns
        # Ensure super_admins has required columns
        sa_cols = {r[1] for r in db.execute('PRAGMA table_info(super_admins)')}
        if 'email' not in sa_cols:
            _col(db, 'super_admins', 'email', 'TEXT')
        if 'name' not in sa_cols:
            _col(db, 'super_admins', 'name', "TEXT DEFAULT 'Super Admin'")
        if 'is_active' not in sa_cols:
            _col(db, 'super_admins', 'is_active', 'INTEGER DEFAULT 1')
        # Backfill email from username if legacy column exists
        sa_cols = {r[1] for r in db.execute('PRAGMA table_info(super_admins)')}
        if 'username' in sa_cols and 'email' in sa_cols:
            # Backfill row-by-row so a UNIQUE conflict on one row doesn't abort all
            for r in db.execute("SELECT id, username FROM super_admins WHERE (email IS NULL OR email='') AND username IS NOT NULL").fetchall():
                try:
                    db.execute('UPDATE super_admins SET email=? WHERE id=?', (r['username'], r['id']))
                except sqlite3.IntegrityError:
                    pass

        # Migrate old columns
        for col, typ in [('hospital_id','INTEGER DEFAULT 1'),('org_id','TEXT'),
                ('uhid','TEXT'),('guardian_relation','TEXT'),
                ('emergency_contact','TEXT'),('emergency_phone','TEXT'),
                ('insurance_no','TEXT'),('height_cm','INTEGER'),
                ('city','TEXT'),('state','TEXT'),('email','TEXT'),
                ('occupation','TEXT'),('marital_status','TEXT'),
                ('nationality',"TEXT DEFAULT 'Indian'"),
                ('known_allergies','TEXT'),('past_medical_history','TEXT'),
                ('past_surgical_history','TEXT'),('family_history','TEXT'),
                ('habits','TEXT'),('patient_type',"TEXT DEFAULT 'OPD'"),
                ('created_at','TIMESTAMP'),('updated_at','TIMESTAMP')]:
            _col(db, 'patients', col, typ)
        for col, typ in [('hospital_id','INTEGER DEFAULT 1'),
                ('visit_type','TEXT'),('token_no','INTEGER'),
                ('visit_time','TIME'),('doctor_id','INTEGER'),
                ('history_of_illness','TEXT'),('examination_findings','TEXT'),
                ('primary_diagnosis','TEXT'),('secondary_diagnosis','TEXT'),
                ('advice','TEXT'),('followup_notes','TEXT'),
                ('height','INTEGER'),('blood_sugar','REAL'),
                ('notes','TEXT'),('created_at','TIMESTAMP'),
                ('visit_date',"DATE DEFAULT (date('now'))"),
                ('prescription_image','TEXT')]:
            _col(db, 'visits', col, typ)
        for t in ('appointments','lab_orders','bills','pharmacy','admissions'):
            _col(db, t, 'hospital_id', 'INTEGER DEFAULT 1')
        _col(db, 'hospitals', 'org_id', 'TEXT')

        # Ensure default super admin account (pavithranmks22@gmail.com / demo)
        sa_email = 'pavithranmks22@gmail.com'
        sa_cols = {r[1] for r in db.execute('PRAGMA table_info(super_admins)')}
        existing_sa = db.execute('SELECT id FROM super_admins WHERE email=?',(sa_email,)).fetchone()
        if not existing_sa:
            # Also check legacy username column
            if 'username' in sa_cols:
                existing_sa = db.execute('SELECT id FROM super_admins WHERE username=?',(sa_email,)).fetchone()
        if not existing_sa:
            if 'username' in sa_cols:
                db.execute('INSERT INTO super_admins (username,email,password_hash,name,is_active) VALUES (?,?,?,?,?)',
                           (sa_email, sa_email, _h('demo'), 'Pavithran', 1))
            else:
                db.execute('INSERT INTO super_admins (email,password_hash,name,is_active) VALUES (?,?,?,?)',
                           (sa_email, _h('demo'), 'Pavithran', 1))
        # NOTE: We intentionally do NOT reset the password of an existing super
        # admin on every boot. Doing so would silently revert any password the
        # admin set themselves and is a backdoor.

        # Default hospital + settings + ward + beds
        if db.execute('SELECT COUNT(*) FROM hospitals').fetchone()[0] == 0:
            db.execute("INSERT INTO hospitals (id,org_id,name,tagline,color1,color2) VALUES (1,'ORG-001','My Hospital','Quality Healthcare','#1a6fad','#0e9f8b')")
            db.execute("INSERT INTO settings (hospital_id,doctor_name,doctor_degree) VALUES (1,'Dr. Admin','MBBS, MD')")
            wid = db.execute("INSERT INTO wards (hospital_id,name,ward_type,total_beds) VALUES (1,'General Ward','General',5)").lastrowid
            for i in range(1,6):
                db.execute("INSERT INTO beds (hospital_id,ward_id,bed_number,status) VALUES (1,?,?,?)",(wid,f'B{i:03d}','available'))

        # Auto org_id for any hospital missing it
        for h in db.execute("SELECT id FROM hospitals WHERE org_id IS NULL OR org_id='' ").fetchall():
            db.execute("UPDATE hospitals SET org_id=? WHERE id=?",(f'ORG-{h["id"]:03d}',h['id']))

        # Auto UHID org binding for patients
        for p in db.execute("SELECT id,hospital_id FROM patients WHERE uhid IS NULL OR uhid='' ").fetchall():
            db.execute("UPDATE patients SET uhid=?,org_id=? WHERE id=?",
                       (f'PT-{p["hospital_id"]:02d}-{p["id"]:05d}',
                        f'ORG-{p["hospital_id"]:03d}',p['id']))

        # Ensure at least one hospital user
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
            db.execute("INSERT INTO users (hospital_id,username,password_hash,role,name) VALUES (1,'admin',?,'admin','Hospital Admin')",(_h('demo'),))

        # Performance indexes (created idempotently). Sized for read-heavy hot paths.
        for ddl in [
            'CREATE INDEX IF NOT EXISTS idx_users_username        ON users(username)',
            'CREATE INDEX IF NOT EXISTS idx_users_hospital        ON users(hospital_id)',
            'CREATE INDEX IF NOT EXISTS idx_patients_hospital     ON patients(hospital_id)',
            'CREATE INDEX IF NOT EXISTS idx_patients_uhid         ON patients(uhid)',
            'CREATE INDEX IF NOT EXISTS idx_patients_phone        ON patients(phone)',
            'CREATE INDEX IF NOT EXISTS idx_visits_hospital_date  ON visits(hospital_id, visit_date)',
            'CREATE INDEX IF NOT EXISTS idx_visits_patient        ON visits(patient_id)',
            'CREATE INDEX IF NOT EXISTS idx_appts_hospital_date   ON appointments(hospital_id, appt_date)',
            'CREATE INDEX IF NOT EXISTS idx_appts_patient         ON appointments(patient_id)',
            'CREATE INDEX IF NOT EXISTS idx_bills_hospital_date   ON bills(hospital_id, bill_date)',
            'CREATE INDEX IF NOT EXISTS idx_bill_items_bill       ON bill_items(bill_id)',
            'CREATE INDEX IF NOT EXISTS idx_lab_orders_hospital   ON lab_orders(hospital_id)',
            'CREATE INDEX IF NOT EXISTS idx_lab_tests_order       ON lab_tests(lab_order_id)',
            'CREATE INDEX IF NOT EXISTS idx_admissions_hospital   ON admissions(hospital_id)',
            'CREATE INDEX IF NOT EXISTS idx_admissions_patient    ON admissions(patient_id)',
            'CREATE INDEX IF NOT EXISTS idx_admissions_bed        ON admissions(bed_id)',
            'CREATE INDEX IF NOT EXISTS idx_beds_ward             ON beds(ward_id)',
            'CREATE INDEX IF NOT EXISTS idx_pharmacy_patient      ON pharmacy(patient_id)',
            'CREATE INDEX IF NOT EXISTS idx_pharmacy_hospital     ON pharmacy(hospital_id)',
        ]:
            try:
                db.execute(ddl)
            except Exception:
                pass

        db.commit()
        print('[DB] Mediprax initialised OK')
