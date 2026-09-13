import os, glob

target = """        {% if user.role == 'admin' or 'ver_integracion' in (user.permissions or '') %}
        <a href="/integracion"><i class="fa-solid fa-network-wired"></i> Integración</a>
        {% endif %}"""

replacement = """        {% if user.role == 'admin' or 'ver_integracion' in (user.permissions or '') %}
        <a href="/integracion"><i class="fa-solid fa-network-wired"></i> Integración</a>
        {% endif %}
        <a href="/historico"><i class="fa-solid fa-history"></i> Histórico</a>"""

for f in glob.glob('c:/Users/wgallardo/Documents/Proyectos gravity/intranet/templates/*.html'):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    if target in content:
        content = content.replace(target, replacement)
        with open(f, 'w', encoding='utf-8') as file:
            file.write(content)
        print('Updated ' + f)
