"""HTTP + storage smoke test, exclusively for the disposable local Docker stack."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from http.cookiejar import CookieJar

from PIL import Image
from sqlalchemy.engine import make_url

from app.core.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("write", "verify"))
    parser.add_argument("--base-url", default="http://frontend:8080")
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--require-html-pdf", action="store_true")
    args = parser.parse_args()
    if os.getenv("CTRX_SMOKE_ALLOW_WRITE") != "1":
        raise RuntimeError("Set CTRX_SMOKE_ALLOW_WRITE=1 only for a disposable local database.")
    if make_url(settings.DATABASE_URL).host not in {"db", "localhost", "127.0.0.1"}:
        raise RuntimeError("Refusing smoke-test writes to an external database.")
    if urlparse(args.base_url).hostname not in {"frontend", "localhost", "127.0.0.1"}:
        raise RuntimeError("Refusing smoke-test writes to an external API.")
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def call(path, method="GET", data=None, token=None, expected=200, raw=False):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if data is not None and not isinstance(data, bytes):
            data = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        request = Request(args.base_url.rstrip("/") + path, data=data, method=method, headers=headers)
        try:
            response = opener.open(request, timeout=30)
        except HTTPError as exc:
            response = exc
        content = response.read()
        assert response.code == expected, (path, response.code, content[:200])
        return content if raw else json.loads(content)

    if not args.api_only:
        html = call("/", raw=True).decode()
        assert '<div id="root">' in html
        scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
        assert scripts
        for path in scripts:
            assert len(call(path, raw=True)) > 100
        assert call("/workspace/test-deep-link", raw=True).decode() == html
        call("/assets/not-a-real-file.js", expected=404, raw=True)
        call("/api/not-a-real-route", expected=404)
    assert call("/health")["db"] == 1
    call("/api/public/statistics")
    call("/api/auth/me", expected=401)
    manifest = Path(settings.STORAGE_DIR) / "docker-smoke.json"
    if args.action == "write":
        email = f"docker-smoke-{secrets.token_hex(6)}@example.test"
        password = secrets.token_urlsafe(24)
        call("/api/auth/register", "POST", {"email": email, "password": password,
             "full_name": "Docker Smoke Tenant", "role": "tenant"}, expected=201)
    else:
        saved = json.loads(manifest.read_text())
        email, password = saved["email"], saved["password"]
    token = call("/api/auth/login", "POST", {"email": email, "password": password})["access_token"]
    assert call("/api/auth/me", token=token)["email"] == email
    assert call("/api/auth/refresh", "POST")["access_token"]
    call("/api/rent/tenancies", token=token, expected=403)
    if args.action == "write":
        output = io.BytesIO()
        Image.new("RGB", (64, 64), "teal").save(output, format="PNG")
        assert call("/api/profile/photo", "PUT", output.getvalue(), token)["photo_url"].startswith("data:image/jpeg")
        from app.certificates.renderer import _asset_bytes, _generate_qr, _html_engine, render
        from app.certificates.storage import store_pdf

        for name in ("Insignia/shapla.png", "Insignia/mapsignia.png", "Logo/logo_ctrx.png"):
            assert _asset_bytes(name)
        if args.require_html_pdf:
            engine = _html_engine()
            assert engine is not None, "Native WeasyPrint renderer is unavailable"
            assert engine(string="<p>Docker PDF readiness</p>").write_pdf().startswith(b"%PDF-")
        pdf = render({"full_name": "Docker Smoke Tenant", "ric_number": "000000000001",
                      "status": "active"}, _generate_qr("docker-smoke-test"))
        assert pdf.startswith(b"%PDF-") and len(pdf) > 1000
        key = store_pdf(pdf, prefix="docker-smoke")
        manifest.write_text(json.dumps({"email": email, "password": password,
            "key": key, "sha256": hashlib.sha256(pdf).hexdigest()}))
        print("Frontend, proxy, DB, auth/refresh, role routing, image storage and PDF checks passed.")
    else:
        assert call("/api/profile", token=token)["photo_url"].startswith("data:image/jpeg")
        pdf = (Path(settings.STORAGE_DIR) / saved["key"]).read_bytes()
        assert hashlib.sha256(pdf).hexdigest() == saved["sha256"]
        print("Account, uploaded image and generated PDF survived container recreation.")


if __name__ == "__main__":
    main()
