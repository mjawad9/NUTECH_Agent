# NUTECH Smart Assistant (CrewAI + Streamlit + Groq)

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env          # add your GROQ_API_KEY (https://console.groq.com)
python make_demo_students.py  # creates demo student accounts
streamlit run app.py
```
Demo logins: `NU-2022-001 / demo123`, `NU-2023-014 / demo456`

## Make it real
1. Put the NUTECH logo at `assets/logo.png`.
2. Replace every `TODO` in `data/knowledge_base.json` with official info (fees, programs, policies).
3. Replace `auth.py` / `students.json` with your real student database or portal API.
