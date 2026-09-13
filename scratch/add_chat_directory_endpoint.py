import os

file_path = r"c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

endpoint_code = """
@app.get("/api/users/chat_directory")
async def api_get_chat_directory(db: Session = Depends(get_db)):
    all_users = db.query(models.User).filter(models.User.is_active == True).all()
    employees = db.query(models.Employee).all()
    emp_map = {emp.name: emp.department for emp in employees}
    
    departments = {}
    for u in all_users:
        dept = emp_map.get(u.full_name, "General")
        if dept not in departments:
            departments[dept] = []
        departments[dept].append({
            "email": u.email,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url
        })
    return departments
"""

if "/api/users/chat_directory" not in content:
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n" + endpoint_code + "\n")
    print("Endpoint añadido.")
else:
    print("El endpoint ya existe.")
