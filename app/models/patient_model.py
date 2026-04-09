from ..database import get_db

def get_all_patients():

    db = get_db()

    return db.execute(
        "SELECT * FROM patients"
    ).fetchall()


def add_patient(data):

    db = get_db()

    db.execute(
        """INSERT INTO patients
        (name,age,gender,phone,address)
        VALUES (?,?,?,?,?)""",

        (data["name"],data["age"],data["gender"],
         data["phone"],data["address"])
    )

    db.commit()