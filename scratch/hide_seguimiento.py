import os

file_path = r'c:\Users\wgallardo\Documents\Proyectos gravity\intranet\templates\integracion.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target1 = """<button class="tab-btn cursor-pointer" onclick="changeTab('seguimiento')" id="tab-seguimiento">Seguimiento <span class="badge-count" id="badge-seguimiento">0</span></button>"""
replacement1 = """<button style="display: none;" class="tab-btn cursor-pointer" onclick="changeTab('seguimiento')" id="tab-seguimiento">Seguimiento <span class="badge-count" id="badge-seguimiento">0</span></button>"""

target2 = """<div class="bg-blue-50 border-l-4 border-blue-500 p-3 flex-1 rounded min-h-[70px]">
                                <p class="text-[11px] text-blue-700 font-semibold mb-1 leading-tight">Cambios Plan o Estado</p>
                                <p id="countSeguimiento" class="text-lg font-bold text-blue-900 leading-none">0</p>
                            </div>"""
replacement2 = """<div style="display: none;" class="bg-blue-50 border-l-4 border-blue-500 p-3 flex-1 rounded min-h-[70px]">
                                <p class="text-[11px] text-blue-700 font-semibold mb-1 leading-tight">Cambios Plan o Estado</p>
                                <p id="countSeguimiento" class="text-lg font-bold text-blue-900 leading-none">0</p>
                            </div>"""

if target1 in content:
    content = content.replace(target1, replacement1)
    if target2 in content:
        content = content.replace(target2, replacement2)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Hidden tab successfully")
else:
    print("Target not found")
