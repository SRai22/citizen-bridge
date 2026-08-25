from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.connections[user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        connections = self.connections.get(user_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self.connections.pop(user_id, None)

    async def broadcast_to_user(self, user_id: str, message: dict) -> None:
        dead = []
        for websocket in self.connections.get(user_id, set()).copy():
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket, user_id)

    async def broadcast_to_users(self, user_ids: list[str], message: dict) -> None:
        for user_id in user_ids:
            await self.broadcast_to_user(user_id, message)
