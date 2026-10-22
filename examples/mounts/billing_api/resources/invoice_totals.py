from bottler import Resource


class InvoiceTotals(Resource):
    # `db` is a cursor on billing's own database, not inventory's.
    def get(self, db):
        db.execute(
            """SELECT COUNT(*) AS invoices,
                      SUM(amount) AS billed,
                      SUM(CASE WHEN paid THEN 0 ELSE amount END) AS outstanding
               FROM invoices"""
        )
        return db.fetchone()
