# backend/ws_price.py – the ONLY live websocket
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
clients: set[WebSocket] = set()

@router.websocket("/ws")
async def ws_price(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    logger.info(f"🔌 Price WebSocket connected (Total: {len(clients)})")
    try:
        while True:                       # block → keeps connection open
            await ws.receive_text()       # ignore whatever the client sends
    except WebSocketDisconnect:
        clients.discard(ws)
        logger.info(f"🔌 Price WebSocket disconnected (Total: {len(clients)})")

async def broadcast_price_update(price: float):
    """Broadcast price update to all connected clients - ONLY price updates, nothing else"""
    if not clients:
        return
    
    # Ensure price is properly formatted as a float with 2 decimal places
    formatted_price = round(float(price), 2)
    
    payload = {"type": "price_update", "data": {"price": formatted_price}}
    disconnected_clients = []
    
    logger.info(f"💰 Broadcasting price update: ${formatted_price:,.2f} to {len(clients)} clients")
    
    for ws in list(clients):
        try:
            await ws.send_json(payload)
        except Exception as e:
            logger.warning(f"Failed to send price update to client: {e}")
            disconnected_clients.append(ws)
    
    # Clean up disconnected clients
    for ws in disconnected_clients:
        clients.discard(ws)
    
    if disconnected_clients:
        logger.info(f"Cleaned up {len(disconnected_clients)} disconnected clients (Total: {len(clients)})") 