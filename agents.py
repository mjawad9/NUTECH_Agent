import json
import re
from pathlib import Path

import requests

from config import get_secret
from web_sources import search_site, tokens

KB_PATH = Path(__file__).parent / "data" / "knowledge_base.json"
if not KB_PATH.exists():
    raise FileNotFoundError(
        f"Missing {KB_PATH}. Upload the 'data' folder (knowledge_base.json and students.json) to the repo."
    )
KB = json.loads(KB_PATH.read_text(encoding="utf-8"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Tried in order after GROQ_MODEL from Secrets. A model Groq rejects (400/404) is skipped.
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

# Always included for outsiders, as general background, when filled in.
BACKGROUND_KEYS = ["about", "contact"]


def _is_filled(text: str) -> bool:
    return bool(text) and not text.strip().upper().startswith("TODO")


def _kb_facts(section: dict, query: str, top_k: int = 4) -> list:
    """Return the best matching knowledge-base entries, skipping placeholder (TODO) entries."""
    q = tokens(query)
    scored = []
    for key, text in section.items():
        if not _is_filled(text):
            continue
        score = 2 * len(q & tokens(key.replace("_", " "))) + len(q & tokens(text))
        if score > 0:
            scored.append((score, key, text))
    scored.sort(key=lambda x: x[0], reverse=True)
    facts = [f"- [{key}] {text}" for _, key, text in scored[:top_k]]
    for key in BACKGROUND_KEYS:
        text = section.get(key, "")
        line = f"- [{key}] {text}"
        if _is_filled(text) and line not in facts:
            facts.append(line)
    return facts


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
                "max_tokens": 800,
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
            break  # key or rate-limit problem: other models won't help
    raise RuntimeError("No Groq model worked. " + " | ".join(errors))


RULES = """You are the NUTECH (National University of Technology, Islamabad) help desk assistant.

How to answer:
- Answer the question directly in the first sentence or two. Never reply with only a link.
- Use the facts provided below as your only source of university-specific information. Do not add fees, dates, percentages, department names or policies from memory.
- If the facts contain the answer, give it clearly. Mention the source web page when it helps the person find more detail.
- If the facts only partly answer the question, give the part you know, say what is missing, and name the specific office to contact (use the contact facts if available).
- If the facts do not answer the question at all, say so in one sentence and point to the Coordination Section or Registrar Office with their web address.
- For lists (departments, programs, documents), use a short bulleted list.
- Reply in the same language the person uses (English, or Roman Urdu/Urdu).
- Be concise, warm and professional."""


def _build_user_message(history: str, query: str) -> str:
    return f"Recent conversation:\n{history or '(none)'}\n\nCurrent question: {query}"


def ask_public(query: str, history: str = "") -> str:
    kb = _kb_facts(KB["public"], query)
    web = search_site(query)
    facts = "\n".join(kb)
    if web:
        facts += "\n\nFrom the NUTECH website:\n" + web
    if not facts.strip():
        facts = "No facts found for this question."
    system = (
        f"{RULES}\n\n"
        "Audience: a prospective (outside) student. Do not share private student information.\n\n"
        f"Facts:\n{facts}"
    )
    return _chat(system, _build_user_message(history, query))


def ask_student(query: str, student: dict, history: str = "") -> str:
    kb = _kb_facts({**KB["student"], **KB["public"]}, query)
    web = search_site(query)
    facts = "\n".join(kb)
    if web:
        facts += "\n\nFrom the NUTECH website:\n" + web
    if not facts.strip():
        facts = "No policy facts found for this question."
    record = json.dumps(student, indent=2)
    system = (
        f"{RULES}\n\n"
        f"You are talking to {student['name']} ({student['program']}, semester {student['semester']}). "
        "Use their personal record for questions about their own dues, fines, attendance, courses, "
        "credit hours and hostel. Use the facts for general policy. "
        "Warn them clearly if attendance is at or below the minimum, or if a fee is overdue or has a late fine.\n\n"
        f"Student record (this student only):\n{record}\n\n"
        f"Policy and website facts:\n{facts}"
    )
    return _chat(system, _build_user_message(history, query))
