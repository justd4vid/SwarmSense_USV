import json
import time
import random
import math
from datetime import datetime
from typing import List, Dict

# Configuration
NUM_BOATS = 20
LOG_FILE = "swarm_log.jsonl"
SIMULATION_STEP_DELAY = 1.0  # Seconds between updates
AREA_CENTER = (24.0, 119.5)  # Taiwan Strait
AREA_RADIUS = 0.5  # Degrees

class USV:
    def __init__(self, boat_id: int):
        self.id = boat_id
        # Start at random positions around center
        self.lat = AREA_CENTER[0] + random.uniform(-AREA_RADIUS, AREA_RADIUS)
        self.lon = AREA_CENTER[1] + random.uniform(-AREA_RADIUS, AREA_RADIUS)
        self.battery = 100.0
        self.status = "IDLE"  # IDLE, MOVING, ERROR
        self.error_msg = ""
        self.course = random.uniform(0, 360)
        self.speed = 0.0

    def update(self):
        # Battery drain
        self.battery -= random.uniform(0.01, 0.05)
        if self.battery < 0: self.battery = 0

        # Random state changes
        if self.status == "ERROR":
            # 5% chance to resolve error
            if random.random() < 0.05:
                self.status = "IDLE"
                self.error_msg = ""
        else:
            # 2% chance to get an error
            if random.random() < 0.02:
                self.status = "ERROR"
                errors = ["Motor Failure", "GPS Signal Lost", "Comms Timeout", "Obstacle Detected"]
                self.error_msg = random.choice(errors)
            
            # Movement logic
            elif self.status == "IDLE":
                if random.random() < 0.2:
                    self.status = "MOVING"
                    self.speed = random.uniform(2.0, 10.0) # knots
                    self.course = random.uniform(0, 360)
            elif self.status == "MOVING":
                if random.random() < 0.1:
                    self.status = "IDLE"
                    self.speed = 0.0
                else:
                    # Move boat based on course/speed (simplified)
                    # 1 deg lat approx 111km. 10 knots is ~18km/h. 
                    # In 1 sec (simulation step), dist is tiny. 
                    # Exaggerating movement for demo visual purposes.
                    move_factor = 0.0001 * self.speed
                    self.lat += move_factor * math.cos(math.radians(self.course))
                    self.lon += move_factor * math.sin(math.radians(self.course))
                    
                    # Random course wiggle
                    self.course += random.uniform(-25, 25)

    def to_dict(self) -> Dict:
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "boat_id": self.id,
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "battery": round(self.battery, 1),
            "status": self.status,
            "error_details": self.error_msg,
            "speed_knots": round(self.speed, 2),
            "course_deg": round(self.course, 1)
        }

def run_simulation():
    boats = [USV(i) for i in range(1, NUM_BOATS + 1)]
    print(f"Starting simulation for {NUM_BOATS} USVs...")
    print(f"Writing logs to {LOG_FILE}")
    
    try:
        # Clear old log file
        with open(LOG_FILE, "w") as f:
            pass

        while True:
            updates = []
            with open(LOG_FILE, "a") as f:
                for boat in boats:
                    boat.update()
                    state = boat.to_dict()
                    f.write(json.dumps(state) + "\n")
                    updates.append(state)
            
            # Print explicit summary
            error_count = sum(1 for b in boats if b.status == "ERROR")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Swarm Status: {NUM_BOATS - error_count} OK, {error_count} ERR")
            
            time.sleep(SIMULATION_STEP_DELAY)
    except KeyboardInterrupt:
        print("\nSimulation stopped.")

if __name__ == "__main__":
    run_simulation()
