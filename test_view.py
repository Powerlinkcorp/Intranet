import asyncio
from fastapi import Request
from main import view_reporte, get_db

async def run():
    class MockRequest:
        query_params = {}
        headers = {}
        cookies = {}
        state = type('State', (), {})()
        scope = {'type': 'http'}
        
    db = next(get_db())
    request = Request(scope={'type': 'http', 'query_string': b''})
    
    try:
        response = await view_reporte(request, db)
        print("Response generated successfully")
        print(response.status_code)
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(run())
