import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://nutech.edu.pk/"   # confirm this is the official NUTECH address
MAX_PAGES = 15                         # how many pages to read from the site
CACHE_SECONDS = 6 * 3600               # reload the site every 6 hours
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
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    lines = [re.sub(r"\s+", " ", line).strip() for line in soup.get_text("\n").split("\n")]
    return [{"source": url, "text": line} for line in lines if len(line) > 40]


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
    chunks, queue, seen = [], [BASE_URL], set()
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


def search_site(query: str, top_k: int = 4) -> str:
    words = set(re.findall(r"\w+", query.lower()))
    scored = []
    for chunk in load_site():
        overlap = len(words & set(re.findall(r"\w+", chunk["text"].lower())))
        if overlap:
            scored.append((overlap, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return "\n".join(f"[{c['source']}] {c['text']}" for _, c in scored[:top_k])
