from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
from rag_engine import SwarmRAG

app = FastAPI(title="Swarm Intelligence Assistant")

# CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, lock this down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG Engine
rag_engine = SwarmRAG()

import threading
import time

# Global state
swarm_state = {}
all_logs = []
playback_active = False
playback_thread = None

def playback_worker():
    global swarm_state, playback_active, all_logs
    print("Starting playback...")
    playback_active = True
    
    # Sort logs by timestamp just in case
    # Assuming timestamp is ISO string or comparable
    sorted_logs = sorted(all_logs, key=lambda x: x.get('timestamp', ''))

    for log in sorted_logs:
        if not playback_active:
            break
        
        # Update state for this boat
        swarm_state[log['boat_id']] = log
        
        # Simple pacing: small sleep
        # Adjust this value to speed up/slow down playback
        time.sleep(0.05) 
        
    print("Playback finished.")
    playback_active = False

class QueryRequest(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"status": "Swarm Assistant Backend Online"}

@app.get("/map-data")
def get_map_data():
    return {
        "boats": list(swarm_state.values()),
        "is_active": playback_active
    }

@app.post("/upload")
async def upload_log(file: UploadFile = File(...)):
    global all_logs, playback_active, playback_thread, swarm_state
    
    # Stop existing playback
    playback_active = False
    if playback_thread and playback_thread.is_alive():
        playback_thread.join(timeout=1.0)

    try:
        file_location = f"temp_{file.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        
        # Ingest and get raw data
        all_logs = rag_engine.ingest_logs(file_location)
        
        # Reset state
        swarm_state = {}
        
        # Start Playback Thread
        playback_thread = threading.Thread(target=playback_worker)
        playback_thread.daemon = True
        playback_thread.start()
        
        # Cleanup
        os.remove(file_location)
        
        return {"message": f"Successfully ingested {file.filename}. Playback started.", "count": len(all_logs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def query_swarm(request: QueryRequest):
    try:
        answer = rag_engine.query_swarm(request.query)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
