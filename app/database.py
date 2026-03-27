import sqlite3, hashlib, os
from flask import g, current_app

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

def _add_col(db, table, col, typ):
    try:
        cols = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
        if col not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    except Exception as e:
        pass

def init_db(app):
    @app.teardown_appcontext
    def close_db(e=None):
        db = g.pop('db', None)
        if db: db.close()

    with app.app_context():
        db = get_db()
        db.executescript("""

        -- ═══════════════════════════════════════════════════
        --  SUPER ADMIN + HOSPITALS
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS super_admins(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hospitals(
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            tagline    TEXT DEFAULT 'Quality Healthcare',
            address    TEXT DEFAULT '',
            phone      TEXT DEFAULT '',
            email      TEXT DEFAULT '',
            color1     TEXT DEFAULT '#1a6fad',
            color2     TEXT DEFAULT '#0e9f8b',
            is_active  INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings(
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id    INTEGER UNIQUE NOT NULL,
            doctor_name    TEXT DEFAULT '',
            doctor_degree  TEXT DEFAULT 'MBBS, MD',
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );

        -- ═══════════════════════════════════════════════════
        --  STAFF / USERS
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS users(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id   INTEGER NOT NULL,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'nurse'
                          CHECK(role IN ('admin','doctor','nurse','patient')),
            name          TEXT NOT NULL,
            specialization TEXT DEFAULT '',
            phone         TEXT DEFAULT '',
            patient_id    INTEGER,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );

        -- ═══════════════════════════════════════════════════
        --  BEDS / WARDS
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS wards(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            name        TEXT NOT NULL,
            ward_type   TEXT DEFAULT 'General'
                        CHECK(ward_type IN ('General','ICU','Private','Semi-Private','Emergency','Maternity','Paediatric','Surgical')),
            total_beds  INTEGER DEFAULT 0,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );

        CREATE TABLE IF NOT EXISTS beds(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            ward_id     INTEGER NOT NULL,
            bed_number  TEXT NOT NULL,
            status      TEXT DEFAULT 'available'
                        CHECK(status IN ('available','occupied','maintenance','reserved')),
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (ward_id)     REFERENCES wards(id)
        );

        -- ═══════════════════════════════════════════════════
        --  PATIENTS (enhanced)
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS patients(
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id       INTEGER NOT NULL,
            uhid              TEXT,
            name              TEXT NOT NULL,
            dob               DATE,
            age               INTEGER,
            gender            TEXT,
            guardian_name     TEXT DEFAULT '',
            guardian_relation TEXT DEFAULT '',
            emergency_contact TEXT DEFAULT '',
            emergency_phone   TEXT DEFAULT '',
            insurance         TEXT DEFAULT '',
            insurance_no      TEXT DEFAULT '',
            blood_group       TEXT DEFAULT '',
            rh_factor         TEXT DEFAULT '',
            height_cm         INTEGER,
            address           TEXT DEFAULT '',
            city              TEXT DEFAULT '',
            state             TEXT DEFAULT '',
            phone             TEXT DEFAULT '',
            email             TEXT DEFAULT '',
            individual_number TEXT DEFAULT '',
            occupation        TEXT DEFAULT '',
            marital_status    TEXT DEFAULT '',
            religion          TEXT DEFAULT '',
            nationality       TEXT DEFAULT 'Indian',
            comorbidity       TEXT DEFAULT '',
            known_allergies   TEXT DEFAULT '',
            past_medical_history TEXT DEFAULT '',
            past_surgical_history TEXT DEFAULT '',
            family_history    TEXT DEFAULT '',
            habits            TEXT DEFAULT '',
            patient_type      TEXT DEFAULT 'OPD'
                              CHECK(patient_type IN ('OPD','IPD','Emergency')),
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );

        -- ═══════════════════════════════════════════════════
        --  IPD ADMISSIONS
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS admissions(
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id         INTEGER NOT NULL,
            patient_id          INTEGER NOT NULL,
            admission_no        TEXT,
            admission_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admission_type      TEXT DEFAULT 'Elective'
                                CHECK(admission_type IN ('Emergency','Elective','Referral','Transfer')),
            ward_id             INTEGER,
            bed_id              INTEGER,
            admitting_doctor_id INTEGER,
            diagnosis_at_admission TEXT DEFAULT '',
            attendant_name      TEXT DEFAULT '',
            attendant_phone     TEXT DEFAULT '',
            attendant_relation  TEXT DEFAULT '',
            status              TEXT DEFAULT 'admitted'
                                CHECK(status IN ('admitted','discharged','transferred','absconded','died')),
            discharge_date      TIMESTAMP,
            discharge_type      TEXT DEFAULT ''
                                CHECK(discharge_type IN ('','Recovered','Improved','LAMA','Referred','Expired','Transfer')),
            discharge_summary   TEXT DEFAULT '',
            final_diagnosis     TEXT DEFAULT '',
            discharge_instructions TEXT DEFAULT '',
            condition_at_discharge TEXT DEFAULT ''
                                CHECK(condition_at_discharge IN ('','Stable','Critical','Improved','Unchanged','Expired')),
            created_by          INTEGER,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id)  REFERENCES hospitals(id),
            FOREIGN KEY (patient_id)   REFERENCES patients(id),
            FOREIGN KEY (ward_id)      REFERENCES wards(id),
            FOREIGN KEY (bed_id)       REFERENCES beds(id)
        );

        -- ═══════════════════════════════════════════════════
        --  VISITS / CONSULTATIONS (OPD + IPD rounds)
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS visits(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id   INTEGER NOT NULL,
            patient_id    INTEGER NOT NULL,
            admission_id  INTEGER,
            visit_type    TEXT DEFAULT 'OPD'
                          CHECK(visit_type IN ('OPD','IPD','Emergency')),
            token_no      INTEGER,
            visit_date    DATE NOT NULL,
            visit_time    TIME,
            doctor_id     INTEGER,
            complaints    TEXT DEFAULT '',
            history_of_illness TEXT DEFAULT '',
            examination_findings TEXT DEFAULT '',
            primary_diagnosis TEXT DEFAULT '',
            secondary_diagnosis TEXT DEFAULT '',
            investigation TEXT DEFAULT '',
            prescription  TEXT DEFAULT '',
            notes         TEXT DEFAULT '',
            advice        TEXT DEFAULT '',
            -- Vitals
            bp_systolic   INTEGER,
            bp_diastolic  INTEGER,
            pulse         INTEGER,
            temperature   REAL,
            weight        REAL,
            height        INTEGER,
            spo2          INTEGER,
            rr            INTEGER,
            blood_sugar   REAL,
            -- Follow-up
            followup_date DATE,
            followup_notes TEXT DEFAULT '',
            created_by    INTEGER,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (patient_id)  REFERENCES patients(id)
        );

        -- ═══════════════════════════════════════════════════
        --  LAB INVESTIGATIONS
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS lab_orders(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id  INTEGER NOT NULL,
            visit_id    INTEGER,
            ordered_by  INTEGER,
            order_date  DATE NOT NULL,
            status      TEXT DEFAULT 'pending'
                        CHECK(status IN ('pending','sample_collected','in_progress','completed','cancelled')),
            notes       TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lab_tests(
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lab_order_id  INTEGER NOT NULL,
            test_name     TEXT NOT NULL,
            test_category TEXT DEFAULT 'General',
            result        TEXT DEFAULT '',
            unit          TEXT DEFAULT '',
            reference_range TEXT DEFAULT '',
            status        TEXT DEFAULT 'pending',
            result_date   DATE,
            remarks       TEXT DEFAULT '',
            FOREIGN KEY (lab_order_id) REFERENCES lab_orders(id)
        );

        -- ═══════════════════════════════════════════════════
        --  BILLING
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS bills(
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id    INTEGER NOT NULL,
            patient_id     INTEGER NOT NULL,
            visit_id       INTEGER,
            admission_id   INTEGER,
            bill_no        TEXT,
            bill_date      DATE NOT NULL,
            bill_type      TEXT DEFAULT 'OPD'
                           CHECK(bill_type IN ('OPD','IPD','Emergency','Lab','Pharmacy')),
            subtotal       REAL DEFAULT 0,
            discount       REAL DEFAULT 0,
            tax            REAL DEFAULT 0,
            total          REAL DEFAULT 0,
            paid_amount    REAL DEFAULT 0,
            payment_mode   TEXT DEFAULT 'Cash'
                           CHECK(payment_mode IN ('Cash','Card','UPI','Insurance','Cheque','Online')),
            payment_status TEXT DEFAULT 'pending'
                           CHECK(payment_status IN ('pending','partial','paid','waived')),
            insurance_claim TEXT DEFAULT '',
            notes          TEXT DEFAULT '',
            created_by     INTEGER,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id),
            FOREIGN KEY (patient_id)  REFERENCES patients(id)
        );

        CREATE TABLE IF NOT EXISTS bill_items(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id     INTEGER NOT NULL,
            category    TEXT DEFAULT 'Consultation'
                        CHECK(category IN ('Consultation','Procedure','Lab','Medicine','Room','Nursing','Other')),
            description TEXT NOT NULL,
            quantity    REAL DEFAULT 1,
            unit_price  REAL DEFAULT 0,
            amount      REAL DEFAULT 0,
            FOREIGN KEY (bill_id) REFERENCES bills(id)
        );

        -- ═══════════════════════════════════════════════════
        --  APPOINTMENTS
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS appointments(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id  INTEGER,
            doctor_id   INTEGER,
            appt_date   TEXT NOT NULL,
            appt_time   TEXT DEFAULT '',
            reason      TEXT DEFAULT '',
            status      TEXT DEFAULT 'scheduled'
                        CHECK(status IN ('scheduled','confirmed','completed','cancelled','no_show')),
            token_no    INTEGER,
            notes       TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );

        -- ═══════════════════════════════════════════════════
        --  PHARMACY
        -- ═══════════════════════════════════════════════════
        CREATE TABLE IF NOT EXISTS pharmacy(
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_id INTEGER NOT NULL,
            patient_id  INTEGER,
            visit_id    INTEGER,
            medicine    TEXT NOT NULL,
            quantity    REAL DEFAULT 1,
            unit        TEXT DEFAULT 'Tablets',
            price       REAL DEFAULT 0,
            dispensed_by INTEGER,
            dispensed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
        );
        """)

        # ── Migrations for old DBs ──────────────────────────
        for col, typ in [('uhid','TEXT'),('guardian_relation','TEXT'),
                ('emergency_contact','TEXT'),('emergency_phone','TEXT'),
                ('insurance_no','TEXT'),('rh_factor','TEXT'),
                ('height_cm','INTEGER'),('city','TEXT'),('state','TEXT'),
                ('email','TEXT'),('occupation','TEXT'),('marital_status','TEXT'),
                ('religion','TEXT'),('nationality','TEXT DEFAULT "Indian"'),
                ('known_allergies','TEXT'),('past_medical_history','TEXT'),
                ('past_surgical_history','TEXT'),('family_history','TEXT'),
                ('habits','TEXT'),('patient_type','TEXT DEFAULT "OPD"')]:
            _add_col(db, 'patients', col, typ)

        for col, typ in [('admission_id','INTEGER'),('visit_type','TEXT'),
                ('token_no','INTEGER'),('visit_time','TIME'),('doctor_id','INTEGER'),
                ('history_of_illness','TEXT'),('examination_findings','TEXT'),
                ('primary_diagnosis','TEXT'),('secondary_diagnosis','TEXT'),
                ('advice','TEXT'),('followup_notes','TEXT'),
                ('height','INTEGER'),('blood_sugar','REAL'),
                ('notes','TEXT'),('created_at','TIMESTAMP')]:
            _add_col(db, 'visits', col, typ)

        # ── Auto-generate UHID for existing patients ────────
        patients_no_uhid = db.execute(
            "SELECT id, hospital_id FROM patients WHERE uhid IS NULL OR uhid=''"
        ).fetchall()
        for p in patients_no_uhid:
            uhid = f"PT-{p['hospital_id']:02d}-{p['id']:05d}"
            db.execute("UPDATE patients SET uhid=? WHERE id=?", (uhid, p['id']))

        # ── Default super admin ─────────────────────────────
        if db.execute("SELECT COUNT(*) FROM super_admins").fetchone()[0] == 0:
            pwd = hashlib.sha256('SuperAdmin@123'.encode()).hexdigest()
            db.execute("INSERT INTO super_admins (username,password_hash) VALUES (?,?)",
                       ('superadmin', pwd))

        # ── Default hospital ────────────────────────────────
        if db.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0] == 0:
            db.execute("""INSERT INTO hospitals (id,name,tagline,color1,color2)
                VALUES (1,'My Hospital','Quality Healthcare','#1a6fad','#0e9f8b')""")
            db.execute("INSERT INTO settings (hospital_id,doctor_name,doctor_degree) VALUES (1,'Dr. Admin','MBBS, MD')")
            # Default ward + beds
            db.execute("INSERT INTO wards (hospital_id,name,ward_type,total_beds) VALUES (1,'General Ward','General',10)")
            for i in range(1, 11):
                db.execute("INSERT INTO beds (hospital_id,ward_id,bed_number,status) VALUES (1,1,?,?)",
                           (f'B{i:03d}', 'available'))

        # ── Default doctor if no users ──────────────────────
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            pwd = hashlib.sha256('Doctor@123'.encode()).hexdigest()
            db.execute("""INSERT INTO users (hospital_id,username,password_hash,role,name)
                VALUES (1,'doctor',?,'admin','Dr. Admin')""", (pwd,))

        db.commit()
        print("[DB] v2 Initialised OK")
