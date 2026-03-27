from ..database import get_db

def add_bill(data):

    db = get_db()

    db.execute(
        """INSERT INTO pharmacy
        (patient_id,medicine,quantity,price)
        VALUES (?,?,?,?)""",

        (data["patient_id"],
         data["medicine"],
         data["quantity"],
         data["price"])
    )

    db.commit()