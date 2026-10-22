from bottle import request, response
from bottler import Resource

# In-memory store, so the example needs no database.
NOTES = {}


class Notes(Resource):
    # Class-level route config wins over default_roles: only tokens with
    # the "admin" role may delete.
    DELETE = {"roles": ["admin"]}

    def get(self, note_id=None):
        if note_id is None:
            return {"notes": list(NOTES.values())}
        note = NOTES.get(int(note_id))
        if not note:
            response.status = 404
            return {"message": "Note not found"}
        return note

    # Needs a token (default_roles = true). The JWT plugin puts the
    # decoded payload on request.user.
    def post(self, text):
        note_id = max(NOTES, default=0) + 1
        NOTES[note_id] = {"id": note_id, "text": text, "author": request.user["user"]}
        response.status = 201
        return NOTES[note_id]

    def delete(self, note_id):
        if NOTES.pop(int(note_id), None) is None:
            response.status = 404
            return {"message": "Note not found"}
        return {"deleted": int(note_id)}
