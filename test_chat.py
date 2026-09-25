from main import app, templates, get_db
from database import SessionLocal
import models
import security
from fastapi import Request

db = SessionLocal()
user = db.query(models.User).first()

all_users = db.query(models.User).filter(models.User.is_active == True).all()
employees = db.query(models.Employee).all()
emp_map = {emp.name: emp.department for emp in employees}

departments = {}
for u in all_users:
    dept = emp_map.get(u.full_name, "General")
    if dept not in departments:
        departments[dept] = []
    departments[dept].append(u)

class DummyRequest:
    def __init__(self):
        self.scope = {"type": "http"}

request = DummyRequest()

try:
    print(templates.TemplateResponse(request, "chat.html", {
        "request": request,
        "user": user,
        "departments": departments
    }))
except Exception as e:
    import traceback
    traceback.print_exc()
