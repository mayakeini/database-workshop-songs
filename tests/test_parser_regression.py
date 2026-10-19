"""Parser regression tests, independent of Oracle/Streamlit."""
import tempfile
import unittest
from pathlib import Path

from src.text_parser import parse_song


class TextParserRegressionTests(unittest.TestCase):
    """Validate word numbering, stanza boundaries and punctuation."""

    def parse_text(self, content: str) -> list[dict]:
        """Parse content written into a temporary UTF-8 text file."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "song.txt"
            path.write_text(content, encoding="utf-8")
            return parse_song(str(path))

    def test_standalone_punctuation_does_not_skip_position(self) -> None:
        """Punctuation tokens attach to a word without consuming positions."""
        rows = self.parse_text("Hi ! there .\n")
        self.assertEqual([row['position_in_line'] for row in rows], [1, 2])
        self.assertEqual([row['position_in_song'] for row in rows], [1, 2])
        self.assertEqual([row['original_token'] for row in rows], ['Hi!', 'there.'])

    def test_leading_punctuation_attaches_to_first_word(self) -> None:
        """A leading punctuation token must not disappear."""
        rows = self.parse_text('( hello ) world\n')
        self.assertEqual([row['original_token'] for row in rows], ['(hello)', 'world'])
        self.assertEqual([row['position_in_line'] for row in rows], [1, 2])

    def test_blank_lines_separate_stanzas_without_empty_stanzas(self) -> None:
        """Repeated empty lines do not create empty stanza records."""
        rows = self.parse_text('\n\nOne two\n\n\nThree\n\nFour five\n')
        self.assertEqual([row['stanza_number'] for row in rows], [1, 1, 2, 3, 3])
        self.assertEqual([row['global_line_number'] for row in rows], [1, 1, 2, 3, 3])
        self.assertEqual([row['line_number_in_stanza'] for row in rows], [1, 1, 1, 1, 1])

    def test_apostrophes_and_case_normalization(self) -> None:
        """Apostrophes within words are kept when normalizing."""
        rows = self.parse_text("Don't I'M LOVE!\n")
        self.assertEqual([row['normalized_word'] for row in rows], ["don't", "i'm", 'love'])

    def test_only_punctuation_produces_no_words(self) -> None:
        """Punctuation-only content does not create fake words."""
        with self.assertLogs('src.text_parser', level='WARNING'):
            rows = self.parse_text('... !!!\n')
        self.assertEqual(rows, [])

    def test_word_positions_restart_per_line(self) -> None:
        """Local positions restart; global positions keep incrementing."""
        rows = self.parse_text('One two\nThree four\n')
        self.assertEqual([r['position_in_line'] for r in rows], [1, 2, 1, 2])
        self.assertEqual([r['position_in_song'] for r in rows], [1, 2, 3, 4])


if __name__ == '__main__':
    unittest.main()
