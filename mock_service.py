import asyncio
import os
import random
from fastapi import FastAPI, Response

app = FastAPI(title="Mock STT LLM TTS Provider")


@app.post("/pipeline/process")
async def process(payload: dict, response: Response):
    if random.random() < float(os.getenv("DOWNSTREAM_FAILURE_RATE", "0.20")):
        response.status_code = 503
        return {"status": "error", "reason": "downstream_timeout"}
    latency_ms = random.lognormvariate(float(os.getenv("DOWNSTREAM_LATENCY_MU", "5.7")), float(os.getenv("DOWNSTREAM_LATENCY_SIGMA", "0.55")))
    await asyncio.sleep(latency_ms / 1000)
    return {"status": "ok", "transcript": "synthetic transcript", "response_audio_ref": "synthetic", "latency_ms": round(latency_ms, 2)}


@app.get("/health")
async def health():
    return {"status": "ok"}
