import json
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Configuration
NUM_FRIENDLY_BOATS = 10
NUM_ADVERSARY_BOATS = 2
LOG_FILE = "sim_log.jsonl"
SIMULATION_DURATION_SEC = 60 * 10  # Generate 10 minutes of data
SIMULATION_STEP_SEC = 1.0  # Time between updates (simulation tick)
AREA_CENTER = (24.0, 119.5)  # Taiwan Strait near Penghu County
AREA_RADIUS_DEG = 0.1  # 0.1 degree latitude ~ 11 km

# Error rates
ERROR_TRIGGER_RATE = 0.001  # 0.1% per second (~1 error every 16 minutes)
ERROR_RECOVERY_RATE = 0.1   # 10% per second (~10 seconds to recover)

# Movement parameters
FRIENDLY_MAX_SPEED = 15.0  # knots
FRIENDLY_ACCELERATION = 2.0  # knots per second
FRIENDLY_DECELERATION = 3.0  # knots per second

ADVERSARY_MAX_SPEED = 10  # knots
ADVERSARY_ACCELERATION = 1.5  # knots per second
ADVERSARY_DECELERATION = 2.5  # knots per second

INTERCEPT_DISTANCE = 0.002  # degrees (~200m) - stay this close to target
COLLISION_AVOIDANCE_DISTANCE = 0.0005  # degrees (~50m) - don't get closer than this

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in degrees between two points"""
    return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing from point 1 to point 2 in degrees"""
    dx = lon2 - lon1
    dy = lat2 - lat1
    bearing = math.degrees(math.atan2(dx, dy))
    return (bearing + 360) % 360

class AdversaryBoat:
    def __init__(self, boat_id: int):
        self.id = boat_id
        # Start at random positions
        self.lat = AREA_CENTER[0] + random.uniform(-AREA_RADIUS_DEG, AREA_RADIUS_DEG)
        self.lon = AREA_CENTER[1] + random.uniform(-AREA_RADIUS_DEG, AREA_RADIUS_DEG)
        self.course = random.uniform(0, 360)
        self.speed = random.uniform(3.0, 6.0)  # Start with some movement
        self.target_speed = self.speed
        self.target_course = self.course
        self.max_turn_rate = 8.0  # degrees per second
        
    def step_sim(self, dt: float):
        # Random course/speed changes
        if random.random() < 0.02 * dt:
            self.target_course = random.uniform(0, 360)
        if random.random() < 0.01 * dt:
            self.target_speed = random.uniform(2.0, ADVERSARY_MAX_SPEED)
        
        # Accelerate/decelerate toward target speed
        speed_diff = self.target_speed - self.speed
        if abs(speed_diff) > 0.1:
            if speed_diff > 0:
                accel = min(ADVERSARY_ACCELERATION * dt, speed_diff)
                self.speed += accel
            else:
                decel = min(ADVERSARY_DECELERATION * dt, abs(speed_diff))
                self.speed -= decel
        else:
            self.speed = self.target_speed
        
        # Smooth turning
        diff = (self.target_course - self.course + 180) % 360 - 180
        max_turn = self.max_turn_rate * dt
        if abs(diff) > max_turn:
            step_turn = max_turn if diff > 0 else -max_turn
            self.course = (self.course + step_turn) % 360
        else:
            self.course = self.target_course
        
        # Move boat
        if self.speed > 0:
            speed_kmh = self.speed * 1.852
            distance_km = speed_kmh * (dt / 3600.0)
            distance_deg = distance_km / 111.32
            
            self.lat += distance_deg * math.cos(math.radians(self.course))
            lon_factor = math.cos(math.radians(self.lat))
            self.lon += distance_deg * math.sin(math.radians(self.course)) / lon_factor
            
            # Small jitter
            self.course = (self.course + random.uniform(-0.3, 0.3)) % 360

    def to_dict(self, current_virtual_time: datetime) -> Dict:
        return {
            "timestamp": current_virtual_time.isoformat() + "Z",
            "boat_id": f"ADV-{self.id}",
            "type": "adversary",
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "speed_knots": round(self.speed, 1),
            "course_deg": round(self.course, 1)
        }

