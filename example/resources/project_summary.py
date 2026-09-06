from bottle import response
from bottle_suite import Resource


class ProjectSummary(Resource):
    # A computed/aggregate response has no auto-CRUD equivalent at all -
    # this is the other legitimate reason (besides joins, see
    # project_tasks.py) to hand-write a Resource.
    def get(self, db, project_id):
        sql = """SELECT p.id, p.name, p.archived,
                        COUNT(t.id) AS total_tasks,
                        SUM(CASE WHEN t.done THEN 1 ELSE 0 END) AS completed_tasks
                 FROM projects p
                 LEFT JOIN tasks t ON t.project_id = p.id
                 WHERE p.id = ?
                 GROUP BY p.id"""
        row = db.execute(sql, (project_id,)).fetchone()
        if not row:
            response.status = 404
            return {"message": "Project not found"}
        row["completed_tasks"] = row["completed_tasks"] or 0
        return row
