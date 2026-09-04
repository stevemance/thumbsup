#!/usr/bin/env python3
"""Download vendor datasheets listed in hardware/datasheets.json into a gitignored dir.

HTML is a failure for required entries (LCSC "pdf" URLs often 302 to a login page).
Optional entries may be stored as .html.
"""

from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "hardware" / "datasheets.json"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def dest_dir(manifest: dict) -> Path:
    return ROOT / manifest["output_dir"]


def looks_like_pdf(data: bytes, content_type: str) -> bool:
    if data.startswith(b"%PDF"):
        return True
    return "pdf" in content_type.lower() and not data.lstrip()[:1] == b"<"


def looks_like_html(data: bytes, content_type: str) -> bool:
    if "html" in content_type.lower():
        return True
    head = data.lstrip()[:64].lower()
    return head.startswith(b"<!doctype") or head.startswith(b"<html")


def fetch(url: str, timeout: int = 60) -> tuple[bytes, str, str]:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.9",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        data = resp.read()
        content_type = resp.headers.get("Content-Type", "")
        final_url = resp.geturl()
    return data, content_type, final_url


def save(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def download_one(entry: dict, out: Path) -> tuple[str, str]:
    ident = entry["id"]
    optional = bool(entry.get("optional"))
    errors: list[str] = []
    for url in entry["urls"]:
        try:
            data, content_type, final_url = fetch(url)
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, ValueError) as exc:
            errors.append(f"{url}: {exc}")
            continue
        if looks_like_pdf(data, content_type):
            path = out / f"{ident}.pdf"
            save(path, data)
            return "ok", f"{path.relative_to(ROOT)} ({len(data)} bytes from {final_url})"
        if looks_like_html(data, content_type):
            if optional:
                path = out / f"{ident}.html"
                save(path, data)
                return "ok-html", f"{path.relative_to(ROOT)} (HTML from {final_url})"
            errors.append(f"{url}: HTML not PDF ({len(data)} bytes, {final_url})")
            continue
        errors.append(f"{url}: unexpected type {content_type!r} ({len(data)} bytes)")
    if optional:
        return "skip", "; ".join(errors)
    return "fail", "; ".join(errors)


def main() -> int:
    manifest = load_manifest()
    out = dest_dir(manifest)
    out.mkdir(parents=True, exist_ok=True)
    (out / "README").write_text(
        "Vendor PDFs downloaded by hardware/tools/download_datasheets.py. Gitignored.\n"
    )
    print(f"Manifest: {MANIFEST.relative_to(ROOT)}")
    print(f"Output:   {out.relative_to(ROOT)}")
    rc = 0
    for entry in manifest["datasheets"]:
        status, detail = download_one(entry, out)
        mark = {"ok": "OK ", "ok-html": "HTML", "skip": "OPT", "fail": "FAIL"}[status]
        print(f"[{mark}] {entry['id']:24} {detail}")
        if status == "fail":
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
