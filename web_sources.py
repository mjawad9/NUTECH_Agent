import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://nutech.edu.pk/"
SEED_URLS = [
    BASE_URL,
    "https://nutech.edu.pk/about/coord-office",
    "https://nutech.edu.pk/about/registrar-office",
    # Add exact department, faculty, admission, and fee page URLs here when you find them.
]
MAX_PAGES = 40
CACHE_SECONDS = 6 * 3600
TIMEOUT = 15
HEADERS = {"User-Agent": "NUTECH-Smart-Assistant/1.0"}
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".doc", ".docx", ".xls", ".xlsx")
PRIORITY_WORDS = (
    "department", "faculty", "admission", "fee", "program", "schedule", "scholarship",
    "hostel", "contact", "about", "academic", "prospectus", "calendar",
)

STOPWORDS = {
    "a", "an", "the", "is", "are", "of", "in", "on", "at", "to", "for", "and", "or", "i", "my",
    "me", "do", "does", "how", "what", "which", "where", "when", "can", "you", "tell", "about",
    "there", "any", "it", "be", "will", "if", "please", "give", "list", "show",
}

# Different words that mean the same thing are mapped to one term.
SYNONYMS = {
    "fees": "fee", "charges": "fee", "tuition": "fee", "payment": "fee", "challan": "fee",
    "faculty": "department", "faculties": "department", "school": "department",
    "programme": "program", "programmes": "program", "degree": "program", "degrees": "program",
    "bs": "program", "ms": "program", "phd": "program", "bachelor": "program", "master": "program",
    "apply": "admission", "application": "admission", "admissions": "admission",
    "merit": "admission", "entry": "admission", "eligibility": "admission",
    "phone": "contact", "email": "contact", "address": "contact", "office": "contact",
    "accommodation": "hostel", "scholarships": "scholarship", "financial": "scholarship",
}

_cache = {"time": 0.0, "chunks": [], "pages": []}


def tokens(text: str) -> set:
    """Lowercase words with simple plural handling and synonyms, so 'fees' matches 'fee'."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOPWORDS:
            continue
        w = SYNONYMS.get(w, w)
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(SYNONYMS.get(w, w))
    return out


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _fetch(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception:
        return None
    if "text/html" not in r.headers.get("Content-Type", ""):
        return None
    return r.text


def _extract(url: str, html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    chunks, seen = [], set()
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "dt", "dd"]):
        text = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if len(text) < 20 or text in seen:
            continue
        seen.add(text)
        text = text[:600]
        chunks.append({
            "source": url,
            "title": title,
            "text": text,
            "tok": tokens(text),
            "ttok": tokens(title),
        })
    return chunks


def _links(url: str, html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    host = _host(BASE_URL)
    found = []
    for a in soup.find_all("a", href=True):
        full = urljoin(url, a["href"]).split("#")[0]
        if _host(full) != host or full.lower().endswith(SKIP_EXTENSIONS) or full in found:
            continue
        found.append(full)
    return found


def _is_priority(url: str) -> bool:
    return any(word in url.lower() for word in PRIORITY_WORDS)


def load_site() -> list:
    if _cache["chunks"] and time.time() - _cache["time"] < CACHE_SECONDS:
        return _cache["chunks"]
    chunks, pages, seen = [], [], set()
    queue = deque(SEED_URLS)
    while queue and len(seen) < MAX_PAGES:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        html = _fetch(url)
        if not html:
            continue
        pages.append(url)
        chunks += _extract(url, html)
        for link in _links(url, html):
            if link in seen:
                continue
            if _is_priority(link):
                queue.appendleft(link)   # read likely-useful pages first
            else:
                queue.append(link)
    if chunks:  # only cache a successful read, so a failed read is retried next time
        _cache.update(time=time.time(), chunks=chunks, pages=pages)
    return chunks


def site_pages() -> list:
    load_site()
    return list(_cache["pages"])


def search_site(query: str, top_k: int = 6) -> str:
    q = tokens(query)
    if not q:
        return ""
    scored = []
    for c in load_site():
        score = 2 * len(q & c["ttok"]) + len(q & c["tok"])
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    lines, used = [], set()
    for _, c in scored:
        if c["text"] in used:
            continue
        used.add(c["text"])
        lines.append(f"- {c['text']} (source: {c['source']})")
        if len(lines) >= top_k:
            break
    return "\n".join(lines)
