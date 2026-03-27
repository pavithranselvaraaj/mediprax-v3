from ..database import get_db

def add_lab_report(data):

    db = get_db()

    db.execute(
        """INSERT INTO lab_reports
        (patient_id,test_name,result)
        VALUES (?,?,?)""",

        (data["patient_id"],
         data["test_name"],
         data["result"])
    )

    db.commit()