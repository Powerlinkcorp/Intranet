import os

main_file = "c:/Users/wgallardo/Documents/Proyectos gravity/intranet/main.py"
with open(main_file, "r", encoding="utf-8") as f:
    content = f.read()

if "import json" not in content:
    content = content.replace("import os", "import os\nimport json\nimport asyncio", 1)

if "StreamingResponse" not in content:
    content = content.replace("from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse", "from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse, StreamingResponse")

endpoints = """

# ==========================================
# ENDPOINTS REPORTES
# ==========================================

reporte_clients = []

async def notify_reporte_clients():
    for queue in reporte_clients:
        await queue.put("update")

@app.get("/reporte", response_class=HTMLResponse)
async def view_reporte(request: Request):
    return templates.TemplateResponse("reporte.html", {"request": request})

@app.get("/api/db")
async def api_get_db():
    try:
        with open("db.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        return {"reports": [], "afectaciones": [], "techs": [], "assignments": [], "motivos": [], "zonas": [], "users": [], "logs": []}

@app.post("/api/db")
async def api_post_db(request: Request):
    try:
        payload = await request.json()
        with open("db.json", "r+", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
            for key in ['reports', 'afectaciones', 'techs', 'assignments', 'motivos', 'zonas', 'users', 'logs']:
                if key in payload and isinstance(payload[key], list):
                    data[key] = payload[key]
            f.seek(0)
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.truncate()
        await notify_reporte_clients()
        return {"status": "ok", "message": "Database saved and clients notified"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/api/login")
async def api_reporte_login(request: Request):
    try:
        payload = await request.json()
        username = payload.get("username", "").strip().lower()
        password = payload.get("password", "").strip()
        try:
            with open("db.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"users": []}
            
        for user in data.get("users", []):
            u_name = str(user.get("username", "")).strip().lower()
            u_pass = str(user.get("password", "")).strip()
            if u_name == username and u_pass == password:
                return {
                    "status": "ok",
                    "success": True,
                    "user": {
                        "id": user.get("id"),
                        "username": user.get("username"),
                        "name": user.get("name") or user.get("username"),
                        "role": user.get("role") or "OPERADOR",
                        "permissions": user.get("permissions")
                    }
                }
        return JSONResponse(status_code=401, content={"status": "error", "success": False, "message": "Usuario o contraseña incorrectos"})
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.get("/api/stream")
async def api_reporte_stream(request: Request):
    queue = asyncio.Queue()
    reporte_clients.append(queue)
    async def event_generator():
        yield "data: connected\\n\\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield f"data: {data}\\n\\n"
                except asyncio.TimeoutError:
                    pass
        finally:
            if queue in reporte_clients:
                reporte_clients.remove(queue)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
"""

if "@app.get(\"/reporte\"" not in content:
    content += endpoints
    with open(main_file, "w", encoding="utf-8") as f:
        f.write(content)
    print("Endpoints agregados con éxito.")
else:
    print("Los endpoints ya estaban agregados.")
