"""HTTP reachability checks for PDFs/videos, plus extraction of the hyperlinks
embedded inside a PDF (the app makes these tappable via pdfrx page.loadLinks)."""
from __future__ import annotations

import io
from dataclasses import dataclass

import requests
from pypdf import PdfReader

_UA = {"User-Agent": "eg-qa-linkcheck/1.0"}


@dataclass
class UrlResult:
    url: str
    ok: bool
    status: int
    content_type: str
    note: str = ""


def check_url(url: str, kind: str = "any", timeout: int = 30) -> UrlResult:
    """Reachability check. Videos/large files use a ranged GET (first 2 bytes)
    so we never download whole media; PDFs are HEAD-checked here (full download
    happens separately when we extract in-PDF links)."""
    if not url:
        return UrlResult(url, False, 0, "", "empty url")
    try:
        if kind == "video":
            r = requests.get(
                url, headers={**_UA, "Range": "bytes=0-1"}, stream=True, timeout=timeout
            )
            ok = r.status_code in (200, 206)
            ct = r.headers.get("Content-Type", "")
            r.close()
            note = "" if ok else f"status {r.status_code}"
            if ok and "video" not in ct and "mp4" not in ct and "octet" not in ct:
                note = f"unexpected content-type: {ct}"
            return UrlResult(url, ok, r.status_code, ct, note)

        # pdf / link: HEAD first, fall back to a light GET if HEAD is unsupported.
        r = requests.head(url, headers=_UA, allow_redirects=True, timeout=timeout)
        if r.status_code >= 400 or r.status_code == 405:
            r = requests.get(url, headers=_UA, allow_redirects=True, stream=True, timeout=timeout)
            r.close()
        ok = r.status_code < 400
        return UrlResult(url, ok, r.status_code, r.headers.get("Content-Type", ""),
                         "" if ok else f"status {r.status_code}")
    except requests.RequestException as exc:
        return UrlResult(url, False, 0, "", f"{type(exc).__name__}: {exc}")


def fetch_pdf_and_links(url: str, timeout: int = 60):
    """Download a PDF and return (UrlResult, embedded_link_urls). Verifies the
    payload really is a PDF (%PDF magic), then extracts /Annots URI links."""
    try:
        r = requests.get(url, headers=_UA, timeout=timeout)
    except requests.RequestException as exc:
        return UrlResult(url, False, 0, "", f"{type(exc).__name__}: {exc}"), []

    if r.status_code >= 400:
        return UrlResult(url, False, r.status_code, r.headers.get("Content-Type", ""),
                         f"status {r.status_code}"), []

    content = r.content
    ct = r.headers.get("Content-Type", "")
    if not content[:5].startswith(b"%PDF"):
        return UrlResult(url, False, r.status_code, ct, "payload is not a PDF"), []

    links = extract_pdf_links(content)
    return UrlResult(url, True, r.status_code, ct), links


def extract_pdf_links(pdf_bytes: bytes) -> list:
    """External URI hyperlinks embedded in the PDF's link annotations."""
    urls = []
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return urls
    for page in reader.pages:
        for annot in page.get("/Annots", []) or []:
            try:
                obj = annot.get_object()
            except Exception:
                continue
            action = obj.get("/A")
            if not action:
                continue
            uri = action.get("/URI")
            if uri:
                urls.append(str(uri))
    # De-dupe, keep order.
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out
