from bottle_suite import Resource


class ProjectTasks(Resource):
    # Auto-CRUD's nested-ref/`levels` FK-following only follows one
    # relationship at a time; this response joins three tables
    # (tasks -> task_tags -> tags) into one flattened row per task with a
    # concatenated tag list, which is beyond what a single FK hop can do.
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
