"""Run once: python make_demo_students.py  -> creates data/students.json with demo accounts."""
from auth import add_student
import json
from auth import STUDENTS_FILE

STUDENTS_FILE.write_text("{}")
add_student("NU-2022-001", "demo123", {
    "name": "Ali Khan", "program": "BS Computer Engineering", "semester": 5,
    "courses": [
        {"code": "CE-301", "title": "Digital Signal Processing", "credit_hours": 3},
        {"code": "CE-305", "title": "Computer Architecture", "credit_hours": 3},
        {"code": "CE-307", "title": "Embedded Systems (Lab)", "credit_hours": 1},
    ],
    "attendance": {"CE-301": 88, "CE-305": 72, "CE-307": 79},
    "fee": {"semester_fee": 120000, "paid": 120000, "due": 0, "due_date": "2026-10-30", "late_fine": 0},
    "hostel": {"allotted": False},
})
add_student("NU-2023-014", "demo456", {
    "name": "Sara Ahmed", "program": "BS Software Engineering", "semester": 3,
    "courses": [
        {"code": "SE-201", "title": "Data Structures", "credit_hours": 3},
        {"code": "SE-203", "title": "Object Oriented Programming", "credit_hours": 3},
    ],
    "attendance": {"SE-201": 91, "SE-203": 68},
    "fee": {"semester_fee": 115000, "paid": 60000, "due": 55000, "due_date": "2026-10-15", "late_fine": 500},
    "hostel": {"allotted": True, "hostel_fee_due": 25000},
})
print("Demo students created: NU-2022-001/demo123, NU-2023-014/demo456")
