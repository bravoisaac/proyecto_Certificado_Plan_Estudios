from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Mapping


COURSE_CODE_RE = re.compile(r"^[A-Z0-9-]{3,20}$")
NAME_STOP_WORDS = {"DE", "DEL", "EL", "EN", "LA", "LAS", "LOS", "Y"}


@dataclass(frozen=True)
class RtfEditResult:
    content: bytes
    inserted_courses: tuple[str, ...]
    appended_courses: tuple[str, ...]
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


def _rtf_visible_text(value: str) -> str:
    # Los saltos físicos del archivo RTF no representan espacios visibles.
    value = value.replace("\r", "").replace("\n", "")
    value = re.sub(
        r"\\u(-?\d+)\??",
        lambda match: chr(int(match.group(1)) % 65536),
        value,
    )
    value = re.sub(
        r"\\'([0-9A-Fa-f]{2})",
        lambda match: bytes([int(match.group(1), 16)]).decode("cp1252"),
        value,
    )
    value = value.replace(r"\~", " ").replace(r"\_", "-")
    value = re.sub(r"\\[A-Za-z]+-?\d* ?", "", value)
    value = value.replace(r"\{", "{").replace(r"\}", "}").replace(r"\\", "\\")
    value = re.sub(r"[{}]", "", value)
    return " ".join(value.split())


def _name_tokens(value: str) -> tuple[str, ...]:
    value = value.replace("�", "")
    value = "".join(
        character
        for character in unicodedata.normalize("NFKD", value.upper())
        if not unicodedata.combining(character)
    )
    return tuple(
        token
        for token in re.findall(r"[A-Z0-9]+", value)
        if token not in NAME_STOP_WORDS
    )


def _name_match_score(source_name: str, target_name: str) -> float | None:
    source_tokens = _name_tokens(source_name)
    target_tokens = _name_tokens(target_name)
    if not source_tokens or not target_tokens:
        return None
    if source_tokens == target_tokens:
        return 1.0

    shorter, longer = (
        (source_tokens, target_tokens)
        if len(source_tokens) <= len(target_tokens)
        else (target_tokens, source_tokens)
    )
    if len(shorter) == 1 and len(shorter[0]) < 6:
        return None

    unused = set(range(len(longer)))
    similarities: list[float] = []
    for token in shorter:
        candidates = [
            (SequenceMatcher(None, token, longer[index]).ratio(), index)
            for index in unused
        ]
        if not candidates:
            return None
        similarity, index = max(candidates)
        minimum = 1.0 if len(token) <= 3 else 0.82
        if similarity < minimum:
            return None
        similarities.append(similarity)
        unused.remove(index)

    score = sum(similarities) / len(similarities)
    score -= 0.03 * (len(longer) - len(shorter))
    return score if score >= 0.84 else None


def _control_number(fragment: str, name: str) -> int | None:
    match = re.search(rf"\\{name}(-?\d+)", fragment)
    return int(match.group(1)) if match else None


def _has_detail_card_geometry(code_controls: str, heading_controls: str) -> bool:
    code_x = _control_number(code_controls, "posx")
    code_y = _control_number(code_controls, "posy")
    code_width = _control_number(code_controls, "absw")
    heading_x = _control_number(heading_controls, "posx")
    heading_y = _control_number(heading_controls, "posy")
    heading_width = _control_number(heading_controls, "absw")
    return (
        None not in (code_x, code_y, code_width, heading_x, heading_y, heading_width)
        and code_y == heading_y
        and code_x < heading_x
        and code_width < heading_width
    )


def _find_detail_anchor_by_name(rtf: str, subject_name: str) -> tuple[int, int] | None:
    candidates: list[tuple[float, tuple[int, int]]] = []
    paragraph_starts = [match.start() for match in re.finditer(r"\\pard\b", rtf)]
    for index, paragraph_start in enumerate(paragraph_starts):
        paragraph_end = (
            paragraph_starts[index + 1]
            if index + 1 < len(paragraph_starts)
            else len(rtf)
        )
        code_controls = rtf[paragraph_start:paragraph_end]
        target_code = _rtf_visible_text(code_controls)
        if (
            not COURSE_CODE_RE.fullmatch(target_code)
            or not re.search(r"[A-Z]", target_code)
            or not re.search(r"\d", target_code)
        ):
            continue

        heading_start = rtf.rfind(
            "\\pard", max(0, paragraph_start - 5000), paragraph_start
        )
        if heading_start < 0:
            continue
        heading_controls = rtf[heading_start:paragraph_start]
        if not _has_detail_card_geometry(code_controls, heading_controls):
            continue

        score = _name_match_score(subject_name, _rtf_visible_text(heading_controls))
        if score is not None:
            candidates.append((score, (paragraph_start, paragraph_start)))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.08:
        return None
    return candidates[0][1]


