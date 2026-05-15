from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.ollama_client import resolve_model_if_needed
from app.workflow.pipeline import run_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    await resolve_model_if_needed()
    yield


app = FastAPI(title="Intake Workflow", version="0.1.0", lifespan=lifespan)

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


class IntakeBody(BaseModel):
    text: str = Field(..., min_length=5, max_length=50000)


@app.post("/api/run")
async def api_run(body: IntakeBody):
    try:
        result = await run_pipeline(body.text)
        return JSONResponse(result)
    except Exception as e:
        msg = str(e) or e.__class__.__name__
        raise HTTPException(status_code=502, detail=msg) from e


@app.get("/")
async def index():
    index_path = STATIC / "index.html"
    if not index_path.is_file():
        return JSONResponse({"error": "static/index.html missing"}, status_code=500)
    return FileResponse(index_path)


app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
