from bottle_suite import Resource


class PlaylistTrack(Resource):
    def get(self, db, playlist_id):
        sql = """SELECT t.TrackId, t.Name, a.Title AlbumTitle, m.Name MediaType, g.Name Genre, 
                        t.Composer, t.Milliseconds, t.Bytes, t.UnitPrice
                 FROM playlists p, tracks t, playlist_track pt, albums a, media_types m, genres g
                 WHERE p.PlaylistId = ?
                 AND pt.TrackId = t.TrackId
                 AND pt.PlaylistId = p.PlaylistId
                 AND t.AlbumId = a.AlbumId
                 AND t.MediaTypeId = m.MediaTypeId
                 AND t.GenreId = g.GenreId"""
        return {"tracks": db.execute(sql, (playlist_id,)).fetchall()}
