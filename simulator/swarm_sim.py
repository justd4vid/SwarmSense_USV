import json
import random
import math
from datetime import datetime, timedelta
from typing import Dict

# Configuration
NUM_BOATS = 20
LOG_FILE = "sim_log.jsonl"
SIMULATION_DURATION_SEC = 60 * 10  # Generate 10 minutes of data. 
SIMULATION_STEP_SEC = 1.0  # Time between updates (simulation tick)
AREA_CENTER = (24.0, 119.5)  # Taiwan Strait near Penghu County
AREA_RADIUS_DEG = 0.1  # 1 degree latitude ~ 111 km

class USV:
    def __init__(self, boat_id: int):
        self.id = boat_id
        # Start at random positions around center
        self.lat = AREA_CENTER[0] + random.uniform(-AREA_RADIUS_DEG, AREA_RADIUS_DEG)
        self.lon = AREA_CENTER[1] + random.uniform(-AREA_RADIUS_DEG, AREA_RADIUS_DEG)
        self.battery = 100.0
        self.status = "IDLE"  # IDLE, MOVING, ERROR
        self.error_msg = ""
        self.course = random.uniform(0, 360)
        self.target_course = self.course # Target destination angle
        self.speed = 0.0
        self.max_turn_rate = 10.0

    def step_sim(self):
        propulsion_drain = (self.speed ** 3) * 0.0002 # Rule of thumb: Power ~ v^3
        self.battery -= propulsion_drain
        if self.battery < 0: self.battery = 0

        # Handle Error State
        if self.status == "ERROR":
            # Motor failure is permanent. Only check recovery for Comms/GPS.
            if self.error_msg in ["GPS Signal Lost", "Comms Timeout"]:
                if random.random() < 0.02:  # 2% chance to regain signal
                    self.status = "IDLE"
                    self.error_msg = ""
            
            # If still in ERROR, ensure speed is 0
            self.speed = 0.0
        else:
            # 1% chance to trigger a new error
            if random.random() < 0.01:
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
                elif random.random() < 0.0001: # 0.01% chance to change mind/target course while moving
                    self.target_course = random.uniform(0, 360)

        # Smooth Turning Logic
        if self.status == "MOVING":
            # Calculate the shortest distance between current course and target course
            diff = (self.target_course - self.course + 180) % 360 - 180
            
            # Apply turn rate limit
            if abs(diff) > self.max_turn_rate:
                # Turn by the max rate in the correct direction
                step_turn = self.max_turn_rate if diff > 0 else -self.max_turn_rate
                self.course = (self.course + step_turn) % 360
            else:
                # If we're close enough, snap to the target
                self.course = self.target_course
        
        # Movement Execution
        if self.speed > 0:
            move_factor = 0.000005 * self.speed
            self.lat += move_factor * math.cos(math.radians(self.course))
            self.lon += move_factor * math.sin(math.radians(self.course))
            
            # Add jitter
            self.course = (self.course + random.uniform(-0.5, 0.5)) % 360

    def to_dict(self, current_virtual_time: datetime) -> Dict:
        return {
            "timestamp": current_virtual_time.isoformat() + "Z",
            "boat_id": self.id,
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "battery": int (self.battery),
            "status": self.status,
            "error_details": self.error_msg,
            "speed_knots": round(self.speed, 1),
            "course_deg": int (self.course)
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
