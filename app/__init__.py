from flask import Flask, session
import os
from .database import init_db, get_db
from .routes.auth_routes        import auth_routes
from .routes.patient_routes     import patient_routes
from .routes.visit_routes       import visit_routes
from .routes.appointment_routes import appointment_routes
from .routes.lab_routes         import lab_routes
from .routes.pharmacy_routes    import pharmacy_routes
from .routes.ai_routes          import ai_routes
from .routes.settings_routes    import settings_routes
from .routes.super_admin_routes import super_admin_routes
from .routes.billing_routes     import billing_routes
from .routes.ipd_routes         import ipd_routes

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object('config.Config')
    # Force template auto-reload for development
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Ensure upload folder exists
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads/prescriptions'), exist_ok=True)

    init_db(app)

    for bp in [auth_routes, patient_routes, visit_routes, appointment_routes,
               lab_routes, pharmacy_routes, ai_routes, settings_routes, super_admin_routes,
               billing_routes, ipd_routes]:
        app.register_blueprint(bp)

    @app.context_processor
    def inject_hospital():
        """Every template gets {{ hospital.name }}, {{ hospital.org_id }}, etc."""
        default = {'name':'Mediprax HMS','tagline':'Quality Healthcare',
                   'doctor':'Dr. Admin','degree':'MBBS, MD',
                   'address':'','phone':'','email':'',
                   'color1':'#1a6fad','color2':'#0e9f8b','org_id':''}
        try:
            hid = session.get('hospital_id')
            if not hid:
                return dict(hospital=default)
            db  = get_db()
            h   = db.execute('SELECT * FROM hospitals WHERE id=?',(hid,)).fetchone()
            s   = db.execute('SELECT * FROM settings WHERE hospital_id=?',(hid,)).fetchone()
            if h:
                # Ensure org_id is present for hospital
                org = h['org_id'] or f'ORG-{h["id"]:03d}'
                if not h['org_id']:
                    db.execute('UPDATE hospitals SET org_id=? WHERE id=?',(org,h['id'])); db.commit()
                return dict(hospital={
                    'name':    h['name']    or default['name'],
                    'tagline': h['tagline'] or default['tagline'],
                    'doctor':  (s['doctor_name']   if s else None) or default['doctor'],
                    'degree':  (s['doctor_degree'] if s else None) or default['degree'],
                    'address': h['address'] or '',
                    'phone':   h['phone']   or '',
                    'email':   h['email']   or '',
                    'color1':  h['color1']  or default['color1'],
                    'color2':  h['color2']  or default['color2'],
                    'org_id':  org,
                })
        except Exception:
            pass
        return dict(hospital=default)

    return app
