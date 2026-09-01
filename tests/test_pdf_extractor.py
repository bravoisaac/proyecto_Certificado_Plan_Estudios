import unittest

from core.pdf_extractor import (
    Equivalence,
    _include_all_subjects,
    _join_wrapped_lines,
    _parse_opportunity_cell,
)


class PdfExtractorTests(unittest.TestCase):
    def test_extracts_only_equivalent_after_approved_attempt(self):
        item = _parse_opportunity_cell(
            "1 2020/2 6.4 A\nRTR20188\nLENGUA DE\nSE�AS",
            subject_code="STRK128",
            subject_name="2-B-G-E-T | ELECTIVO TRACK 1",
            page=1,
        )
        self.assertIsNotNone(item)
        self.assertEqual(item.equivalent_code, "RTR20188")
        self.assertEqual(item.equivalent_name, "LENGUA DE SEÑAS")
        self.assertEqual(item.subject_name, "ELECTIVO TRACK 1")

    def test_ignores_failed_attempt(self):
        item = _parse_opportunity_cell(
            "1 2022/1 1.0 R\nHTR20182\nEXPRESI�N TEATRAL",
            subject_code="STRK319",
            subject_name="ELECTIVO TRACK 4",
            page=2,
        )
        self.assertIsNone(item)

    def test_repairs_words_split_by_narrow_pdf_column(self):
        value = _join_wrapped_lines(["NEURODIVERSIDA", "D: EXPERIENCIAS", "INTERDISCIPLINAR", "IAS EN CONTEXTO"])
        self.assertEqual(value, "NEURODIVERSIDAD: EXPERIENCIAS INTERDISCIPLINARIAS EN CONTEXTO")

    def test_includes_subjects_without_approved_equivalence(self):
        approved = Equivalence(
            subject_code="NUC114",
            subject_name="BASES QUÍMICAS",
            equivalent_code="PCSAL124",
            equivalent_name="BASES QUÍMICAS",
            period="2020/2",
            grade="6.4",
            page=1,
        )
        result = _include_all_subjects(
            {
                "NUC114": ("BASES QUÍMICAS", 1),
                "NUC117": ("BASES BIOLÓGICAS", 1),
            },
            [approved],
        )

        self.assertEqual([item.subject_code for item in result], ["NUC114", "NUC117"])
        self.assertTrue(result[0].has_equivalence)
        self.assertFalse(result[1].has_equivalence)
        self.assertEqual(result[1].equivalent_code, "")
        self.assertEqual(result[1].equivalent_name, "")


if __name__ == "__main__":
    unittest.main()
