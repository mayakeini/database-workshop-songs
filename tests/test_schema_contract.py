"""Static Oracle-schema contract tests, independent of external packages."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SchemaContractTests(unittest.TestCase):
    """Ensure project constraints and schema cleanup remain present."""

    def test_year_check_exists(self) -> None:
        """Require a database check constraint on publication year."""
        sql = (ROOT / 'schema.sql').read_text(encoding='utf-8').lower()
        self.assertIn('chk_songs_publication_year', sql)
        self.assertRegex(sql, r'publication_year\s+between\s+1000\s+and\s+2100')

    def test_group_names_case_insensitive_unique(self) -> None:
        """Require Oracle-level case-insensitive unique index."""
        sql = (ROOT / 'schema.sql').read_text(encoding='utf-8').lower()
        self.assertRegex(sql, r'create\s+unique\s+index\s+ux_word_groups_name_ci')
        self.assertIn('lower(group_name)', sql)

    def test_drop_schema_lists_eight_project_tables(self) -> None:
        """Keep all project tables listed for optional teardown."""
        sql = (ROOT / 'drop_schema.sql').read_text(encoding='utf-8').upper()
        for name in ('SONGS', 'STANZAS', 'WORDS', 'WORD_OCCURRENCES',
                     'WORD_GROUPS', 'GROUP_WORDS', 'PHRASES', 'PHRASE_OCCURRENCES'):
            self.assertIn(f"'{name}'", sql)

    def test_no_oneoff_publication_year_script_in_submission(self) -> None:
        """The temporary migration script must not ship."""
        self.assertFalse((ROOT / 'add_publication_year_check.sql').exists())


if __name__ == '__main__':
    unittest.main()
