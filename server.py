#!/usr/bin/env python3
"""초파리 뇌–몸 질병 시뮬레이션 화면을 로컬에서 띄운다."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sim.model import DISEASES, dose_response, live_reset, live_tick, meta, warmup

WEB = ROOT / "web"
DATA = ROOT / "data"
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/vendor/three.module.js": ("vendor/three.module.js", "text/javascript; charset=utf-8"),
}
FILES = {
    "/flywire_points.bin": (DATA / "flywire_points.bin", "application/octet-stream"),
    "/flywire_brain.json": (DATA / "flywire_brain.json", "application/json; charset=utf-8"),
}
LIVE_LOCK = threading.Lock()
CSV_COLUMNS = [
    "severity",
    "disease_score",
    "grade",
    "locomotion",
    "climbing",
    "dopamine",
    "synapses",
    "change_label",
    "change_value",
]


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: object, code: int = 200) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/meta":
            self._json(meta())
            return
        if parsed.path in {"/api/dose", "/api/dose.csv"}:
            disease = parse_qs(parsed.query).get("disease", ["parkinson"])[0]
            if disease not in DISEASES:
                self._json({"error": "알 수 없는 질병입니다."}, 400)
                return
            if parsed.path.endswith(".csv"):
                lines = [",".join(CSV_COLUMNS)]
                for row in dose_response(disease):
                    lines.append(",".join(str(row.get(column, "")) for column in CSV_COLUMNS))
                body = ("\n".join(lines) + "\n").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="{disease}.csv"')
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._json({"disease": disease, "points": dose_response(disease)})
            return
        extra = FILES.get(parsed.path)
        if extra is not None:
            path, content_type = extra
            self._send(200, path.read_bytes(), content_type)
            return
        item = STATIC.get(parsed.path)
        if item is None:
            self._json({"error": "없는 주소입니다."}, 404)
            return
        name, content_type = item
        self._send(200, (WEB / name).read_bytes(), content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/api/live", "/api/reset"}:
            self._json({"error": "없는 주소입니다."}, 404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 20_000:
            self._json({"error": "요청이 너무 큽니다."}, 413)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}") if length else {}
            disease = str(payload.get("disease", "parkinson"))
            severity = float(payload.get("severity", 0))
            seconds = float(payload.get("seconds", 0.1))
        except (TypeError, json.JSONDecodeError, ValueError):
            self._json({"error": "요청 형식이 맞지 않습니다."}, 400)
            return
        if disease not in DISEASES:
            self._json({"error": "알 수 없는 질병입니다."}, 400)
            return
        with LIVE_LOCK:
            if path == "/api/reset":
                payload = live_reset(disease, severity)
            else:
                payload = live_tick(disease, severity, seconds)
        self._json(payload)


def main() -> None:
    if "--check" in sys.argv:
        from sim.model import run_checks

        run_checks()
        return
    port = 8765
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    print("건강한 파리의 기준을 준비합니다...")
    warmup()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"시뮬레이션 화면: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
