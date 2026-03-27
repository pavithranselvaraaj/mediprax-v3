COMPLAINTS = [
    "Abdominal pain","Abdominal cramps","Acute fever","Allergic reaction",
    "Ankle pain","Anxiety","Appetite loss","Asthma","Back pain",
    "Bleeding per rectum","Body ache","Breathlessness","Burning micturition",
    "Chest pain","Chest tightness","Chills","Cold","Constipation",
    "Cough","Cough with expectoration","Diarrhea","Difficulty swallowing",
    "Dizziness","Dry cough","Ear pain","Edema feet","Eye pain","Eye redness",
    "Fever with cold","Fever without cold","Fatigue","Facial swelling",
    "Frequent urination","Giddiness","Gastritis","Generalized weakness",
    "Headache","Heartburn","High blood pressure","Hip pain",
    "Indigestion","Insomnia","Itching","Jaundice","Joint pain",
    "Knee pain","Leg pain","Leg swelling","Loss of appetite","Low back pain",
    "Mouth ulcer","Muscle pain","Myalgia","Nasal discharge","Nausea",
    "Neck pain","Numbness","Nausea with vomiting","Palpitation","Pedal edema",
    "RTA","Rash","Running nose","Shortness of breath","Sore throat",
    "Stomach pain","Swelling","Skin rash","Throat pain","Tiredness",
    "Tremors","Urinary complaints","Vertigo","Vision changes","Vomiting",
    "Weakness","Weight loss","Wheezing",
]

MEDICINES = [
    "Tab. Paracetamol 500mg","Tab. Paracetamol 650mg",
    "Syr. Paracetamol 125mg/5ml","Tab. Ibuprofen 400mg",
    "Tab. Diclofenac 50mg","Tab. Aceclofenac 100mg",
    "Tab. Nimesulide 100mg","Tab. Amoxicillin 500mg",
    "Tab. Amoxicillin + Clavulanate 625mg","Tab. Azithromycin 500mg",
    "Tab. Ciprofloxacin 500mg","Tab. Levofloxacin 500mg",
    "Tab. Metronidazole 400mg","Tab. Cefixime 200mg",
    "Tab. Cetirizine 10mg","Tab. Levocetirizine 5mg",
    "Tab. Montelukast 10mg","Tab. Montelukast + Levocetirizine",
    "Tab. Omeprazole 20mg","Tab. Pantoprazole 40mg",
    "Tab. Domperidone 10mg","Tab. Ondansetron 4mg",
    "Syr. ORS Powder","Tab. Prednisolone 10mg",
    "Tab. Amlodipine 5mg","Tab. Atenolol 50mg",
    "Tab. Metformin 500mg","Tab. Glimepiride 2mg",
    "Tab. Atorvastatin 10mg","Tab. Vitamin D3 60000 IU (weekly)",
    "Tab. Calcium + Vitamin D3","Tab. Ferrous Ascorbate",
    "Tab. Methylcobalamin 500mcg","Tab. Vitamin B Complex",
    "Inhaler Salbutamol 100mcg","Tab. Levothyroxine 50mcg",
    "Inj. Ceftriaxone 1g","Inj. Ondansetron 4mg/2ml",
    "Inj. Normal Saline 500ml","Inj. Ringer Lactate 500ml",
]

def suggest_complaint(q):
    if not q:
        return []
    q = q.lower()
    starts   = [c for c in COMPLAINTS if c.lower().startswith(q)]
    contains = [c for c in COMPLAINTS if q in c.lower() and not c.lower().startswith(q)]
    return (starts + contains)[:12]

def suggest_medicine(q):
    if not q:
        return []
    q = q.lower()
    starts   = [m for m in MEDICINES if m.lower().startswith(q)]
    contains = [m for m in MEDICINES if q in m.lower() and not m.lower().startswith(q)]
    return (starts + contains)[:14]
