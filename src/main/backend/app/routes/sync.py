from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.realtime import register, unregister

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        unregister(ws)
    except Exception:
        unregister(ws)
