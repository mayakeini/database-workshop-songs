# Songs Concordance System

**Open University — Database Workshop (20563)**  
**Authors:** Maya Keini Landsman and Roi Landsman  
**Implementation:** Python, Oracle Database, Streamlit

## Overview

Songs Concordance System is a text retrieval and concordance application for English-language song lyrics. It imports `.txt` song files, breaks their text down into normalized words and individual occurrences, and stores structured locations in a relational Oracle database. It supports searching, browsing word contexts, managing word groups and phrases, examining statistics, and backing up or restoring data in XML format.

The database does **not** store complete song files as single text fields. Instead, lines are reconstructed from saved word occurrences and their original tokens. Consequently, reconstruction is intended for readable search context rather than exact character-by-character reproduction of the source file (for example, spacing and punctuation-only lines may not be preserved).

## Requirements

- **Docker Desktop** (Windows) or **Docker Engine** (Linux), running and able to download container images.
- **Python 3** with `venv` and `pip` available.
- Internet access on first setup to download the Oracle image and Python dependencies.
- Available host port **1521** for Oracle and a browser-accessible Streamlit port (normally **8501**).

The startup scripts use the Docker image `gvenzl/oracle-free:23-slim`, an Oracle container named `oracle-free`, and the persistent Docker volume `oracle-free-data`.

## Quick start

Run the commands below **from the project folder** (the folder containing `app.py` and `schema.sql`).

### Windows

1. Start Docker Desktop.
2. Double-click `run_project.bat`, or run it in Command Prompt:

   ```bat
   run_project.bat
   ```

### Linux

1. Start Docker Engine.
2. Open a terminal in the project directory and run:

   ```bash
   bash run_project.sh
   ```

The scripts check prerequisites, create a Python virtual environment under `.venv`, install packages from `requirements.txt`, start or reuse the Oracle Docker container, initialize the application user/schema as needed, and launch Streamlit.

The first startup may take longer because Docker must download Oracle and initialize the database. Open the local URL printed by Streamlit (usually `http://localhost:8501`).

### Important: existing database

If the Oracle application user already exists, the script asks whether to recreate the database. **Answering Yes deletes the existing application's schema and all project data.** Answer No to keep the data. If you keep an existing database created with an older schema, ensure it is compatible with the current `schema.sql`.

The Docker volume persists across normal container restarts. Removing or recreating the container alone is not a substitute for an XML backup.

## Connection settings

The application uses the following **local development defaults**:

| Setting | Value |
| --- | --- |
| Host | `localhost` |
| Port | `1521` |
| Oracle service | `FREEPDB1` |
| Application user | `concordance` |
| Application password | `songsproject` |

The Python connection pool reads optional environment variables `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE`, `ORACLE_USER`, and `ORACLE_PASSWORD`. Its built-in defaults match the supplied startup scripts. **These credentials are for a local course demonstration, not a production deployment.** Environment variables must match the actual Oracle account and database in use.

## Manual application start

Once a compatible Oracle database is running and the Python dependencies are installed, launch the UI with:

```bash
python -m streamlit run app.py
```

If using `.venv`, activate it first, or execute its Python interpreter directly. Manual startup does not create the Oracle schema automatically; use the supplied startup script for initial setup.

## Application pages

The application consists of a home dashboard plus nine task pages:

1. **Upload Song** — upload UTF-8 `.txt` lyrics with title, artist, album (optional), and publication year; see counts of imported stanzas, lines, and words.
2. **Search** — search songs by metadata; locate word occurrences and browse context with Previous/Next; search by positions within a song.
3. **Word Index** — browse word occurrences and filter by song and/or word group.
4. **Word Groups** — create, rename, and delete groups; manage their member words and inspect their occurrences. New groups require an existing first word.
5. **Phrases** — define phrases and inspect their occurrences in lyrics.
6. **Statistics** — inspect collection/song statistics, word frequencies, word lengths, and words per stanza.
7. **Backup & Restore** — export all project tables to XML or restore them from a compatible XML backup.
8. **All Songs** — list songs with stanza, line, and word counts, and view reconstructed lyrics.
9. **Delete Song** — explicitly confirm and delete a song and its dependent records.

## Sample files

The `sample_songs/` directory contains `.txt` files for trying song upload. Use the **Upload Song** page to import them one at a time, filling in the song metadata manually. Song text is expected to be UTF-8; blank lines indicate stanza boundaries.

The `backup/` directory includes a sample XML backup. **Restoring an XML backup replaces the current project contents**; create/download a fresh backup before testing this feature with data you want to keep.

## Database design

`schema.sql` defines eight related tables:

| Table | Role |
| --- | --- |
| `SONGS` | Song metadata |
| `STANZAS` | Stanza numbering within each song |
| `WORDS` | Dictionary of normalized unique words |
| `WORD_OCCURRENCES` | Original word tokens and their exact word positions |
| `WORD_GROUPS` | User-defined named word groups |
| `GROUP_WORDS` | Many-to-many membership between groups and words |
| `PHRASES` | User-defined ordered word sequences |
| `PHRASE_OCCURRENCES` | Located phrase matches |

Primary/foreign keys, uniqueness constraints, checks, and indexes help enforce integrity and support retrieval. A case-insensitive unique index prevents word groups with names that differ only by letter case.

**Note:** This distribution includes `schema.sql` for creating the schema, but does not include a separate `drop_schema.sql` script. The startup scripts can recreate the application's Oracle user and schema after an explicit confirmation; that action deletes the existing data.

## Project structure

```text
app.py                      # Streamlit entry point / dashboard
pages/                      # Nine Streamlit pages
src/db.py                   # Oracle connection pool and transaction contexts
src/text_parser.py          # Song text parsing and word normalization
src/*_service.py            # Business operations, searches, and XML
src/queries/db_queries.py   # Oracle SQL queries
schema.sql                  # Oracle schema, constraints, and indexes
requirements.txt            # Python dependencies
run_project.bat             # Windows setup and launch
run_project.sh              # Linux setup and launch
sample_songs/               # Sample input text files
backup/                     # Example XML backup
```

## Key implementation details

- **Parameterized SQL:** query parameters are bound through `python-oracledb` rather than concatenated from user input.
- **Connection pooling:** `src/db.py` holds a reusable Oracle connection pool.
- **Transactions:** write operations use a transaction context that commits on success and rolls back on failure.
- **Text representation:** words are normalized for searching while original tokens are saved for readable context reconstruction.
- **Phrase refresh:** uploading another song updates occurrences of already defined phrases for that song.
- **XML:** full-database backup and restore preserve logical links by mapping original identifiers to newly created database identifiers during restore.

## Troubleshooting

- **Docker not found / daemon unavailable:** install and start Docker, then run the startup script again.
- **Port 1521 already in use:** stop or reconfigure the conflicting local service/container before using the supplied scripts.
- **Oracle not ready:** inspect logs with `docker logs oracle-free` and allow the initial database setup to finish.
- **Streamlit cannot connect to Oracle:** verify the Oracle container is running and the connection settings match the application account. If the account is missing, use the project startup script.
- **Existing database incompatible with `schema.sql`:** create an XML backup first and use the script's explicit recreation option only if deleting the existing database is acceptable.
- **Unexpected lyrics formatting:** text is split on whitespace and saved as word occurrences, not preserved as an exact copy of the source file.

## Academic submission

Developed for the Open University's **Database Workshop (20563)** as a course project. The associated project report describes the relational schema, implementation process, selected technologies, XML extension, and development challenges.
