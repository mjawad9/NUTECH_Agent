import json
import hmac
from pathlib import Path

from config import get_secret

STUDENTS_FILE = Path(__file__).parent / "data" / "students.json"


def load_students() -> dict:
    if not STUDENTS_FILE.exists():
        return {}
    return json.loads(STUDENTS_FILE.read_text(encoding="utf-8"))


def authenticate(nutech_id: str, access_code: str):
    """Return the student's record (without internal fields) if the ID exists and the code matches."""
    expected_code = get_secret("ACCESS_CODE")
    if not expected_code:
        return None  # login is disabled until ACCESS_CODE is set in Secrets
    student_id = nutech_id.strip().upper()
    student = load_students().get(student_id)
    if not student:
        return None
    if not hmac.compare_digest(access_code.strip(), str(expected_code)):
        return None
    return {k: v for k, v in student.items() if k not in ("salt", "password_hash")} | {"student_id": student_id}
