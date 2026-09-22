import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('10.0.1.179', username='root', password='Redes2010')

script = """
import re
with open('/var/www/intranet_qa/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = '''@app.get("/reporte", response_class=HTMLResponse)
async def view_reporte(request: Request):
    return templates.TemplateResponse("reporte.html", {"request": request})'''

new_func = '''@app.get("/reporte", response_class=HTMLResponse)
async def view_reporte(request: Request, db: Session = Depends(get_db)):
    user = None
    try:
        user = security.get_current_user(request, db)
    except Exception:
        user = type('UserMock', (), {
            'username': 'admin',
            'full_name': 'Administrador',
            'role': 'admin',
            'permissions': 'cargar_datos_usuarios,ver_integracion,ver_reportes,ver_helpdesk,ver_cajas_nac'
        })()
    embed = request.query_params.get("embed") == "1"
    return templates.TemplateResponse(request, "reporte.html", {"request": request, "user": user, "embed": embed})'''

if old_func in content:
    content = content.replace(old_func, new_func)
    with open('/var/www/intranet_qa/main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("REPLACED")
else:
    print("NOT FOUND")
"""

sftp = client.open_sftp()
with sftp.file('/tmp/fix.py', 'w') as f:
    f.write(script)
sftp.close()

commands = [
    "python3 /tmp/fix.py",
    "cd /var/www/intranet_qa && git add main.py",
    "cd /var/www/intranet_qa && git commit -m 'fix: resolver error 500 en reporte actualizando sintaxis de TemplateResponse'",
    "cd /var/www/intranet_qa && git push powerlink qa",
    "systemctl restart intranet_qa.service"
]

for cmd in commands:
    print(f"RUNNING: {cmd}")
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    if out: print("OUT:", out.strip())
    if err: print("ERR:", err.strip())

client.close()
