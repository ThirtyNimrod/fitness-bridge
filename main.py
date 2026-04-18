import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Project imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.utils.logger import app_logger
from src.sync.service import run_sync_with_lock
from config import BACKGROUND_SYNC_INTERVAL, validate_config
from src.agents.router import build_graph
from langchain_core.messages import HumanMessage, AIMessage
from src.utils.database import (
    init_db, 
    get_workouts_filtered, 
    get_sessions, 
    create_session, 
    get_api_token,
    get_chat_history,
    save_message
)

load_dotenv()

# --- Background Sync Task ---

async def background_sync_task():
    """Infinite loop for background synchronization."""
    while True:
        try:
            app_logger.info("Background sync task triggered")
            run_sync_with_lock(force=False)
        except Exception as e:
            app_logger.error(f"Background sync task failed: {e}")
        
        await asyncio.sleep(BACKGROUND_SYNC_INTERVAL)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    init_db()
    
    # Validate config
    warnings = validate_config()
    for w in warnings:
        app_logger.warning(f"[CONFIG] {w}")
    
    # Initial startup sync (optional, can be moved to background)
    app_logger.info("Starting initial sync...")
    asyncio.create_task(asyncio.to_thread(run_sync_with_lock, force=False))
    
    # Start the continuous background sync loop
    sync_task = asyncio.create_task(background_sync_task())
    
    yield
    
    # Shutdown actions
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        app_logger.info("Background sync task cancelled during shutdown")

# --- App Initialization ---

app = FastAPI(
    title="Fitness Bridge API",
    description="Backend API for Fitness Bridge AI",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---

class ChatMessageRequest(BaseModel):
    session_id: str
    message: str

class SessionCreateRequest(BaseModel):
    title: str = "New Session"

# --- Endpoints ---

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

@app.get("/api/workouts")
async def get_workouts(
    start_date: str = None, 
    end_date: str = None, 
    limit: int = 50, 
    offset: int = 0
):
    try:
        workouts = get_workouts_filtered(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        return {"workouts": workouts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": get_sessions()}

@app.post("/api/sessions")
async def create_new_session(req: SessionCreateRequest):
    session_id = create_session(req.title)
    return {"session_id": session_id}

@app.get("/api/tokens/status")
async def get_tokens_status():
    return {
        "strava": {"has_token": get_api_token("strava") is not None},
        "fitbit": {"has_token": get_api_token("fitbit") is not None},
    }

@app.post("/api/chat")
async def chat_agent_endpoint(req: ChatMessageRequest):
    """Process a message through the AI Coach multi-agent graph."""
    try:
        # 1. Fetch history
        history = get_chat_history(req.session_id)
        
        # 2. Format for LangGraph
        messages = []
        for h in history:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            else:
                messages.append(AIMessage(content=h["content"]))
        
        # Add new message
        messages.append(HumanMessage(content=req.message))
        save_message(req.session_id, "user", req.message)
        
        # 3. Invoke Graph
        graph = build_graph()
        result = await asyncio.to_thread(graph.invoke, {"messages": messages})
        
        # 4. Save response
        response_content = result["messages"][-1].content
        save_message(req.session_id, "assistant", response_content)
        
        return {
            "response": response_content,
            "agent": result.get("routed_to", "Coach")
        }
    except Exception as e:
        app_logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """Trigger an on-demand sync."""
    background_tasks.add_task(run_sync_with_lock, force=True)
    return {"message": "Sync triggered in background"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
