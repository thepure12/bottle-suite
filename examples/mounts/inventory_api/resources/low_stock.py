from bottler import Resource

from .. import settings


class LowStock(Resource):
    def get(self, db):
        threshold = settings["low_stock_threshold"]
        db.execute(
            "SELECT * FROM products WHERE quantity < ? ORDER BY quantity",
            (threshold,),
        )
        return {"threshold": threshold, "products": db.fetchall()}
