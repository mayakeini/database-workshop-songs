-- Drop only the eight tables created by schema.sql.
-- WARNING: This permanently removes all project data stored in these tables.
-- Run this script while connected as the project's Oracle application user.
-- Safe to rerun: a table that does not exist is skipped (ORA-00942).
-- Dependent tables are dropped first to satisfy foreign-key constraints.
-- Indexes and constraints belonging to these tables are dropped automatically.

SET SERVEROUTPUT ON;
WHENEVER SQLERROR EXIT SQL.SQLCODE;

DECLARE
    TYPE table_name_list IS TABLE OF VARCHAR2(30);
    table_names table_name_list DEFAULT table_name_list(
        'PHRASE_OCCURRENCES',
        'GROUP_WORDS',
        'WORD_OCCURRENCES',
        'PHRASES',
        'WORD_GROUPS',
        'STANZAS',
        'WORDS',
        'SONGS'
    );
BEGIN
    FOR i IN 1 .. table_names.COUNT LOOP
        BEGIN
            EXECUTE IMMEDIATE 'DROP TABLE ' || table_names(i) || ' PURGE';
            DBMS_OUTPUT.PUT_LINE('Dropped table ' || table_names(i));
        EXCEPTION
            WHEN OTHERS THEN
                IF SQLCODE = -942 THEN
                    DBMS_OUTPUT.PUT_LINE('Table ' || table_names(i) || ' does not exist; skipped.');
                ELSE
                    RAISE;
                END IF;
        END;
    END LOOP;
END;
/

PROMPT Project schema tables dropped successfully.
