import os
import re

def replace_in_file(filepath, pattern, replacement):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    content = re.sub(pattern, replacement, content)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

# 1. Update FLASHEO DB and API URL in Aprovisionamiento
f_int = 'aprovisionamiento/core/services/flasheo_integration_service.py'
replace_in_file(f_int, r'FLASHEO_API_URL = .*', 'FLASHEO_API_URL = "http://localhost:8000/api/flasheo/onus/{query}/credentials"')
replace_in_file(f_int, r'FLASHEO_ROOT = .*', 'FLASHEO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))')
replace_in_file(f_int, r'FLASHEO_DB_PATH = .*', 'FLASHEO_DB_PATH = os.path.join(FLASHEO_ROOT, "intranet_local.db")')

# 2. Update DB Path in Flasheo
f_db = 'flasheo/core/database.py'
replace_in_file(f_db, r'DB_PATH = os\.path\.join\(CONFIG_DIR, "estacion_flasheo\.db"\)', 'DB_PATH = os.path.join(PROJECT_ROOT, "..", "intranet_local.db")')

# 3. Refactor imports safely
def refactor_imports(directory, module_name, old_packages):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                for pkg in old_packages:
                    # Match 'from pkg import' or 'from pkg.something import'
                    content = re.sub(rf'^from {pkg}(\.|\s+import)', rf'from {module_name}.{pkg}\1', content, flags=re.MULTILINE)
                    # Match 'import pkg'
                    content = re.sub(rf'^import {pkg}(\n|\s)', rf'import {module_name}.{pkg}\1', content, flags=re.MULTILINE)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

refactor_imports('flasheo', 'flasheo', ['core', 'api'])
refactor_imports('aprovisionamiento', 'aprovisionamiento', ['core', 'web'])

# 4. Add __init__.py to flasheo and aprovisionamiento
open('flasheo/__init__.py', 'w').close()
open('aprovisionamiento/__init__.py', 'w').close()

print('Done script')
