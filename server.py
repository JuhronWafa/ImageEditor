from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List
import uvicorn
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.clients: List[WebSocket] = []
        self.client_ids: Dict[WebSocket, int] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.append(websocket)
        self.client_ids[websocket] = id(websocket)
        print(f"Client {id(websocket)} connected")

    def disconnect(self, websocket: WebSocket):
        self.clients.remove(websocket)
        cid = self.client_ids.pop(websocket, None)
        print(f"Client {cid} disconnected")

    async def broadcast(self, message: str, exclude: WebSocket = None):
        for client in self.clients:
            if client != exclude:
                await client.send_text(message)

    async def broadcast_bytes(self, message: bytes, exclude: WebSocket = None):
        for client in self.clients:
            if client != exclude:
                await client.send_bytes(message)

manager = ConnectionManager()

@app.websocket("/ws/image")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    client_id = id(websocket)

    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    action = data.get("type")
                    image_id = data.get("image_id")

                    if action == "edit":
                        await manager.broadcast(json.dumps({
                            "type": "edit",
                            "image_id": image_id,
                            "data": data.get("data"),
                            "editor_id": client_id
                        }), exclude=websocket)

                    elif action == "image_upload":
                        await manager.broadcast(json.dumps({
                            "type": "image_upload",
                            "filename": data.get("filename", f"Image_{client_id}.png"),
                            "image_data": data.get("image_data"),
                            "sender_id": client_id
                        }), exclude=websocket)

                except json.JSONDecodeError:
                    print("Invalid JSON format")

            elif "bytes" in message:
                await manager.broadcast_bytes(message["bytes"], exclude=websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run("server:app", host="192.168.30.134", port=8000, reload=True)