class USV:
    def __init__(self, boat_id: int):
        self.id = boat_id
        # Start at random positions
        self.lat = AREA_CENTER[0] + random.uniform(-AREA_RADIUS_DEG, AREA_RADIUS_DEG)
        self.lon = AREA_CENTER[1] + random.uniform(-AREA_RADIUS_DEG, AREA_RADIUS_DEG)
        self.battery = 100.0
        self.status = "IDLE"  # IDLE, TRACKING, ERROR
        self.error_msg = ""
        self.course = random.uniform(0, 360)
        self.speed = 0.0
        self.target_speed = 0.0
        self.max_turn_rate = 15.0  # degrees per second (more agile than adversary)
        self.assigned_target: Optional[AdversaryBoat] = None
        
    def assign_closest_target(self, adversaries: List[AdversaryBoat]):
        """Find and assign the closest adversary boat as target"""
        min_dist = float('inf')
        closest = None
        
        for adv in adversaries:
            dist = calculate_distance(self.lat, self.lon, adv.lat, adv.lon)
            if dist < min_dist:
                min_dist = dist
                closest = adv
        
        self.assigned_target = closest

    def get_target_point(self):
        """Calculates the world coordinate for the USV's specific station."""
        if not self.assigned_target:
            return self.lat, self.lon
            
        adv = self.assigned_target
        # 1. Lead Pursuit: Project where the target will be in 10 seconds
        lead_time = 10.0 
        speed_deg_sec = (adv.speed * 1.852 / 3600.0) / 111.32
        projected_lat = adv.lat + (speed_deg_sec * lead_time * math.cos(math.radians(adv.course)))
        projected_lon = adv.lon + (speed_deg_sec * lead_time * math.sin(math.radians(adv.course)))

        # 2. Station Offset: Position relative to the adversary's heading
        # self.station_angle and self.station_dist are assigned by the manager
        offset_angle = (adv.course + self.station_angle) % 360
        station_lat = projected_lat + (self.station_dist * math.cos(math.radians(offset_angle)))
        station_lon = projected_lon + (self.station_dist * math.sin(math.radians(offset_angle)))
        
        return station_lat, station_lon

    def step_sim(self, dt: float):
        # Battery drain based on speed
        if self.speed > 0:
            propulsion_drain = (self.speed ** 2) * 0.00033 * dt
            self.battery -= propulsion_drain
            if self.battery < 0:
                self.battery = 0

        # Cannot move with dead battery
        if self.battery <= 0:
            self.target_speed = 0.0
            if self.status == "TRACKING":
                self.status = "IDLE"

        # Handle Error State
        if self.status == "ERROR":
            self.target_speed = 0.0
            if self.error_msg in ["GPS Signal Lost", "Comms Timeout"]:
                if random.random() < ERROR_RECOVERY_RATE * dt:
                    self.status = "IDLE"
                    self.error_msg = ""
        else:
            # Trigger new error (only if battery not dead)
            if self.battery > 0 and random.random() < ERROR_TRIGGER_RATE * dt:
                self.status = "ERROR"
                errors = ["Motor Failure", "GPS Signal Lost", "Comms Timeout"]
                self.error_msg = random.choice(errors)
                self.target_speed = 0.0
            
            # Tracking logic
            elif self.battery > 5 and self.assigned_target is not None:
                self.status = "TRACKING"
                
                # Calculate distance and bearing to target
                dist = calculate_distance(self.lat, self.lon, 
                                        self.assigned_target.lat, 
                                        self.assigned_target.lon)
                bearing = calculate_bearing(self.lat, self.lon,
                                          self.assigned_target.lat,
                                          self.assigned_target.lon)
                
                # Collision avoidance - if too close, back off
                if dist < COLLISION_AVOIDANCE_DISTANCE:
                    # Turn away and slow down
                    self.target_speed = 2.0
                    # Point away from target
                    target_course = (bearing + 180) % 360
                else:
                    # Point toward target
                    target_course = bearing
                    
                    # Speed control based on distance
                    if dist > INTERCEPT_DISTANCE * 3:
                        # Far away - go fast
                        self.target_speed = FRIENDLY_MAX_SPEED
                    elif dist > INTERCEPT_DISTANCE * 1.5:
                        # Medium distance - moderate speed
                        self.target_speed = 8.0
                    elif dist > INTERCEPT_DISTANCE:
                        # Close - match target speed
                        self.target_speed = self.assigned_target.speed
                    else:
                        # Very close - slow down slightly below target
                        self.target_speed = max(2.0, self.assigned_target.speed - 1.0)
                
                # Set course to intercept
                self.set_course(target_course)

        # Accelerate/decelerate toward target speed
        speed_diff = self.target_speed - self.speed
        if abs(speed_diff) > 0.1:
            if speed_diff > 0:
                accel = min(FRIENDLY_ACCELERATION * dt, speed_diff)
                self.speed = min(FRIENDLY_MAX_SPEED, self.speed + accel)
            else:
                decel = min(FRIENDLY_DECELERATION * dt, abs(speed_diff))
                self.speed = max(0, self.speed - decel)
        else:
            self.speed = self.target_speed
        
        # Enforce battery constraint
        if self.battery <= 0:
            self.speed = 0.0

        # Movement execution
        if self.speed > 0 and self.battery > 0:
            speed_kmh = self.speed * 1.852
            distance_km = speed_kmh * (dt / 3600.0)
            distance_deg = distance_km / 111.32
            
            self.lat += distance_deg * math.cos(math.radians(self.course))
            lon_factor = math.cos(math.radians(self.lat))
            self.lon += distance_deg * math.sin(math.radians(self.course)) / lon_factor
            
            # Small jitter
            self.course = (self.course + random.uniform(-0.3, 0.3)) % 360

    def set_course(self, target_course: float):
        """Set target course with smooth turning"""
        diff = (target_course - self.course + 180) % 360 - 180
        max_turn = self.max_turn_rate * SIMULATION_STEP_SEC
        
        if abs(diff) > max_turn:
            step_turn = max_turn if diff > 0 else -max_turn
            self.course = (self.course + step_turn) % 360
        else:
            self.course = target_course

    def to_dict(self, current_virtual_time: datetime) -> Dict:
        target_info = None
        if self.assigned_target:
            dist = calculate_distance(self.lat, self.lon,
                                    self.assigned_target.lat,
                                    self.assigned_target.lon)
            target_info = {
                "target_id": f"ADV-{self.assigned_target.id}",
                "distance_deg": round(dist, 6),
                "distance_m": round(dist * 111320, 1)  # Approximate meters
            }
        
        return {
            "timestamp": current_virtual_time.isoformat() + "Z",
            "boat_id": f"USV-{self.id}",
            "type": "friendly",
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "battery": round(self.battery, 1),
            "status": self.status,
            "error_details": self.error_msg,
            "speed_knots": round(self.speed, 1),
            "course_deg": round(self.course, 1),
            "target": target_info
        }

