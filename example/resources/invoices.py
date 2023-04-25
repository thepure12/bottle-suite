from bottle_suite import Resource


class Invoices(Resource):
    def get(self, db, type_id=None):
        print("Overriding generated resource")
        sql = """SELECT *
                 FROM invoices"""
        return {"media_types": db.execute(sql).fetchall()}
