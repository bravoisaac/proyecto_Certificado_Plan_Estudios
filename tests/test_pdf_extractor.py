import unittest

from core.pdf_extractor import _join_wrapped_lines, _parse_opportunity_cell


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


if __name__ == "__main__":
    unittest.main()

