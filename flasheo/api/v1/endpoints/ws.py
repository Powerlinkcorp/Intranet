# -*- coding: utf-8 -*-
"""
api.v1.endpoints.ws — WebSocket para telemetría en tiempo real de los 20 puertos y terminal.
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from flasheo.api.v1.endpoints.flasheo import get_status, get_logs

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            status_data = get_status()
            logs_data = get_logs(max_lines=60)
            payload = {
                "type": "telemetry",
                "status": status_data,
                "logs": logs_data.get("logs", []),
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
