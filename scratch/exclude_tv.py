import os
import re

file_path = r'c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace: if planNew.upper() == 'IPTV' or tipoServicioNew == 'IPTV':
content = content.replace(
    "if planNew.upper() == 'IPTV' or tipoServicioNew == 'IPTV':",
    "if planNew.upper() in ['IPTV', 'TV'] or tipoServicioNew in ['IPTV', 'TV']:"
)

# Replace: if 'iptv' not in plan_lower:
content = content.replace(
    "if 'iptv' not in plan_lower:",
    "if 'iptv' not in plan_lower and 'tv' not in plan_lower:"
)

# Replace: if plan.upper() == 'IPTV' or service_type == 'IPTV':
content = content.replace(
    "if plan.upper() == 'IPTV' or service_type == 'IPTV':",
    "if plan.upper() in ['IPTV', 'TV'] or service_type in ['IPTV', 'TV']:"
)

# Replace: if plan == 'IPTV' or service_type == 'IPTV':
content = content.replace(
    "if plan == 'IPTV' or service_type == 'IPTV':",
    "if plan in ['IPTV', 'TV'] or service_type in ['IPTV', 'TV']:"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done replacing TV plans')
