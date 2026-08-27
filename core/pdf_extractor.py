from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from typing import BinaryIO, Iterable

import pdfplumber


COURSE_CODE_RE = re.compile(r"^[A-ZÁÉÍÓÚÑ]{2,}[A-ZÁÉÍÓÚÑ0-9-]*\d+[A-Z0-9-]*$")
ATTEMPT_RE = re.compile(
    r"^\s*(?P<attempt>\d+)\s+(?P<period>\d{4}/\d+)\s+"
    r"(?P<grade>\d+(?:[.,]\d+)?)\s+(?P<status>[A-Z])(?:\s|$)",
    re.IGNORECASE,
)

# Algunos PDF institucionales no incluyen un mapa Unicode completo. pdfplumber
# conserva el carácter desconocido como �. Este vocabulario repara las palabras
# académicas más frecuentes; los casos restantes quedan visibles y editables.
MOJIBAKE_WORDS = {
    "ALL�": "ALLÁ",
    "CL�NICA": "CLÍNICA",
    "CL�NICO": "CLÍNICO",
    "CR�DITOS": "CRÉDITOS",
    "DIAGN�STICO": "DIAGNÓSTICO",
    "ENSE�ANZA": "ENSEÑANZA",
    "ESPA�OL": "ESPAÑOL",
    "�TICA": "ÉTICA",
    "EVALUACI�N": "EVALUACIÓN",
    "EXPRESI�N": "EXPRESIÓN",
    "INGL�S": "INGLÉS",
    "INCLUSI�N": "INCLUSIÓN",
    "INVESTIGACI�N": "INVESTIGACIÓN",
    "M�S": "MÁS",
    "NEUROL�GICAS": "NEUROLÓGICAS",
    "ORGANIZACI�N": "ORGANIZACIÓN",
    "PR�CTICA": "PRÁCTICA",
    "PREPR�CTICA": "PREPRÁCTICA",
    "PSICOLOG�A": "PSICOLOGÍA",
    "PSICOL�GICO": "PSICOLÓGICO",
    "P�BLICAS": "PÚBLICAS",
    "SE�AS": "SEÑAS",
    "T�CNICAS": "TÉCNICAS",
    "TEOR�AS": "TEORÍAS",
}

SHORT_WORDS = {
    "A",
    "AL",
    "DE",
    "DEL",
    "EL",
    "EN",
    "LA",
    "LAS",
    "LO",
    "LOS",
    "O",
    "QUE",
    "UN",
    "UNA",
    "Y",
}


@dataclass(frozen=True)
class Equivalence:
    subject_code: str
    subject_name: str
    equivalent_code: str
    equivalent_name: str
    period: str
    grade: str
    page: int
    has_unrecognized_characters: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExtractionResult:
    equivalences: tuple[Equivalence, ...]
    subjects_read: int
    pages_read: int
    warnings: tuple[str, ...]


class PdfExtractionError(ValueError):
    """El PDF no pudo interpretarse como una ficha curricular compatible."""


def _repair_text(value: str) -> str:
    value = " ".join(value.replace("\r", " ").split())
    for broken, repaired in MOJIBAKE_WORDS.items():
        value = value.replace(broken, repaired)
    return value


def _join_wrapped_lines(lines: Iterable[str]) -> str:
    result: list[str] = []
    for raw_line in lines:
        line = _repair_text(raw_line.strip())
        if not line:
            continue
        if result:
            previous_words = result[-1].split()
            current_words = line.split()
            if previous_words and current_words:
                previous = previous_words[-1]
                current = current_words[0]
                normalized_current = re.sub(r"[^A-ZÁÉÍÓÚÑ]", "", current.upper())
                if (
                    len(previous) >= 6
                    and 1 <= len(normalized_current) <= 3
                    and normalized_current not in SHORT_WORDS
                ):
                    previous_words[-1] = previous + current
                    result[-1] = " ".join(previous_words)
                    line = " ".join(current_words[1:])
                    if not line:
                        continue
        result.append(line)
    return " ".join(result)


def _normalize_subject_name(value: str) -> str:
    name = _join_wrapped_lines(value.splitlines())
    if "|" in name:
        name = name.split("|", 1)[1].strip()
    return name


