import unittest

from core.rtf_editor import apply_equivalences, course_exists_in_detail


SAMPLE_RTF = rb"""{\rtf1\ansi
\pard \posx1587\posy4222\absh-482\absw6085 {\b ELECTIVO TRACK 1
\par }{\b
\par }\pard \posx732\posy4222\absh-192\absw825 {\b STRK128
\par }\pard \posx60 OTRO CONTENIDO\par
}"""


class RtfEditorTests(unittest.TestCase):
    def test_finds_only_detail_course_anchor(self):
        self.assertTrue(course_exists_in_detail(SAMPLE_RTF, "STRK128"))
        self.assertFalse(course_exists_in_detail(SAMPLE_RTF, "STT123"))

    def test_inserts_equivalence_in_reserved_heading_paragraph(self):
        result = apply_equivalences(
            SAMPLE_RTF,
            [{
                "subject_code": "STRK128",
                "equivalent_code": "RTR20188",
                "equivalent_name": "LENGUA DE SEÑAS",
            }],
        )
        text = result.content.decode("latin-1")
        self.assertIn("EQUIVALENTE: RTR20188 LENGUA DE SE\\u209?AS", text)
        self.assertEqual(result.inserted_courses, ("STRK128",))

    def test_does_not_duplicate_existing_equivalence(self):
        first = apply_equivalences(
            SAMPLE_RTF,
            [{"subject_code": "STRK128", "equivalent_code": "RTR20188", "equivalent_name": "LENGUA DE SEÑAS"}],
        )
        second = apply_equivalences(
            first.content,
            [{"subject_code": "STRK128", "equivalent_code": "RTR20188", "equivalent_name": "LENGUA DE SEÑAS"}],
        )
        self.assertEqual(second.already_filled_courses, ("STRK128",))


if __name__ == "__main__":
    unittest.main()
