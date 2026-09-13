import os

file_path = r'c:\Users\wgallardo\Documents\Proyectos gravity\intranet\main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('date_only = str(raw_estado).split("T")[0]', 'date_only = str(raw_estado).split("T")[0].split(" ")[0][:10]')
content = content.replace('date_only = str(raw_inst).split("T")[0]', 'date_only = str(raw_inst).split("T")[0].split(" ")[0][:10]')
content = content.replace('date_only = str(raw_plan).split("T")[0]', 'date_only = str(raw_plan).split("T")[0].split(" ")[0][:10]')

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
