import base64
from pathlib import Path

import streamlit as st

from agents import ask_public, ask_student
from auth import authenticate
from voice import speak

st.set_page_config(page_title="NUTECH Smart Assistant", page_icon="🎓", layout="wide")

LOGO = Path(__file__).parent / "assets" / "logo.png"
NAVY, GOLD = "#0B2A5B", "#F2B705"

# ---------- Styling ----------
st.markdown(f"""
<style>
#MainMenu, footer {{visibility:hidden;}}
.hero {{background:linear-gradient(135deg,{NAVY} 0%,#1b4a9c 100%);padding:2.2rem 1rem;border-radius:20px;
        text-align:center;color:white;margin-bottom:1.5rem;box-shadow:0 8px 24px rgba(11,42,91,.25);}}
.hero h1 {{margin:.6rem 0 .2rem;font-size:2.2rem;color:white;}}
.hero p {{opacity:.9;margin:0;font-size:1.05rem;}}
.card {{background:white;border:1px solid #e5e9f2;border-top:5px solid {GOLD};border-radius:16px;
        padding:1.5rem;min-height:170px;box-shadow:0 4px 14px rgba(0,0,0,.06);color:#222;}}
.card h3 {{color:{NAVY};margin-top:0;}}
.topbar {{background:{NAVY};color:white;padding:.8rem 1.2rem;border-radius:12px;margin-bottom:1rem;}}
.stButton>button {{border-radius:10px;font-weight:600;}}
</style>""", unsafe_allow_html=True)


def logo_html(width=110):
    if LOGO.exists():
        b64 = base64.b64encode(LOGO.read_bytes()).decode()
        return f'<img src="data:image/png;base64,{b64}" width="{width}" style="background:white;border-radius:50%;padding:8px;">'
    return '<div style="font-size:3.5rem;">🎓</div>'  # shown until assets/logo.png is added


# ---------- Session state ----------
for k, v in {"mode": None, "student": None, "chat_public": [], "chat_student": []}.items():
    st.session_state.setdefault(k, v)


def go(mode):
    st.session_state.mode = mode
    st.rerun()


def history_text(chat, n=6):
    return "\n".join(f"{m['role']}: {m['content']}" for m in chat[-n:])


def chat_ui(key, chat_key, answer_fn, placeholder):
    chat = st.session_state[chat_key]
    for m in chat:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    pending = st.session_state.pop(f"{key}_quick", None)
    query = st.chat_input(placeholder) or pending
    if query:
        with st.chat_message("user"):
            st.markdown(query)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    reply = answer_fn(query, history_text(chat))
                except Exception as e:
                    reply = f"⚠️ Something went wrong: `{e}`. Check your API key in Secrets and your internet connection."
            st.markdown(reply)
            try:
                audio = speak(reply)
                if audio:
                    st.audio(audio, format="audio/mp3")
            except Exception:
                pass  # voice is optional; the text answer still shows
        chat += [{"role": "user", "content": query}, {"role": "assistant", "content": reply}]


def quick_buttons(key, items):
    cols = st.columns(len(items))
    for col, (label, q) in zip(cols, items):
        if col.button(label, key=f"{key}_{label}"):
            st.session_state[f"{key}_quick"] = q
            st.rerun()


# ---------- Pages ----------
def landing():
    st.markdown(f"""<div class="hero">{logo_html(120)}
        <h1>NUTECH Smart Assistant</h1>
        <p>National University of Technology · Your AI help desk for admissions, fees, courses and more</p></div>""",
                unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center;color:%s'>Who are you?</h3>" % NAVY, unsafe_allow_html=True)
    _, c1, c2, _ = st.columns([0.5, 2, 2, 0.5])
    with c1:
        st.markdown("""<div class="card"><h3>🧑‍🎓 University Student</h3>
        Login with your NUTECH ID and access code to ask about late fees, credit hours, attendance, fee submission,
        hostel and your personal dues.</div>""", unsafe_allow_html=True)
        if st.button("Student Login →", type="primary"):
            go("student_login")
    with c2:
        st.markdown("""<div class="card"><h3>🌍 Prospective / Outside Student</h3>
        No login needed. Ask about admissions, fees, BS / MS / PhD programs and departments.</div>""",
                    unsafe_allow_html=True)
        if st.button("Explore NUTECH →", type="primary"):
            go("public")


def public_page():
    st.markdown('<div class="topbar">🌍 <b>Prospective Student Portal</b></div>', unsafe_allow_html=True)
    if st.button("← Back to home"):
        go(None)
    st.markdown("#### Popular topics")
    quick_buttons("pub1", [("💰 Fees", "What is the fee structure?"),
                           ("🎓 BS Programs", "Which BS programs are offered and what is the eligibility?"),
                           ("📘 MS", "Tell me about MS programs and admission requirements."),
                           ("🔬 PhD", "Tell me about PhD programs and requirements.")])
    quick_buttons("pub2", [("🏛️ Departments", "List the departments at NUTECH."),
                           ("📝 Admission process", "How do I apply for admission?"),
                           ("🏆 Scholarships", "What scholarships are available?"),
                           ("🏠 Hostel", "Is hostel available for new students?")])
    st.divider()
    chat_ui("pub", "chat_public", lambda q, h: ask_public(q, h), "Ask anything about NUTECH admissions...")


def student_login():
    if st.button("← Back to home"):
        go(None)
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(f"<div style='text-align:center'>{logo_html(80)}</div>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align:center;color:{NAVY}'>Student Login</h2>", unsafe_allow_html=True)
        with st.form("login"):
            nutech_id = st.text_input("NUTECH ID", placeholder="e.g. NU-2022-001")
            access_code = st.text_input("Access Code", type="password")
            ok = st.form_submit_button("Login", type="primary")
        if ok:
            student = authenticate(nutech_id, access_code)
            if student:
                st.session_state.student = student
                go("student")
            else:
                st.error("Invalid NUTECH ID or access code.")


def student_page():
    s = st.session_state.student
    if not s:
        go("student_login")
    st.markdown(f'<div class="topbar">🧑‍🎓 <b>{s["name"]}</b> · {s["student_id"]} · {s["program"]} · Semester {s["semester"]}</div>',
                unsafe_allow_html=True)
    if st.button("Logout"):
        st.session_state.update(student=None, chat_student=[])
        go(None)
    st.markdown("#### Quick questions")
    quick_buttons("stu1", [("⏰ Late fee", "What is the late fee policy and do I have any late fine?"),
                           ("📚 Credit hours", "What are my courses and total credit hours?"),
                           ("📅 Attendance", "What is the minimum attendance and what is my attendance status?"),
                           ("💳 Fee process", "How do I submit my fee?")])
    quick_buttons("stu2", [("🏠 Hostel fee", "What is the hostel fee process?"),
                           ("🧾 My dues", "How much fee do I have due and when is the deadline?"),
                           ("📝 Registration", "How do I register or drop courses?"),
                           ("🆘 Get help", "I have an issue. Whom should I contact?")])
    st.divider()
    chat_ui("stu", "chat_student", lambda q, h: ask_student(q, s, h), "Ask about fees, courses, attendance, hostel...")


# ---------- Router ----------
PAGES = {None: landing, "public": public_page, "student_login": student_login, "student": student_page}
PAGES[st.session_state.mode]()
