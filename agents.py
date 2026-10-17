import json
import re
from pathlib import Path

import requests

from config import get_secret
from web_sources import search_site

KB_PATH = Path(__file__).parent / "data" / "knowledge_base.json"
if not KB_PATH.exists():
    raise FileNotFoundError(
        f"Missing {KB_PATH}. Upload the 'data' folder (knowledge_base.json and students.json) to the repo."
    )
KB = json.loads(KB_PATH.read_text(encoding="utf-8"))

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Tried in order. A model Groq rejects (404) is skipped and the next one is used.
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]


def _search(section: dict, query: str, top_k: int = 3) -> str:
    words = set(re.findall(r"\w+", query.lower()))
    scored = []
    for key, text in section.items():
        haystack = set(re.findall(r"\w+", (key.replace("_", " ") + " " + text).lower()))
        scored.append((len(words & haystack), key, text))
    scored.sort(reverse=True)
    hits = [f"[{k}] {t}" for s, k, t in scored[:top_k] if s > 0]
    return "\n\n".join(hits)


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
                "temperature": 0.2,
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


RULES = (
    "You are the NUTECH help desk assistant. Answer using ONLY the facts provided. "
    "Facts marked with a web address come from the official NUTECH website; mention the page when useful. "
    "If a fact is missing or says TODO, say you don't have that information yet and suggest "
    "contacting the relevant NUTECH office. Never invent fees, dates, percentages or policies. "
    "Reply in the user's language (English or Roman Urdu/Urdu). Be concise, clear and friendly."
)


def ask_public(query: str, history: str = "") -> str:
    kb_facts = _search(KB["public"], query)
    web_facts = search_site(query)
    facts = "\n\n".join(x for x in [kb_facts, web_facts] if x) or "No matching information found."
    system = (
        f"{RULES}\n\nAudience: prospective (outside) student. Do not discuss private student data.\n\n"
        f"Facts:\n{facts}"
    )
    user = f"Conversation so far:\n{history or '(none)'}\n\nQuestion: {query}"
    return _chat(system, user)


def ask_student(query: str, student: dict, history: str = "") -> str:
    kb_facts = _search({**KB["student"], **KB["public"]}, query)
    web_facts = search_site(query)
    facts = "\n\n".join(x for x in [kb_facts, web_facts] if x) or "No matching policy facts found."
    record = json.dumps(student, indent=2)
    system = (
        f"{RULES}\n\nYou are talking to {student['name']} ({student['program']}). "
        "Use their own record for personal questions (dues, attendance, credit hours) and policies "
        "for general ones. Warn them if attendance is near or below the minimum or if fee is overdue.\n\n"
        f"Student record (personal, from the university system):\n{record}\n\nPolicy and website facts:\n{facts}"
    )
    user = f"Conversation so far:\n{history or '(none)'}\n\nQuestion: {query}"
    return _chat(system, user)
