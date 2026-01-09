import json
import random
import math
from datetime import datetime, timedelta
from typing import Dict

# Configuration
NUM_BOATS = 20
LOG_FILE = "sim_log.jsonl"
SIMULATION_DURATION_SEC = 60 * 10  # Generate 10 minutes of data. 
SIMULATION_STEP_SEC = 1.0  # Seconds between updates
AREA_CENTER = (24.0, 119.5)  # Taiwan Strait near Penghu County
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

    def step_sim(self):
        # Battery drain (per virtual second)
        self.battery -= random.uniform(0.001, 0.005) 

        if self.battery < 0: self.battery = 0

        # Random state changes
        if self.status == "ERROR":
            # 5% chance to resolve error
            if random.random() < 0.05:
                self.status = "IDLE"
                self.error_msg = ""
        else:
            # 1% chance to get an error
            if random.random() < 0.02:
                self.status = "ERROR"
                errors = ["Motor Failure", "GPS Signal Lost", "Comms Timeout"]
                self.error_msg = random.choice(errors)
            
            # Movement logic
            elif self.status == "IDLE":
                if random.random() < 0.05:
                    self.status = "MOVING"
                    self.speed = random.uniform(4.0, 10.0) # knots
                    self.course = random.uniform(0, 360)
            elif self.status == "MOVING":
                if random.random() < 0.01:
                    self.status = "IDLE"
                    self.speed = 0.0
                else:
                    # Realistic movement: 1 knot = 0.0005144 meters per second

                    # For visualization, we keep your move_factor but scale it

                    move_factor = 0.00001 * self.speed 
                    self.lat += move_factor * math.cos(math.radians(self.course))
                    self.lon += move_factor * math.sin(math.radians(self.course))
                    self.course += random.uniform(-5, 5) # Random wiggle

    def to_dict(self, current_virtual_time: datetime) -> Dict:
        return {
            "timestamp": current_virtual_time.isoformat() + "Z",
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

    # Define the start time
    virtual_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    print(f"Starting simulation for {NUM_BOATS} USVs...")
    print(f"Writing logs to {LOG_FILE}")
    try:
        with open(LOG_FILE, "w") as f:
            for _ in range(SIMULATION_DURATION_SEC):
                for boat in boats:
                    boat.step_sim()
                    f.write(json.dumps(boat.to_dict(virtual_time)) + "\n")
                
                # Increment the virtual clock by 1 second
                virtual_time += timedelta(seconds=SIMULATION_STEP_SEC)
        print(f"Simulation Complete! Data written to {LOG_FILE}")
    except KeyboardInterrupt:
        print("\nSimulation stopped.")

if __name__ == "__main__":
    run_simulation()
