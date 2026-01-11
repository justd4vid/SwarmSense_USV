import sys
import os
# Add simulator directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../simulator"))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
from rag_engine import SwarmRAG
from swarm_sim import SwarmSimulator

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
playback_speed = 1.0

# Live Simulation State
simulation_instance = None
live_sim_active = False
live_sim_thread = None

def get_virtual_step_delay():
    # Base step is 1.0s.
    return 1.0 / playback_speed

def playback_worker():
    global swarm_state, playback_active, all_logs, playback_speed
    print("Starting playback...")
    playback_active = True
    
    # Sort logs by timestamp just in case
    # Assuming timestamp is ISO string or comparable
    sorted_logs = sorted(all_logs, key=lambda x: x.get('timestamp', ''))

    i = 0
    while i < len(sorted_logs):
        if not playback_active:
            break
        
        log = sorted_logs[i]
        current_ts = log['timestamp']
        batch = []
        while i < len(sorted_logs) and sorted_logs[i]['timestamp'] == current_ts:
            batch.append(sorted_logs[i])
            i += 1
            
        # Update state for batch
        for b in batch:
             swarm_state[b['boat_id']] = b
        
        # Wait for next step
        time.sleep(get_virtual_step_delay())
        
    print("Playback finished.")
    playback_active = False

def live_sim_worker():
    global swarm_state, live_sim_active, simulation_instance
    print("Starting live simulation...")
    live_sim_active = True
    
    while live_sim_active:
        if not simulation_instance:
            break
            
        # Run one step
        simulation_instance.step(1.0)
        
        # Get state and update global map
        current_state_list = simulation_instance.get_state()
        for boat in current_state_list:
            swarm_state[boat['boat_id']] = boat
            
        # Wait
        time.sleep(get_virtual_step_delay())
        
    print("Live simulation stopped.")
    live_sim_active = False

class QueryRequest(BaseModel):
    query: str

class SpeedRequest(BaseModel):
    speed: float

@app.get("/")
def read_root():
    return {"status": "Swarm Assistant Backend Online"}

@app.get("/map-data")
def get_map_data():
    return {
        "boats": list(swarm_state.values()),
        "is_active": playback_active or live_sim_active,
        "speed": playback_speed
    }

@app.post("/playback/speed")
async def set_speed(request: SpeedRequest):
    global playback_speed
    playback_speed = max(0.1, min(100.0, request.speed))
    return {"status": "ok", "speed": playback_speed}

@app.post("/simulation/start")
async def start_simulation():
    global playback_active, live_sim_active, simulation_instance, live_sim_thread, swarm_state
    
    # Stop any existing playback or sim
    playback_active = False
    live_sim_active = False
    if playback_thread and playback_thread.is_alive():
        playback_thread.join(timeout=0.5)
    if live_sim_thread and live_sim_thread.is_alive():
        live_sim_thread.join(timeout=0.5)

    # Init new Sim
    try:
        simulation_instance = SwarmSimulator()
        swarm_state = {}
        
        # Start Thread
        live_sim_thread = threading.Thread(target=live_sim_worker)
        live_sim_thread.daemon = True
        live_sim_thread.start()
        
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/simulation/stop")
async def stop_simulation():
    global live_sim_active
    live_sim_active = False
    return {"status": "stopped"}

@app.post("/upload")
async def upload_log(file: UploadFile = File(...)):
    global all_logs, playback_active, playback_thread, swarm_state, live_sim_active
    
    # Stop existing playback/sim
    playback_active = False
    live_sim_active = False
    if playback_thread and playback_thread.is_alive():
        playback_thread.join(timeout=1.0)
    if live_sim_thread and live_sim_thread.is_alive():
        live_sim_thread.join(timeout=1.0)
    
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
