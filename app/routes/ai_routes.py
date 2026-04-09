from flask import Blueprint, request, jsonify
ai_routes = Blueprint('ai', __name__, url_prefix='/ai')

COMPLAINTS = ['Fever with cold','Fever without cold','Headache','Giddiness','Vomiting','Nausea',
    'Abdominal pain','Chest pain','Cough','Breathlessness','Back pain','Joint pain',
    'RTA injuries','Skin rash','Burning micturition','Loose stools','Constipation',
    'Loss of appetite','Fatigue','Swelling']
MEDICINES  = ['Tab. Paracetamol 500mg','Tab. Paracetamol 650mg','Tab. Amoxicillin 500mg',
    'Tab. Azithromycin 500mg','Tab. Cetirizine 10mg','Tab. Pantoprazole 40mg',
    'Tab. Metformin 500mg','Tab. Amlodipine 5mg','Tab. Atorvastatin 10mg',
    'Tab. Ibuprofen 400mg','Tab. Diclofenac 50mg','Syr. Amoxicillin 125mg/5ml',
    'Syr. Paracetamol 125mg/5ml','Inj. Dexamethasone','Inj. Ondansetron']

@ai_routes.route('/complaint')
def complaint():
    q = request.args.get('q','').strip().lower()
    return jsonify([c for c in COMPLAINTS if q in c.lower()] if q else COMPLAINTS[:8])

@ai_routes.route('/medicine')
def medicine():
    q = request.args.get('q','').strip().lower()
    return jsonify([m for m in MEDICINES if q in m.lower()] if q else MEDICINES[:8])
