import unittest

from core.rtf_editor import apply_equivalences, course_exists_in_detail


SAMPLE_RTF = rb"""{\rtf1\ansi
\pard \posx1587\posy4222\absh-482\absw6085 {\b ELECTIVO TRACK 1
\par }{\b
\par }\pard \posx732\posy4222\absh-192\absw825 {\b STRK128
\par }\pard \posx60 OTRO CONTENIDO\par
}"""

ALTERNATE_CARD_RTF = rb"""{\rtf1\ansi
\pard \posx1700\posy2100\absh-520\absw5900 {\b BASES QUIMICAS
\par }{\b
\par }\pard \posx850\posy2100\absh-210\absw900 {\b NUC114
\par }\pard \posx60 OTRO CONTENIDO\par
}"""

MISMATCHED_CODE_CARD_RTF = rb"""{\rtf1\ansi
\pard \posx1700\posy2100\absh-520\absw5900 {\b BASES QU\'cdMICAS DE LA VIDA
\par }{\b
\par }\pard \posx850\posy2100\absh-210\absw900 {\b KIC124
\par }\pard \posx60 OTRO CONTENIDO\par
}"""

RTF_WITHOUT_EDITABLE_CARD = rb"""{\rtf1\ansi
\pard PLAN DE ESTUDIOS\par
}"""

ENGLISH_LEVEL_2_RTF = rb"""{\rtf1\ansi
\pard \posx1587\posy9758\absh-482\absw6085 {\b INGL\'c9S NIVEL 2
\par }{\b
\par }\pard \posx732\posy9758\absh-192\absw825 {\b INGL2
\par }\pard \posx60 OTRO CONTENIDO\par
}"""


class RtfEditorTests(unittest.TestCase):
    def test_finds_only_detail_course_anchor(self):
        self.assertTrue(course_exists_in_detail(SAMPLE_RTF, "STRK128"))
        self.assertFalse(course_exists_in_detail(SAMPLE_RTF, "STT123"))

    def test_finds_compatible_card_with_different_geometry(self):
        self.assertTrue(course_exists_in_detail(ALTERNATE_CARD_RTF, "NUC114"))

    def test_finds_card_by_subject_name_when_code_changed(self):
        self.assertTrue(
            course_exists_in_detail(
                MISMATCHED_CODE_CARD_RTF,
                "NUC114",
                "BASES QU�MICAS",
            )
        )

    def test_inserts_by_subject_name_when_code_changed(self):
        result = apply_equivalences(
            MISMATCHED_CODE_CARD_RTF,
            [{
                "subject_code": "NUC114",
                "subject_name": "BASES QU�MICAS",
                "equivalent_code": "PCSAL124",
                "equivalent_name": "BASES QUÍMICAS",
            }],
        )
        text = result.content.decode("latin-1")
        self.assertIn("EQUIVALENTE: PCSAL124 BASES QU\\u205?MICAS", text)
        self.assertEqual(result.inserted_courses, ("NUC114",))
        self.assertEqual(result.appended_courses, ())

    def test_inserts_into_compatible_card_with_different_geometry(self):
        result = apply_equivalences(
            ALTERNATE_CARD_RTF,
            [{
                "subject_code": "NUC114",
                "equivalent_code": "PCSAL124",
                "equivalent_name": "BASES QUIMICAS",
            }],
        )
        text = result.content.decode("latin-1")
        self.assertIn("EQUIVALENTE: PCSAL124 BASES QUIMICAS", text)
        self.assertEqual(result.inserted_courses, ("NUC114",))

    def test_appends_equivalence_when_subject_has_no_editable_card(self):
        result = apply_equivalences(
            RTF_WITHOUT_EDITABLE_CARD,
            [{
                "subject_code": "NUC114",
                "subject_name": "BASES QUÍMICAS",
                "equivalent_code": "PCSAL124",
                "equivalent_name": "BASES QUÍMICAS",
            }],
        )
        text = result.content.decode("latin-1")
        self.assertIn("\\page", text)
        self.assertIn("EQUIVALENCIAS SIN FICHA EDITABLE", text)
        self.assertIn("ASIGNATURA SIN FICHA: NUC114 BASES QU\\u205?MICAS", text)
        self.assertIn("EQUIVALENTE: PCSAL124 BASES QU\\u205?MICAS", text)
        self.assertEqual(result.appended_courses, ("NUC114",))
        self.assertEqual(result.missing_courses, ())

    def test_does_not_duplicate_appended_equivalence(self):
        item = {
            "subject_code": "NUC114",
            "subject_name": "BASES QUÍMICAS",
            "equivalent_code": "PCSAL124",
            "equivalent_name": "BASES QUÍMICAS",
        }
        first = apply_equivalences(RTF_WITHOUT_EDITABLE_CARD, [item])
        second = apply_equivalences(first.content, [item])
        self.assertEqual(second.appended_courses, ())
        self.assertEqual(second.already_filled_courses, ("NUC114",))

    def test_appends_every_selected_equivalence(self):
        items = [
            {
                "subject_code": f"NUC{number}",
                "subject_name": f"ASIGNATURA {number}",
                "equivalent_code": f"PCSAL{number}",
                "equivalent_name": f"EQUIVALENTE {number}",
            }
            for number in range(101, 114)
        ]
        result = apply_equivalences(RTF_WITHOUT_EDITABLE_CARD, items)
        text = result.content.decode("latin-1")

        self.assertEqual(len(result.appended_courses), 13)
        for item in items:
            self.assertIn(
                f"EQUIVALENTE: {item['equivalent_code']} {item['equivalent_name']}",
                text,
            )

    def test_inserts_english_level_2_equivalence(self):
        result = apply_equivalences(
            ENGLISH_LEVEL_2_RTF,
            [{
                "subject_code": "INGL2",
                "subject_name": "INGLÉS NIVEL 2",
                "equivalent_code": "ING112",
                "equivalent_name": "INGLÉS 2",
            }],
        )
        text = result.content.decode("latin-1")
        self.assertIn("EQUIVALENTE: ING112 INGL\\u201?S 2", text)
        self.assertEqual(result.inserted_courses, ("INGL2",))

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
