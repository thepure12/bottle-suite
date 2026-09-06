from bottle_suite import Resource


class ProjectTasks(Resource):
    # Auto-CRUD only ever queries one table at a time, and the framework's
    # nested-ref/`levels` FK-following (the built-in way to join across
    # tables) is implemented via a MySQL-only information_schema query, so it
    # doesn't work against this sqlite-backed example. A plain hand-written
    # join is the correct way to expose this on sqlite.
    def get(self, db, project_id):
        sql = """SELECT t.id, t.title, t.priority, t.done, t.due_date,
                        GROUP_CONCAT(tg.name) AS tags
                 FROM tasks t
                 LEFT JOIN task_tags tt ON tt.task_id = t.id
                 LEFT JOIN tags tg ON tg.id = tt.tag_id
                 WHERE t.project_id = ?
                 GROUP BY t.id
                 ORDER BY t.priority, t.id"""
        return {"tasks": db.execute(sql, (project_id,)).fetchall()}
