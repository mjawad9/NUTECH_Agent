import json
import re
from pathlib import Path

import requests

from config import get_secret

RES_PATH = Path(__file__).parent / "data" / "resources.json"
if not RES_PATH.exists():
    raise FileNotFoundError(
        f"Missing {RES_PATH}. Upload the 'data' folder (resources.json, knowledge_base.json, students.json) to the repo."
    )
RESOURCES = json.loads(RES_PATH.read_text(encoding="utf-8"))["resources"]

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

STOP = {
    "a", "an", "the", "is", "are", "of", "in", "on", "at", "to", "for", "and", "or", "i", "my", "me",
    "do", "does", "how", "what", "which", "where", "when", "can", "you", "tell", "about", "there",
    "any", "it", "be", "will", "if", "please", "give", "list", "show", "link", "page", "resource",
}
SYN = {
    "fees": "fee", "tuition": "fee", "charges": "fee", "challan": "fee", "payment": "fee", "pay": "fee",
    "faculty": "department", "faculties": "department", "programme": "program", "degree": "program",
    "bachelor": "bs", "master": "ms", "doctorate": "phd", "apply": "admission",
    "application": "admission", "admissions": "admission", "hostels": "hostel",
    "accommodation": "hostel", "scholarships": "scholarship", "contacts": "contact",
    "phone": "contact", "email": "contact", "address": "contact",
}


def tokens(text: str) -> set:
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w in STOP:
            continue
        w = SYN.get(w, w)
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(SYN.get(w, w))
    return out


def find_links(query: str, audience: str, top_k: int = 3) -> list:
    """Return the best matching resource links for this audience. Entries with no URL are skipped."""
    q = tokens(query)
    scored = []
    for r in RESOURCES:
        if r.get("audience") not in (audience, "both"):
            continue
        url = r.get("url", "")
        if not url or url.upper().startswith("TODO"):
            continue
        score = (
            3 * len(q & tokens(" ".join(r.get("keywords", []))))
            + 2 * len(q & tokens(r.get("title", "")))
            + len(q & tokens(r.get("description", "")))
        )
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    links = [r for _, r in scored[:top_k]]
    if not links:
        links = [r for r in RESOURCES if r.get("default") and r.get("url") and not r["url"].upper().startswith("TODO")]
    return links


def format_links(links: list) -> str:
    if len(links) == 1:
        head = "Here is the direct page for your question:"
    else:
        head = "These pages should answer your question:"
    lines = [head]
    for r in links:
        lines.append(f"- [{r['title']}]({r['url']}): {r['description']}")
    return "\n".join(lines)


def _candidate_models() -> list:
    preferred = get_secret("GROQ_MODEL")
    models = [preferred] if preferred else []
    models += [m for m in FALLBACK_MODELS if m not in models]
    return [m.replace("groq/", "") for m in models]


def _chat(system: str, user: str) -> str:
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to Streamlit secrets.")
    errors = []
    for model in _candidate_models():
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "temperature": 0.1,
                "max_tokens": 600,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        errors.append(f"{model}: {resp.status_code} {resp.text[:150]}")
        if resp.status_code not in (400, 404):
            break
    raise RuntimeError("No Groq model worked. " + " | ".join(errors))


def ask_public(query: str, history: str = "") -> str:
    # Outsiders get direct links only. No model call is needed, so answers can't be invented.
    return format_links(find_links(query, "public"))


def ask_student(query: str, student: dict, history: str = "") -> str:
    links = find_links(query, "student")
    link_block = "\n".join(f"- {r['title']} ({r['url']}): {r['description']}" for r in links) or "None"
    system = (
        "You are the NUTECH help desk assistant, talking to a logged-in student. "
        f"Student: {student['name']}, {student['program']}, semester {student['semester']}.\n\n"
        "Answer personal questions (dues, late fine, attendance, courses, credit hours, hostel) "
        "ONLY from this student record. Warn clearly if attendance is at or below the minimum or a fee is overdue.\n"
        "For general policy questions, point to the matching resource links below. Do not invent policies, "
        "fees, dates or percentages. Be concise and friendly. Use the same language as the student.\n\n"
        f"Student record:\n{json.dumps(student, indent=2)}\n\n"
        f"Matching resource links:\n{link_block}"
    )
    answer = _chat(system, f"Recent conversation:\n{history or '(none)'}\n\nQuestion: {query}")
    if links:
        answer += "\n\n" + format_links(links)
    return answer
