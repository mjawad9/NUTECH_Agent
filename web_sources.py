import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://nutech.edu.pk/"   # confirm this is the official NUTECH address

# Add the exact URLs of pages you know have important info (departments, fees, admissions).
# These are read first, before the crawler follows links.
SEED_URLS = [
    "https://nutech.edu.pk/",
    "https://nutech.edu.pk/admission/undergraduate/",
     "https://nutech.edu.pk/program/postgraduate/",   <- paste real department/faculty page URLs here
     "https://nutech.edu.pk/admissions",
]

MAX_PAGES = 30
CACHE_SECONDS = 6 * 3600
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc", ".docx", ".xls", ".xlsx")
HEADERS = {"User-Agent": "NUTECH-Smart-Assistant/1.0"}

_cache = {"time": 0.0, "chunks": []}


def _fetch(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except Exception:
        return None
    if "text/html" not in r.headers.get("Content-Type", ""):
        return None
    return r.text


def _page_chunks(url: str, html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):   # menus and headers are kept
        tag.decompose()
    lines = [re.sub(r"\s+", " ", line).strip() for line in soup.get_text("\n").split("\n")]
    return [{"source": url, "text": line} for line in lines if len(line) > 15]


def _links(url: str, html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(BASE_URL).netloc
    found = []
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"]).split("#")[0]
        if urlparse(full).netloc == host and not full.lower().endswith(SKIP_EXTENSIONS) and full not in found:
            found.append(full)
    return found


def load_site() -> list:
    if _cache["chunks"] and time.time() - _cache["time"] < CACHE_SECONDS:
        return _cache["chunks"]
    chunks, seen = [], set()
    queue = list(SEED_URLS) + [BASE_URL]
    while queue and len(seen) < MAX_PAGES:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        html = _fetch(url)
        if not html:
            continue
        chunks += _page_chunks(url, html)
        queue += [link for link in _links(url, html) if link not in seen]
    _cache.update(time=time.time(), chunks=chunks)
    return chunks


def _words(text: str) -> set:
    # Simple plural handling: "departments" matches "department", "faculties" matches "faculty"
    out = set()
    for w in re.findall(r"[a-z]+", text.lower()):
        if len(w) > 3 and w.endswith("s"):
            out.add(w[:-1])
        out.add(w)
    return out


def search_site(query: str, top_k: int = 6) -> str:
    words = _words(query)
    scored = []
    for chunk in load_site():
        overlap = len(words & _words(chunk["text"]))
        if overlap:
            scored.append((overlap, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return "\n".join(f"[{c['source']}] {c['text']}" for _, c in scored[:top_k])
