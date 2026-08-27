from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from core.pdf_extractor import PdfExtractionError, extract_equivalences
from core.rtf_editor import RtfEditError, apply_equivalences, course_exists_in_detail, is_rtf


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_BODY_BYTES = 50 * 1024 * 1024
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_RTF_BYTES = 25 * 1024 * 1024
SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_-]+")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("equivalencias")


class RequestError(ValueError):
    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


def _safe_output_name(filename: str) -> str:
    stem = Path(filename or "plan_estudios").stem
    stem = SAFE_STEM_RE.sub("_", stem).strip("_") or "plan_estudios"
    return f"{stem}_con_equivalencias.rtf"


class AppHandler(BaseHTTPRequestHandler):
    server_version = "EquivalenciasUDD/1.0"

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _send_file(self, path: Path) -> None:
        if not path.is_file() or path.parent != STATIC_DIR:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = path.read_bytes()
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _read_form(self) -> dict[str, tuple[str, bytes]]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise RequestError("Tamaño de solicitud inválido.") from exc
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            raise RequestError(
                "La carga supera el límite permitido de 50 MB.",
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise RequestError("La solicitud debe usar multipart/form-data.")

        body = self.rfile.read(content_length)
        message = BytesParser(policy=default).parsebytes(
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("ascii")
            + body
        )
        fields: dict[str, tuple[str, bytes]] = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            filename = part.get_filename() or ""
            fields[name] = (filename, part.get_payload(decode=True) or b"")
        return fields

    @staticmethod
    def _require_file(
        fields: dict[str, tuple[str, bytes]],
        name: str,
        extension: str,
        max_size: int,
    ) -> tuple[str, bytes]:
        filename, content = fields.get(name, ("", b""))
        if not filename or not content:
            raise RequestError(f"Falta el archivo {extension.upper()}.")
        if Path(filename).suffix.lower() != extension:
            raise RequestError(f"El archivo {filename} debe tener extensión {extension}.")
        if len(content) > max_size:
            raise RequestError(
                f"El archivo {filename} supera el límite de {max_size // (1024 * 1024)} MB.",
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        return filename, content

    def do_GET(self) -> None:  # noqa: N802 - API de BaseHTTPRequestHandler
        path = urlparse(self.path).path
        routes = {
            "/": "index.html",
            "/app.js": "app.js",
            "/styles.css": "styles.css",
        }
        filename = routes.get(path)
        if not filename:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._send_file(STATIC_DIR / filename)

    def do_POST(self) -> None:  # noqa: N802 - API de BaseHTTPRequestHandler
        try:
            path = urlparse(self.path).path
            if path == "/api/analyze":
                self._analyze()
            elif path == "/api/generate":
                self._generate()
            else:
                self._send_json({"error": "Ruta no encontrada."}, HTTPStatus.NOT_FOUND)
        except RequestError as exc:
            self._send_json({"error": str(exc)}, exc.status)
        except (PdfExtractionError, RtfEditError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)
        except Exception:
            LOGGER.exception("Error inesperado al procesar la solicitud")
            self._send_json(
                {"error": "No se pudo completar el proceso. Revise los archivos e inténtelo nuevamente."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _analyze(self) -> None:
        fields = self._read_form()
        _, pdf_content = self._require_file(fields, "pdf", ".pdf", MAX_PDF_BYTES)
        _, rtf_content = self._require_file(fields, "rtf", ".rtf", MAX_RTF_BYTES)
        if not pdf_content.startswith(b"%PDF"):
            raise RequestError("El archivo PDF no tiene una firma válida.")
        if not is_rtf(rtf_content):
            raise RequestError("El archivo Word no es un RTF válido.")

        result = extract_equivalences(pdf_content)
        items = []
        for equivalence in result.equivalences:
            item = equivalence.to_dict()
            item["found_in_rtf"] = course_exists_in_detail(
                rtf_content, equivalence.subject_code
            )
            items.append(item)

        self._send_json(
            {
                "equivalences": items,
                "subjects_read": result.subjects_read,
                "pages_read": result.pages_read,
                "warnings": result.warnings,
            }
        )

    def _generate(self) -> None:
        fields = self._read_form()
        rtf_filename, rtf_content = self._require_file(
            fields, "rtf", ".rtf", MAX_RTF_BYTES
        )
        _, equivalences_raw = fields.get("equivalences", ("", b""))
        if not equivalences_raw or len(equivalences_raw) > 250_000:
            raise RequestError("La lista de equivalencias está vacía o es demasiado grande.")
        try:
            equivalences = json.loads(equivalences_raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError("La lista de equivalencias no es válida.") from exc
        if not isinstance(equivalences, list) or not equivalences:
            raise RequestError("Seleccione al menos una equivalencia.")
        if len(equivalences) > 500:
            raise RequestError("La solicitud contiene demasiadas equivalencias.")

        result = apply_equivalences(rtf_content, equivalences)
        if not result.inserted_courses:
            if result.already_filled_courses:
                raise RequestError("Las asignaturas seleccionadas ya contienen equivalencias.")
            raise RequestError("Ninguna asignatura seleccionada se encontró en el RTF.")

        output_name = _safe_output_name(rtf_filename)
        metadata = json.dumps(
            {
                "inserted": result.inserted_courses,
                "missing": result.missing_courses,
                "already_filled": result.already_filled_courses,
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/rtf")
        self.send_header("Content-Disposition", f'attachment; filename="{output_name}"')
        self.send_header("Content-Length", str(len(result.content)))
        self.send_header("X-Equivalence-Result", metadata)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(result.content)


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    print(f"Aplicación disponible en http://{display_host}:{port}")
    print("Presione Ctrl+C para detenerla.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