def run_simulation():
    # 1. Initialization
    friendly_boats = [USV(i) for i in range(1, NUM_FRIENDLY_BOATS + 1)]
    adversary_boats = [AdversaryBoat(i) for i in range(1, NUM_ADVERSARY_BOATS + 1)]
    
    # 2. Tactical Assignment (Wolfpack Logic)
    # Divide USVs among adversaries
    usvs_per_adv = len(friendly_boats) // len(adversary_boats)
    
    # Offsets: spread USVs around the target (in degrees relative to target heading)
    # e.g., 45° (Starboard Bow), -45° (Port Bow), 90° (Starboard Beam), etc.
    station_angles = [45, -45, 135, -135, 90, -90, 180, 0]
    
    print(f"Initializing Tactical Formations...")
    for i, adv in enumerate(adversary_boats):
        start_idx = i * usvs_per_adv
        end_idx = (i + 1) * usvs_per_adv if i < len(adversary_boats)-1 else len(friendly_boats)
        
        pack = friendly_boats[start_idx:end_idx]
        for j, usv in enumerate(pack):
            usv.assigned_target = adv
            usv.station_angle = station_angles[j % len(station_angles)]
            usv.station_dist = INTERCEPT_DISTANCE * 1.2 # Stay slightly outside target
            print(f"  USV-{usv.id} assigned to ADV-{adv.id} at {usv.station_angle}° station")

    # 3. Simulation Loop
    virtual_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    num_steps = int(SIMULATION_DURATION_SEC / SIMULATION_STEP_SEC)

    try:
        with open(LOG_FILE, "w") as f:
            for step in range(num_steps):
                # Update Adversaries (Movement)
                for adv in adversary_boats:
                    adv.step_sim(SIMULATION_STEP_SEC)
                
                # Update USVs (Tactical Navigation)
                for usv in friendly_boats:
                    if usv.status != "ERROR" and usv.battery > 0:
                        # Find where our assigned station is now
                        target_lat, target_lon = usv.get_target_point()
                        
                        # Calculate bearing and distance to that specific POINT
                        dist_to_station = calculate_distance(usv.lat, usv.lon, target_lat, target_lon)
                        bearing_to_station = calculate_bearing(usv.lat, usv.lon, target_lat, target_lon)
                        
                        # Set course and dynamic speed
                        usv.set_course(bearing_to_station)
                        
                        # High speed if far from station, match speed if close
                        if dist_to_station > INTERCEPT_DISTANCE:
                            usv.target_speed = FRIENDLY_MAX_SPEED
                        else:
                            usv.target_speed = usv.assigned_target.speed

                    usv.step_sim(SIMULATION_STEP_SEC)
                
                # Logging (JSONL)
                for boat in adversary_boats + friendly_boats:
                    f.write(json.dumps(boat.to_dict(virtual_time)) + "\n")
                
                virtual_time += timedelta(seconds=SIMULATION_STEP_SEC)
                
                if step % 60 == 0:
                    print(f"Simulating... {step//60}m completed.")

        print(f"\nSimulation Complete! Results saved to {LOG_FILE}")
                  
    except KeyboardInterrupt:
        print("\nSimulation aborted by user.")

if __name__ == "__main__":
    run_simulation()