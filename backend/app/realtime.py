import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Set, Any
from pydantic import BaseModel, Field
from fastapi import WebSocket


class RealtimeEvent(BaseModel):
    event_id: str
    type: str  # "INVOICE_PROCESSED", "PRICE_ALERT", "STOCK_UPDATE", "DEMAND_LOGGED", "PROFIT_LEAK", "DATA_RESET", "SYSTEM_STATUS"
    business_id: str
    title: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConnectionManager:
    def __init__(self):
        # Maps business_id -> Set of active WebSockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, business_id: str):
        await websocket.accept()
        async with self.lock:
            if business_id not in self.active_connections:
                self.active_connections[business_id] = set()
            self.active_connections[business_id].add(websocket)

    async def disconnect(self, websocket: WebSocket, business_id: str):
        async with self.lock:
            if business_id in self.active_connections:
                self.active_connections[business_id].discard(websocket)
                if not self.active_connections[business_id]:
                    del self.active_connections[business_id]

    async def broadcast(self, business_id: str, event: RealtimeEvent):
        payload = event.model_dump()
        dead_sockets = set()
        
        async with self.lock:
            connections = list(self.active_connections.get(business_id, []))

        for connection in connections:
            try:
                await connection.send_json(payload)
            except Exception:
                dead_sockets.add(connection)

        if dead_sockets:
            async with self.lock:
                if business_id in self.active_connections:
                    for dead in dead_sockets:
                        self.active_connections[business_id].discard(dead)
                    if not self.active_connections[business_id]:
                        del self.active_connections[business_id]


# Singleton connection manager instance
manager = ConnectionManager()
