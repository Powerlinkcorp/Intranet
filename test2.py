import urllib.request
import urllib.error

try:
    response = urllib.request.urlopen('http://127.0.0.1:8000/reporte', timeout=3)
    print("Success:", response.status)
except urllib.error.HTTPError as e:
    print("Error:", e.code)
    print("Body:", e.read().decode('utf-8'))
except Exception as e:
    print("Other error:", e)
