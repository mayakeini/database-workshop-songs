# Database Workshop - Songs Concordance System

A database workshop project for managing, indexing, searching, and analyzing English song lyrics.

The system is implemented in Python, uses Oracle Database for data storage, and provides a web interface using Streamlit.

## Project Overview

The project implements a concordance and text retrieval system for a collection of English songs.

The system allows users to:

- Upload song lyrics from TXT files.
- Store song metadata.
- Parse songs into stanzas and word occurrences.
- Search songs by metadata.
- Search for specific words.
- Display all occurrences of a word.
- Display the textual context around each occurrence.
- Search by word location.
- Browse a complete word index.
- Create and manage custom word groups.
- Define phrases and search for their occurrences.
- View textual and statistical information about the song collection.
- Export the entire database to XML.
- Restore the database from an XML backup.

## Technologies

The project uses:

- Python
- Oracle Database
- Streamlit
- python-oracledb
- pandas
- Altair
- python-dotenv
- XML using Python's `xml.etree.ElementTree`
- Git and GitHub

## Architecture

The system is divided into several layers.

### Text Processing Layer

Responsible for:

- Reading TXT files.
- Splitting songs into stanzas and lines.
- Splitting lines into words.
- Normalizing words for search.
- Preserving the original token for text reconstruction.
- Calculating the location of each word inside the song.

### Database Layer

Oracle Database stores:

- Songs
- Stanzas
- Unique words
- Word occurrences
- Word groups
- Word-to-group relationships
- Phrases
- Phrase occurrences

The system does not store complete song lines in a separate table.

Instead, lines and full song texts are reconstructed from the word occurrence table using the stored location information.

### Service Layer

Python service modules handle the main application logic:

- Song loading
- Text parsing
- Search
- Word groups
- Phrases
- Statistics
- XML backup and restore
- Database connection

### User Interface Layer

The Streamlit interface provides separate pages for:

1. Upload Song
2. Search
3. Word Index
4. Word Groups
5. Phrases
6. Statistics
7. Backup & Restore

## Project Structure

database-workshop-songs/
│
├── app.py
├── README.md
├── requirements.txt
├── .gitignore
│
├── src/
│   ├── __init__.py
│   ├── db.py
│   ├── logger_config.py
│   ├── text_parser.py
│   ├── song_service.py
│   ├── search_service.py
│   ├── group_service.py
│   ├── phrase_service.py
│   ├── statistics_service.py
│   └── xml_service.py
│
├── pages/
│   ├── 1_Upload_Song.py
│   ├── 2_Search.py
│   ├── 3_Word_Index.py
│   ├── 4_Word_Groups.py
│   ├── 5_Phrases.py
│   ├── 6_Statistics.py
│   └── 7_Backup_Restore.py
│
└── sample_songs/
    └── example.txt

## Database Schema

The project contains the following main tables.

### SONGS

Stores general song information:

- Song ID
- Title
- Artist
- Album
- Publication year
- Upload date

### STANZAS

Stores the stanza structure of each song.

### WORDS

Stores every normalized word once.

For example:

Love
love,
LOVE!

are all represented by the normalized word:

love

### WORD_OCCURRENCES

Stores every occurrence of every word.

Each occurrence includes:

- Word ID
- Song ID
- Stanza ID
- Global line number
- Line number inside the stanza
- Position inside the line
- Position inside the song
- Original token

This table allows the system to reconstruct complete lines and songs without storing duplicated line text.

### WORD_GROUPS

Stores custom word groups created by users.

### GROUP_WORDS

Stores the many-to-many relationship between words and word groups.

### PHRASES

Stores phrase definitions.

### PHRASE_OCCURRENCES

Stores the start and end occurrence of each phrase found inside the songs.

## Song Parsing

Each TXT file represents one song.

A blank line separates stanzas.

Example:

Hello, beautiful world!
This is my song.

Love is in the air,
And love is everywhere.

The parser produces word occurrences such as:

hello       stanza=1 line=1 position=1
beautiful   stanza=1 line=1 position=2
world       stanza=1 line=1 position=3
this        stanza=1 line=2 position=1
love        stanza=2 line=3 position=1

The original token is also preserved, allowing punctuation to be reconstructed.

For example:

Normalized word: hello
Original token: Hello,

## Search Features

### Song Search

Songs can be searched by:

- Title
- Artist
- Album
- Publication year

### Word Search

For each searched word, the system displays:

- Song
- Artist
- Stanza
- Global line number
- Line number inside the stanza
- Position inside the line
- Position inside the song
- Surrounding context

### Context

The system displays:

- Previous line
- Current line
- Next line

when those lines exist.

### Location Search

Users can search using:

- Global line number
- Stanza number and local line number
- Word position inside a line

## Word Index

The word index displays all word occurrences in alphabetical order.

For each occurrence, the system displays the location in multiple forms, including:

- Global line number
- Stanza number
- Line number inside the stanza
- Position inside the line

The index can also be filtered by song and exported to CSV.

## Word Groups

Users can:

- Create a group
- Edit a group
- Delete a group
- Add existing words to a group
- Remove words from a group
- View all words in a group
- View all occurrences of the group's words

## Phrases

Users can define multi-word phrases such as:

love is

The system searches for consecutive matching word occurrences inside the same line.

For each phrase occurrence, the system stores:

- Song
- Start word occurrence
- End word occurrence

The interface also displays the surrounding context.

## Statistics

The system provides statistics for the entire database or for a specific song.

Available statistics include:

- Number of songs
- Number of stanzas
- Number of lines
- Total number of words
- Number of unique words
- Average word length
- Average number of words per line
- Most frequent words
- Rarest words
- Word length distribution
- Number of words per stanza

Charts are displayed using Altair.

## XML Backup and Restore

The XML functionality is the additional topic implemented in the project.

The system can export the complete database into a single XML file.

The backup contains:

- Songs
- Stanzas
- Words
- Word occurrences
- Word groups
- Group-word relationships
- Phrases
- Phrase occurrences

The database can later be restored from the XML backup.

During restoration, new Oracle IDs are generated and mappings are used to rebuild all relationships correctly.

The restore operation is performed inside a database transaction.

If an error occurs, the operation is rolled back so that partial data is not left in the database.

## Logging

The project uses Python's built-in `logging` module.

Logs are used for:

- Application startup
- Database connections
- Song parsing
- Song insertion
- Search operations
- Group management
- Phrase management
- Statistics
- XML export and restore
- Error handling

## Environment Variables

Database credentials are stored in a local `.env` file.

Example:

ORACLE_HOST=localhost
ORACLE_PORT=1521
ORACLE_SERVICE=FREEPDB1
ORACLE_USER=concordance
ORACLE_PASSWORD=your_password

The `.env` file must not be committed to Git.

## Installation

Create and activate a virtual environment.

Install the dependencies:

pip install -r requirements.txt

The requirements include packages such as:

oracledb
streamlit
python-dotenv
pandas
altair

## Oracle Database

The project uses Oracle Database Free running locally.

Example connection settings:

Host: localhost
Port: 1521
Service Name: FREEPDB1
User: concordance

The application user must have the required permissions to access and modify the project objects.

## Running the Application

Make sure Oracle Database is running.

Then start Streamlit:

python -m streamlit run app.py 
if it doesn't work try:
.\.venv\Scripts\python.exe -m streamlit run app.py

The application will usually open at:

http://localhost:8501

## Authors

Maya Keini  
Roi Lantzman

Open University - Database Workshop