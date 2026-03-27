from flask import Flask, g, session
from .database import init_db, get_db
from .routes.auth_routes        import auth_routes
from .routes.patient_routes     import patient_routes
from .routes.visit_routes       import visit_routes
from .routes.ipd_routes         import ipd_routes
from .routes.billing_routes     import billing_routes
from .routes.lab_routes         import lab_routes
from .routes.appointment_routes import appointment_routes
from .routes.pharmacy_routes    import pharmacy_routes
from .routes.ai_routes          import ai_routes
from .routes.settings_routes    import settings_routes
from .routes.super_admin_routes import super_admin_routes

def create_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object('config.Config')
    init_db(app)
    for bp in [auth_routes, patient_routes, visit_routes, ipd_routes,
               billing_routes, lab_routes, appointment_routes, pharmacy_routes,
               ai_routes, settings_routes, super_admin_routes]:
        app.register_blueprint(bp)

    @app.context_processor
    def inject_settings():
        default = {
            'name':'Mediprax HMS','tagline':'Quality Healthcare',
            'doctor':'Dr. Admin','degree':'MBBS, MD',
            'address':'','phone':'','email':'',
            'color1':'#1a6fad','color2':'#0e9f8b'
        }
        try:
            hid = session.get('hospital_id') or 1
            db   = get_db()
            hosp = db.execute('SELECT * FROM hospitals WHERE id=?', (hid,)).fetchone()
            sett = db.execute('SELECT * FROM settings WHERE hospital_id=?', (hid,)).fetchone()
            if hosp:
                return dict(hospital={
                    'name':    hosp['name']    or default['name'],
                    'tagline': hosp['tagline'] or default['tagline'],
                    'doctor':  (sett['doctor_name']   if sett else None) or default['doctor'],
                    'degree':  (sett['doctor_degree'] if sett else None) or default['degree'],
                    'address': hosp['address'] or '',
                    'phone':   hosp['phone']   or '',
                    'email':   hosp['email']   or '',
                    'color1':  hosp['color1']  or default['color1'],
                    'color2':  hosp['color2']  or default['color2'],
                })
        except Exception:
            pass
        return dict(hospital=default)
    return app
