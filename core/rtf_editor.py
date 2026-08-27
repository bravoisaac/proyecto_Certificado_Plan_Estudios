from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping


COURSE_CODE_RE = re.compile(r"^[A-Z0-9-]{3,20}$")


@dataclass(frozen=True)
class RtfEditResult:
    content: bytes
    inserted_courses: tuple[str, ...]
    missing_courses: tuple[str, ...]
    already_filled_courses: tuple[str, ...]


class RtfEditError(ValueError):
    """El archivo RTF no tiene una estructura compatible o está dañado."""


def is_rtf(content: bytes) -> bool:
    return content.lstrip().startswith(b"{\\rtf")


def _rtf_escape(value: str) -> str:
    output: list[str] = []
    for character in value:
        if character in "{}\\":
            output.append("\\" + character)
        elif character == "\n":
            output.append("\\line ")
        elif 32 <= ord(character) <= 126:
            output.append(character)
        else:
            codepoint = ord(character)
            if codepoint > 32767:
                codepoint -= 65536
            output.append(f"\\u{codepoint}?")
    return "".join(output)


def _find_detail_anchor(rtf: str, course_code: str) -> tuple[int, int] | None:
    token = re.compile(rf"(?<![A-Z0-9]){re.escape(course_code)}(?![A-Z0-9])")
    for match in token.finditer(rtf):
        paragraph_start = rtf.rfind("\\pard", max(0, match.start() - 1800), match.start())
        if paragraph_start < 0:
            continue
        controls = rtf[paragraph_start:match.start()]
        if "\\posx732" in controls and "\\absh-192" in controls:
            return paragraph_start, match.start()
    return None


def course_exists_in_detail(rtf_content: bytes, course_code: str) -> bool:
    if not is_rtf(rtf_content):
        return False
    text = rtf_content.decode("latin-1")
    return _find_detail_anchor(text, course_code.upper()) is not None


def _insert_course_equivalences(
    rtf: str,
    course_code: str,
    values: list[tuple[str, str]],
) -> tuple[str, str]:
    anchor = _find_detail_anchor(rtf, course_code)
    if not anchor:
        return rtf, "missing"

    code_paragraph_start, _ = anchor
    heading_start = rtf.rfind("\\pard", max(0, code_paragraph_start - 5000), code_paragraph_start)
    if heading_start < 0:
        return rtf, "missing"

    heading_controls = rtf[heading_start:code_paragraph_start]
    if "\\posx1587" not in heading_controls:
        return rtf, "missing"

    if "EQUIVALENTE:" in heading_controls.upper():
        return rtf, "already_filled"

    heading_paragraph_end = rtf.find("\\par }", heading_start, code_paragraph_start)
    if heading_paragraph_end < 0:
        return rtf, "missing"

    lines = []
    for equivalent_code, equivalent_name in values:
        label = f"EQUIVALENTE: {equivalent_code} {equivalent_name}".strip()
        lines.append(_rtf_escape(label))
    font_match = re.search(r"\\af(?P<font>\d+)", heading_controls)
    font_id = font_match.group("font") if font_match else "0"
    injected = (
        "{\\rtlch\\fcs1 \\ab\\af"
        + font_id
        + " \\ltrch\\fcs0 \\b\\fs14\\cf1 "
        + "\\hich\\af"
        + font_id
        + "\\dbch\\af31505\\loch\\f"
        + font_id
        + " "
        + "\\line ".join(lines)
        + "\\par }"
    )
    insertion_point = heading_paragraph_end + len("\\par }")
    updated = rtf[:insertion_point] + injected + rtf[insertion_point:]
    return updated, "inserted"


def apply_equivalences(
    rtf_content: bytes,
    equivalences: Iterable[Mapping[str, str]],
) -> RtfEditResult:
    if not is_rtf(rtf_content):
        raise RtfEditError("El archivo Word debe estar en formato RTF válido.")

    grouped: dict[str, list[tuple[str, str]]] = {}
    for item in equivalences:
        subject_code = str(item.get("subject_code", "")).strip().upper()
        equivalent_code = str(item.get("equivalent_code", "")).strip().upper()
        equivalent_name = " ".join(str(item.get("equivalent_name", "")).split())
        if not COURSE_CODE_RE.fullmatch(subject_code):
            raise RtfEditError(f"Código de asignatura inválido: {subject_code or '(vacío)'}")
        if not COURSE_CODE_RE.fullmatch(equivalent_code):
            raise RtfEditError(f"Código equivalente inválido: {equivalent_code or '(vacío)'}")
        if not equivalent_name or len(equivalent_name) > 300:
            raise RtfEditError("El nombre equivalente debe tener entre 1 y 300 caracteres.")
        grouped.setdefault(subject_code, []).append((equivalent_code, equivalent_name))

    rtf = rtf_content.decode("latin-1")
    inserted: list[str] = []
    missing: list[str] = []
    already_filled: list[str] = []

    for course_code, values in grouped.items():
        rtf, status = _insert_course_equivalences(rtf, course_code, values)
        if status == "inserted":
            inserted.append(course_code)
        elif status == "already_filled":
            already_filled.append(course_code)
        else:
            missing.append(course_code)

    return RtfEditResult(
        content=rtf.encode("latin-1"),
        inserted_courses=tuple(inserted),
        missing_courses=tuple(missing),
        already_filled_courses=tuple(already_filled),
    )