def _find_detail_anchor(rtf: str, course_code: str) -> tuple[int, int] | None:
    token = re.compile(rf"(?<![A-Z0-9]){re.escape(course_code)}(?![A-Z0-9])")
    compatible_anchor: tuple[int, int] | None = None
    for match in token.finditer(rtf):
        paragraph_start = rtf.rfind("\\pard", max(0, match.start() - 1800), match.start())
        if paragraph_start < 0:
            continue
        controls = rtf[paragraph_start:match.start()]
        if "\\posx732" in controls and "\\absh-192" in controls:
            return paragraph_start, match.start()

        paragraph_end = rtf.find("\\par }", match.end(), match.end() + 1800)
        heading_start = rtf.rfind(
            "\\pard", max(0, paragraph_start - 5000), paragraph_start
        )
        if paragraph_end < 0 or heading_start < 0:
            continue
        heading_end = rtf.find("\\par }", heading_start, paragraph_start)
        heading_controls = rtf[heading_start:paragraph_start]
        if (
            heading_end >= 0
            and re.search(r"\\posx-?\d+", controls)
            and re.search(r"\\absh-?\d+", controls)
            and re.search(r"\\posx-?\d+", heading_controls)
            and re.search(r"\\absh-?\d+", heading_controls)
        ):
            compatible_anchor = (paragraph_start, match.start())
    return compatible_anchor


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
    if not re.search(r"\\posx-?\d+", heading_controls):
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


def _append_unmatched_equivalences(
    rtf: str,
    courses: Iterable[tuple[str, str, list[tuple[str, str]]]],
) -> tuple[str, list[str], list[str]]:
    document_end = rtf.rfind("}")
    if document_end < 0:
        raise RtfEditError("El archivo RTF no tiene un cierre válido.")

    blocks: list[str] = []
    appended: list[str] = []
    already_filled: list[str] = []
    upper_rtf = rtf.upper()
    for subject_code, subject_name, values in courses:
        marker = f"ASIGNATURA SIN FICHA: {subject_code}"
        if marker in upper_rtf:
            already_filled.append(subject_code)
            continue
        lines = [
            _rtf_escape(f"EQUIVALENTE: {code} {name}".strip())
            for code, name in values
        ]
        heading = f"ASIGNATURA SIN FICHA: {subject_code} {subject_name}".strip()
        blocks.append(
            "{\\pard\\plain\\sa120\\fs18\\b "
            + _rtf_escape(heading)
            + "\\b0\\line "
            + "\\line ".join(lines)
            + "\\par}\n"
        )
        appended.append(subject_code)

    if not blocks:
        return rtf, appended, already_filled
    title = ""
    if "EQUIVALENCIAS SIN FICHA EDITABLE" not in upper_rtf:
        title = (
            "\n\\page\n{\\pard\\plain\\sa240\\b\\fs20 "
            "EQUIVALENCIAS SIN FICHA EDITABLE\\par}\n"
        )
    updated = rtf[:document_end] + title + "".join(blocks) + rtf[document_end:]
    return updated, appended, already_filled


def apply_equivalences(
    rtf_content: bytes,
    equivalences: Iterable[Mapping[str, str]],
) -> RtfEditResult:
    if not is_rtf(rtf_content):
        raise RtfEditError("El archivo Word debe estar en formato RTF válido.")

    grouped: dict[str, list[tuple[str, str]]] = {}
    subject_names: dict[str, str] = {}
    for item in equivalences:
        subject_code = str(item.get("subject_code", "")).strip().upper()
        subject_name = " ".join(str(item.get("subject_name", "")).split())
        equivalent_code = str(item.get("equivalent_code", "")).strip().upper()
        equivalent_name = " ".join(str(item.get("equivalent_name", "")).split())
        if not COURSE_CODE_RE.fullmatch(subject_code):
            raise RtfEditError(f"Código de asignatura inválido: {subject_code or '(vacío)'}")
        if not COURSE_CODE_RE.fullmatch(equivalent_code):
            raise RtfEditError(f"Código equivalente inválido: {equivalent_code or '(vacío)'}")
        if not equivalent_name or len(equivalent_name) > 300:
            raise RtfEditError("El nombre equivalente debe tener entre 1 y 300 caracteres.")
        grouped.setdefault(subject_code, []).append((equivalent_code, equivalent_name))
        subject_names.setdefault(subject_code, subject_name)

    rtf = rtf_content.decode("latin-1")
    inserted: list[str] = []
    appended: list[str] = []
    missing: list[str] = []
    already_filled: list[str] = []
    unmatched: list[tuple[str, str, list[tuple[str, str]]]] = []

    for course_code, values in grouped.items():
        rtf, status = _insert_course_equivalences(rtf, course_code, values)
        if status == "inserted":
            inserted.append(course_code)
        elif status == "already_filled":
            already_filled.append(course_code)
        else:
            unmatched.append((course_code, subject_names[course_code], values))

    if unmatched:
        try:
            rtf, appended, fallback_already_filled = _append_unmatched_equivalences(
                rtf, unmatched
            )
            already_filled.extend(fallback_already_filled)
        except RtfEditError:
            missing.extend(course_code for course_code, _, _ in unmatched)

    return RtfEditResult(
        content=rtf.encode("latin-1"),
        inserted_courses=tuple(inserted),
        appended_courses=tuple(appended),
        missing_courses=tuple(missing),
        already_filled_courses=tuple(already_filled),
    )
