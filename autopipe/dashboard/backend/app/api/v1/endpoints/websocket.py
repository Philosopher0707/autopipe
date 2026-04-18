"""WebSocket endpoints for real-time updates."""

import json
from datetime import datetime, timezone
from typing import Dict, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()

# Connection manager for WebSocket connections
class ConnectionManager:
    """Manages WebSocket connections with channel subscriptions."""
    
    def __init__(self):
        # channel -> set of websockets
        self.channels: Dict[str, Set[WebSocket]] = {}
        # websocket -> set of channels
        self.connections: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str):
        """Connect a websocket to a channel."""
        await websocket.accept()
        
        if channel not in self.channels:
            self.channels[channel] = set()
        
        self.channels[channel].add(websocket)
        
        if websocket not in self.connections:
            self.connections[websocket] = set()
        
        self.connections[websocket].add(channel)
    
    def disconnect(self, websocket: WebSocket, channel: str):
        """Disconnect a websocket from a channel."""
        if channel in self.channels:
            self.channels[channel].discard(websocket)
            if not self.channels[channel]:
                del self.channels[channel]
        
        if websocket in self.connections:
            self.connections[websocket].discard(channel)
    
    def disconnect_all(self, websocket: WebSocket):
        """Remove websocket from all channels."""
        if websocket in self.connections:
            for channel in self.connections[websocket]:
                if channel in self.channels:
                    self.channels[channel].discard(websocket)
                    if not self.channels[channel]:
                        del self.channels[channel]
            del self.connections[websocket]
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """Broadcast a message to all websockets in a channel."""
        if channel not in self.channels:
            return
        
        disconnected = set()
        message_json = json.dumps(message, default=str)
        
        for websocket in self.channels[channel]:
            try:
                await websocket.send_text(message_json)
            except Exception:
                disconnected.add(websocket)
        
        # Clean up disconnected websockets
        for websocket in disconnected:
            self.disconnect_all(websocket)
    
    async def send_to_websocket(self, websocket: WebSocket, message: dict):
        """Send a message to a specific websocket."""
        try:
            await websocket.send_text(json.dumps(message, default=str))
        except Exception:
            self.disconnect_all(websocket)


manager = ConnectionManager()


@router.websocket("/runs/{run_id}")
async def run_websocket(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time run updates."""
    channel = f"run:{run_id}"
    await manager.connect(websocket, channel)
    
    try:
        # Send initial connection confirmation
        await manager.send_to_websocket(websocket, {
            "type": "connection_established",
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                # Handle incoming commands if needed
                if message.get("type") == "ping":
                    await manager.send_to_websocket(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect_all(websocket)


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for dashboard real-time updates."""
    channel = "dashboard"
    await manager.connect(websocket, channel)
    
    try:
        # Send initial connection confirmation
        await manager.send_to_websocket(websocket, {
            "type": "connection_established",
            "channel": "dashboard",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_to_websocket(websocket, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect_all(websocket)


async def broadcast_run_status(run_id: str, status: str, data: dict = None):
    """Broadcast run status update."""
    message = {
        "type": "run.status",
        "run_id": run_id,
        "status": status,
        "data": data or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_channel(f"run:{run_id}", message)
    # Also broadcast to dashboard
    message["channel"] = f"run:{run_id}"
    await manager.broadcast_to_channel("dashboard", message)


async def broadcast_run_log(run_id: str, step_id: str, level: str, message_text: str):
    """Broadcast new log line."""
    message = {
        "type": "run.log",
        "run_id": run_id,
        "step_id": step_id,
        "level": level,
        "message": message_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_channel(f"run:{run_id}", message)


async def broadcast_run_metric(run_id: str, step_id: str, metric_name: str, value: float, step_number: int = None):
    """Broadcast metric update."""
    message = {
        "type": "run.metric",
        "run_id": run_id,
        "step_id": step_id,
        "metric_name": metric_name,
        "value": value,
        "step_number": step_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_channel(f"run:{run_id}", message)


async def broadcast_drift_alert(alert_id: str, feature_name: str, severity: str, message: str):
    """Broadcast drift alert."""
    alert_message = {
        "type": "drift.alert",
        "alert_id": alert_id,
        "feature_name": feature_name,
        "severity": severity,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_channel("dashboard", alert_message)


async def broadcast_model_promoted(model_id: str, version: int, from_stage: str, to_stage: str):
    """Broadcast model promotion event."""
    message = {
        "type": "model.promoted",
        "model_id": model_id,
        "version": version,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_channel("dashboard", message)


async def broadcast_dashboard_update(update_type: str, data: dict):
    """Broadcast general dashboard update."""
    message = {
        "type": f"dashboard.{update_type}",
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await manager.broadcast_to_channel("dashboard", message)
