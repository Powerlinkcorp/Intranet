import os
import re

templates_dir = r"c:\Users\wgallardo\Documents\Proyectos gravity\intranet\templates"
files = ["intranet.html", "directorio.html", "helpdesk.html", "historico.html", "integracion.html", "reportes.html", "rrhh.html", "chat.html"]

for file in files:
    file_path = os.path.join(templates_dir, file)
    if not os.path.exists(file_path):
        continue
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Eliminar enlace de chat en fast-links
    # Patrón: busca la línea que tenga href="/chat" (y su posible clase active) o href="javascript:void(0)" onclick="...chat..."
    content = re.sub(r'^[ \t]*<a href="/chat".*?>.*?</a >\s*$', '', content, flags=re.MULTILINE|re.IGNORECASE)
    content = re.sub(r'^[ \t]*<a[^>]*href="/chat"[^>]*>.*?</a>\s*$', '', content, flags=re.MULTILINE|re.IGNORECASE)
    
    # Si es rrhh.html y tiene un subtab-btn de chat (aunque creo que rrhh.html no tiene chat)
    
    # 2. Inyectar {% include 'global_chat.html' %} antes de </body>
    if "{% include 'global_chat.html' %}" not in content:
        content = content.replace("</body>", "{% include 'global_chat.html' %}\n</body>")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Inyectado en {file}")
