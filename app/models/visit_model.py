from ..database import get_db

def add_visit(data):

    db = get_db()

    db.execute(
        """INSERT INTO visits
        (patient_id,complaints,investigation,prescription)
        VALUES (?,?,?,?)""",

        (data["patient_id"],
         data["complaints"],
         data["investigation"],
         data["prescription"])
    )

    db.commit()