def _parse_opportunity_cell(
    cell: str,
    *,
    subject_code: str,
    subject_name: str,
    page: int,
) -> Equivalence | None:
    lines = [line.strip() for line in cell.splitlines() if line.strip()]
    if len(lines) < 2:
        return None

    attempt = ATTEMPT_RE.match(lines[0])
    if not attempt or attempt.group("status").upper() != "A":
        return None

    remainder = lines[1:]
    first_parts = remainder[0].split(maxsplit=1)
    if not first_parts or not COURSE_CODE_RE.fullmatch(first_parts[0].upper()):
        return None

    equivalent_code = first_parts[0].upper()
    name_lines: list[str] = []
    if len(first_parts) == 2:
        name_lines.append(first_parts[1])
    name_lines.extend(remainder[1:])
    equivalent_name = _join_wrapped_lines(name_lines)
    if not equivalent_name:
        return None

    subject_name = _normalize_subject_name(subject_name)
    has_unknown = "�" in equivalent_name or "�" in subject_name
    return Equivalence(
        subject_code=subject_code.upper(),
        subject_name=subject_name,
        equivalent_code=equivalent_code,
        equivalent_name=equivalent_name,
        period=attempt.group("period"),
        grade=attempt.group("grade").replace(",", "."),
        page=page,
        has_unrecognized_characters=has_unknown,
    )


def _looks_like_curricular_table(table: list[list[str | None]]) -> bool:
    if not table:
        return False
    header = " ".join(str(value or "") for value in table[0]).upper()
    if "RAMO" in header and ("OPORT" in header or "CR�DS" in header or "CRÉDS" in header):
        return True
    valid_rows = 0
    for row in table[:8]:
        values = row or []
        candidates = [str(value or "").strip().upper() for value in values[:2]]
        if any(COURSE_CODE_RE.fullmatch(candidate) for candidate in candidates):
            valid_rows += 1
    return valid_rows >= 2


def _iter_subject_rows(table: list[list[str | None]]) -> Iterable[list[str | None]]:
    if not table:
        return
    start = 1 if "RAMO" in " ".join(str(v or "") for v in table[0]).upper() else 0
    for row in table[start:]:
        if not row:
            continue
        # En la primera página existe una columna "Origen" antes de "Ramo".
        if len(row) >= 9:
            candidate = str(row[1] or "").strip().upper()
            if COURSE_CODE_RE.fullmatch(candidate):
                yield row[1:]
                continue
        candidate = str(row[0] or "").strip().upper()
        if COURSE_CODE_RE.fullmatch(candidate):
            yield row


def extract_equivalences(source: bytes | BinaryIO) -> ExtractionResult:
    if isinstance(source, bytes):
        stream: BinaryIO = io.BytesIO(source)
    else:
        stream = source

    equivalences: list[Equivalence] = []
    subjects_read = 0
    warnings: list[str] = []

    try:
        with pdfplumber.open(stream) as document:
            pages_read = len(document.pages)
            for page_number, page in enumerate(document.pages, start=1):
                for table in page.extract_tables() or []:
                    if not _looks_like_curricular_table(table):
                        continue
                    for row in _iter_subject_rows(table):
                        if len(row) < 4:
                            continue
                        subject_code = str(row[0] or "").strip().upper()
                        subject_name = str(row[1] or "").strip()
                        subjects_read += 1
                        for cell in row[3:]:
                            if not cell:
                                continue
                            equivalence = _parse_opportunity_cell(
                                str(cell),
                                subject_code=subject_code,
                                subject_name=subject_name,
                                page=page_number,
                            )
                            if equivalence:
                                equivalences.append(equivalence)
    except Exception as exc:  # pdfplumber agrupa varias excepciones de PDF.
        raise PdfExtractionError("No se pudo leer la estructura del PDF.") from exc

    if not subjects_read:
        raise PdfExtractionError(
            "No se encontró una tabla curricular con códigos de asignatura."
        )

    if any(item.has_unrecognized_characters for item in equivalences):
        warnings.append(
            "Algunos acentos no pudieron recuperarse del PDF. Revise los nombres marcados antes de generar el Word."
        )

    # Evita duplicados idénticos cuando una tabla se repite por el encabezado de página.
    unique: dict[tuple[str, str, str], Equivalence] = {}
    for item in equivalences:
        unique[(item.subject_code, item.equivalent_code, item.period)] = item

    return ExtractionResult(
        equivalences=tuple(unique.values()),
        subjects_read=subjects_read,
        pages_read=pages_read,
        warnings=tuple(warnings),
    )
