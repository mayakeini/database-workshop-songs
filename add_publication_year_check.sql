-- Apply to an EXISTING concordance schema without deleting songs.
-- First review the results of this query; it must return no rows:
SELECT song_id, title, publication_year
FROM songs
WHERE publication_year NOT BETWEEN 1000 AND 2100;

-- Adds database-level validation to the existing table.
-- Oracle rejects this ALTER if invalid data is present.
ALTER TABLE songs
    ADD CONSTRAINT chk_songs_publication_year
    CHECK (publication_year BETWEEN 1000 AND 2100);
