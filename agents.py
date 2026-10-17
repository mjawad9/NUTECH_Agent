import json
import os
import re
from pathlib import Path

from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

from config import get_secret

KB_PATH = Path(__file__).parent / "data" / "knowledge_base.json"
if not KB_PATH.exists():
    raise FileNotFoundError(
        f"Missing {KB_PATH}. Upload the 'data' folder (knowledge_base.json and students.json) to the repo."
    )
KB = json.loads(KB_PATH.read_text(encoding="utf-8"))


def get_llm() -> LLM:
    api_key = get_secret("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to Streamlit secrets or your .env file.")
    os.environ["GROQ_API_KEY"] = api_key
    return LLM(
        model=get_secret("GROQ_MODEL", "groq/llama-3.3-70b-versatile"),
        api_key=api_key,
        temperature=0.2,
    )


def _search(section: dict, query: str, top_k: int = 3) -> str:
    words = set(re.findall(r"\w+", query.lower()))
    scored = []
    for key, text in section.items():
        haystack = set(re.findall(r"\w+", (key.replace("_", " ") + " " + text).lower()))
        scored.append((len(words & haystack), key, text))
    scored.sort(reverse=True)
    hits = [f"[{k}] {t}" for s, k, t in scored[:top_k] if s > 0]
    return "\n\n".join(hits) or "No matching information found in the knowledge base."


@tool("Public University Info Search")
def public_search(query: str) -> str:
    """Search NUTECH public info: admissions, BS/MS/PhD programs, departments, fees, scholarships, contact."""
    return _search(KB["public"], query)


@tool("Student Policy Search")
def student_policy_search(query: str) -> str:
    """Search NUTECH student policies: late fee, fee submission, credit hours, attendance, hostel, registration."""
    return _search({**KB["student"], **KB["public"]}, query)


def _student_tool(student: dict):
    """Tool bound to ONE logged-in student, so the agent can never read other students' data."""
    @tool("My Student Record")
    def my_record(question: str) -> str:
        """Get the logged-in student's own data: courses, credit hours, attendance, fee dues, late fine, hostel."""
        return json.dumps(student, indent=2)
    return my_record


def _build(role_goal: str, tools: list, user_query: str, history: str, extra_rules: str):
    llm = get_llm()
    retriever = Agent(
        role="NUTECH Information Retriever",
        goal="Find the exact, relevant facts needed to answer the query using the tools.",
        backstory="You work in the NUTECH help desk. You only trust tool results, never guess.",
        tools=tools, llm=llm, allow_delegation=False, verbose=False,
    )
    advisor = Agent(
        role="NUTECH Help Desk Advisor",
        goal=role_goal,
        backstory="A friendly, clear and honest university advisor who answers in the user's language "
                  "(English or Roman Urdu/Urdu as the user writes).",
        llm=llm, allow_delegation=False, verbose=False,
    )
    t1 = Task(
        description=f"Conversation so far:\n{history or '(none)'}\n\nUser query: {user_query}\n\n"
                    "Use your tools to collect every fact relevant to this query.",
        expected_output="A concise list of relevant facts from the tools.",
        agent=retriever,
    )
    t2 = Task(
        description=f"Write the final answer to: {user_query}\n\nRules:\n"
                    "- Use ONLY the retrieved facts. If a fact is missing or says TODO, say you don't have "
                    "that information yet and suggest contacting the relevant NUTECH office.\n"
                    "- Never invent fees, dates, percentages or policies.\n"
                    f"- {extra_rules}\n- Be concise, well structured, friendly.",
        expected_output="A clear, helpful final answer for the user.",
        agent=advisor, context=[t1],
    )
    return Crew(agents=[retriever, advisor], tasks=[t1, t2], process=Process.sequential, verbose=False)


def ask_public(query: str, history: str = "") -> str:
    crew = _build(
        "Help prospective students with admissions, programs, departments and fees.",
        [public_search], query, history,
        "You are talking to a prospective (outside) student. Do not discuss private student data.",
    )
    return str(crew.kickoff())


def ask_student(query: str, student: dict, history: str = "") -> str:
    crew = _build(
        "Help the logged-in NUTECH student with fees, courses, attendance, hostel and university issues.",
        [student_policy_search, _student_tool(student)], query, history,
        f"You are talking to {student['name']} ({student['program']}). Use their own record for personal "
        "questions (dues, attendance, credit hours) and policies for general ones. "
        "Warn them if attendance is near/below the minimum or if fee is overdue.",
    )
    return str(crew.kickoff())
