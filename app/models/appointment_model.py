from ..database import get_db

def create_appointment(data):

    db = get_db()

    db.execute(
        """INSERT INTO appointments
        (patient_id,doctor,date,status)
        VALUES (?,?,?,?)""",

        (data["patient_id"],
         data["doctor"],
         data["date"],
         "scheduled")
    )

    db.commit()