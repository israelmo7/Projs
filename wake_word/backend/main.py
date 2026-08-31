"""FastAPI backend for Nevo wake word dashboard."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import METRICS_JSON_PATH, MODEL_H5_PATH, MODEL_TFLITE_PATH, UDP_PORT
from inference.engine import InferenceEngine

from backend.brain import NevoBrain
from backend.events import EventBroadcaster
from backend.pipeline_worker import PipelineWorker
from backend.udp_server import UdpServer
from backend.ws import InferenceSession

broadcaster = EventBroadcaster()
brain = NevoBrain()
pipeline_worker = PipelineWorker()
engine: InferenceEngine | None = None
udp_server: UdpServer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine, udp_server

    try:
        engine = InferenceEngine()
    except FileNotFoundError:
        engine = None

    udp_server = UdpServer(broadcaster, brain, port=UDP_PORT)
    await udp_server.start()

    yield

    if udp_server:
        await udp_server.stop()


app = FastAPI(title="Nevo Wake Word API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineRunRequest(BaseModel):
    skip_tts: bool = False
    skip_bootstrap: bool = False


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": engine is not None and engine.loaded,
        "model_backend": engine.backend_name if engine else None,
        "ws_clients": broadcaster.client_count,
        "device": udp_server.status.to_dict() if udp_server else {},
    }


@app.get("/api/model/metrics")
async def model_metrics():
    if METRICS_JSON_PATH.exists():
        with open(METRICS_JSON_PATH) as f:
            return json.load(f)
    return {"error": "No metrics available. Run the training pipeline first."}


@app.get("/api/model/info")
async def model_info():
    h5_size = MODEL_H5_PATH.stat().st_size if MODEL_H5_PATH.exists() else 0
    tflite_size = MODEL_TFLITE_PATH.stat().st_size if MODEL_TFLITE_PATH.exists() else 0
    return {
        "h5_exists": MODEL_H5_PATH.exists(),
        "tflite_exists": MODEL_TFLITE_PATH.exists(),
        "h5_size_kb": round(h5_size / 1024, 2),
        "tflite_size_kb": round(tflite_size / 1024, 2),
        "backend": engine.backend_name if engine else None,
    }


@app.post("/api/pipeline/run")
async def run_pipeline(req: PipelineRunRequest):
    started = pipeline_worker.start(
        skip_tts=req.skip_tts,
        skip_bootstrap=req.skip_bootstrap,
    )
    if not started:
        return {"ok": False, "message": "Pipeline already running"}
    return {"ok": True, "message": "Pipeline started"}


@app.get("/api/pipeline/status")
async def pipeline_status():
    return pipeline_worker.get_status()


@app.get("/api/device/status")
async def device_status():
    if udp_server:
        return udp_server.status.to_dict()
    return {"connected": False}


@app.websocket("/ws/inference")
async def ws_inference(ws: WebSocket):
    if engine is None:
        await ws.accept()
        await ws.send_json(
            {"event": "error", "data": {"message": "Model not loaded. Run pipeline first."}}
        )
        await ws.close()
        return

    session = InferenceSession(ws, engine, brain, broadcaster)
    await session.run()


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """General event stream for dashboard panels."""
    await broadcaster.connect(ws)
    try:
        while True:
            await asyncio.sleep(30)
            await ws.send_json({"event": "ping", "data": {}})
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.disconnect(ws)


@app.get("/api/demo/script")
async def demo_script():
    return {
        "browser": [
            "Open the Live Demo panel and click Start Listening",
            "Grant microphone permission when prompted",
            "Say 'היי נבו' clearly — watch the confidence bar spike",
            "View the Whisper transcript in the Transcript panel",
        ],
        "esp32": [
            "Flash firmware: cd Firmware && pio run -t upload",
            "Configure secrets.h with WiFi and host IP",
            "Open Device Monitor — verify wake word scores",
            "Dashboard Device panel shows UDP stream + transcript on wake",
        ],
    }
