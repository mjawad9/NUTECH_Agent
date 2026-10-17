"""Simple student authentication (demo). Replace with your real student DB / portal API in production."""
import hashlib, hmac, json, os, secrets
from pathlib import Path

STUDENTS_FILE = Path(__file__).parent / "data" / "students.json"


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()


def load_students() -> dict:
    with open(STUDENTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def authenticate(student_id: str, password: str):
    """Return the student record (without credentials) or None."""
    student = load_students().get(student_id.strip().upper())
    if not student:
        return None
    attempt = hash_password(password, student["salt"])
    if hmac.compare_digest(attempt, student["password_hash"]):
        return {k: v for k, v in student.items() if k not in ("salt", "password_hash")} | {
            "student_id": student_id.strip().upper()
        }
    return None


def add_student(student_id: str, password: str, record: dict):
    """Helper to register a student: add_student('NU-2022-010', 'pass', {...})"""
    students = load_students() if STUDENTS_FILE.exists() else {}
    salt = secrets.token_hex(8)
    students[student_id.upper()] = {"salt": salt, "password_hash": hash_password(password, salt), **record}
    STUDENTS_FILE.write_text(json.dumps(students, indent=2), encoding="utf-8")
