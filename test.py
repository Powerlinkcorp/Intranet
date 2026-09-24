import sys
from fastapi.testclient import TestClient
from main import app

try:
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get('/reporte')
    print("STATUS:", r.status_code)
    print("TEXT:", r.text)
except Exception as e:
    import traceback
    traceback.print_exc()
