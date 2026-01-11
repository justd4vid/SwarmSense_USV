import json
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# --- Configuration ---
NUM_FRIENDLY_BOATS = 10
NUM_ADVERSARY_BOATS = 2
LOG_FILE = "sim_log.jsonl"
SIMULATION_DURATION_SEC = 60 * 10  # 10 minutes
SIMULATION_STEP_SEC = 1.0

# Map Settings: 10km x 10km centered at (24.0, 119.5)
AREA_CENTER_LAT = 24.0
AREA_CENTER_LON = 119.5
# Approx conversion: 1 deg lat = 111.32 km
# 1 deg lon = 111.32 * cos(lat) km. At 24 deg, cos(24) ~ 0.9135 -> ~101.7 km
LAT_DEG_PER_KM = 1 / 111.32
LON_DEG_PER_KM = 1 / 101.7 # Approximate at 24 deg

HALF_HEIGHT_KM = 5.0
HALF_WIDTH_KM = 5.0

MIN_LAT = AREA_CENTER_LAT - (HALF_HEIGHT_KM * LAT_DEG_PER_KM)
MAX_LAT = AREA_CENTER_LAT + (HALF_HEIGHT_KM * LAT_DEG_PER_KM)
MIN_LON = AREA_CENTER_LON - (HALF_WIDTH_KM * LON_DEG_PER_KM)
MAX_LON = AREA_CENTER_LON + (HALF_WIDTH_KM * LON_DEG_PER_KM)

# Movement Specs
FRIENDLY_MAX_SPEED_KNOTS = 15.0
ADVERSARY_SPEED_KNOTS = 10.0
FRIENDLY_TURN_RATE_DEG_PER_SEC = 36.0
NOISE_KNOTS = 0.5

KNOTS_TO_KMH = 1.852

def calculate_distance_km(lat1, lon1, lat2, lon2):
    """Haversine-ish approximation for short distances on a plane representation"""
    # Just use euclidean on degrees converted to km for simplicity in small area
    d_lat_km = (lat2 - lat1) / LAT_DEG_PER_KM
    d_lon_km = (lon2 - lon1) / LON_DEG_PER_KM
    return math.sqrt(d_lat_km**2 + d_lon_km**2)

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Bearing from p1 to p2, 0=North, 90=East"""
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    # Adjust for aspect ratio of lat/lon degrees
    d_lon_corrected = d_lon * (111.32 * math.cos(math.radians(lat1)))
    d_lat_corrected = d_lat * 111.32
    
    angle = math.degrees(math.atan2(d_lon_corrected, d_lat_corrected))
    return (angle + 360) % 360

def move_point(lat, lon, speed_knots, course_deg, dt_sec):
    """Returns new (lat, lon) after moving"""
    # Add random noise to velocity components
    # Noise is applied to the effective velocity vector
    
    speed_kmh = speed_knots * KNOTS_TO_KMH
    dist_km = speed_kmh * (dt_sec / 3600.0)
    
    # Components of main movement
    d_lat_km = dist_km * math.cos(math.radians(course_deg))
    d_lon_km = dist_km * math.sin(math.radians(course_deg))
    
    # Add noise: +/- 0.5 knots in both lat and lon directions independently
    # 0.5 knots to km/s
    noise_range_km_s = (NOISE_KNOTS * KNOTS_TO_KMH) / 3600.0
    noise_lat_km = random.uniform(-noise_range_km_s, noise_range_km_s) * dt_sec
    noise_lon_km = random.uniform(-noise_range_km_s, noise_range_km_s) * dt_sec
    
    final_d_lat_km = d_lat_km + noise_lat_km
    final_d_lon_km = d_lon_km + noise_lon_km
    
    new_lat = lat + (final_d_lat_km * LAT_DEG_PER_KM)
    new_lon = lon + (final_d_lon_km * LON_DEG_PER_KM)
    
    return new_lat, new_lon

class AdversaryBoat:
    def __init__(self, boat_id: int):
        self.id = boat_id
        # Start in top 10% of map (90% to 100% of height)
        range_lat = MAX_LAT - MIN_LAT
        start_lat_min = MIN_LAT + 0.9 * range_lat
        
        self.lat = random.uniform(start_lat_min, MAX_LAT)
        self.lon = random.uniform(MIN_LON, MAX_LON)
        
        self.speed = ADVERSARY_SPEED_KNOTS
        self.course = 180.0 # South
        
    def step_sim(self, dt: float):
        self.lat, self.lon = move_point(self.lat, self.lon, self.speed, self.course, dt)

    def to_dict(self, current_time: datetime) -> Dict:
        return {
            "timestamp": current_time.isoformat() + "Z",
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
        # Start in bottom 10% of map (0% to 10% of height)
        range_lat = MAX_LAT - MIN_LAT
        start_lat_max = MIN_LAT + 0.1 * range_lat
        
        self.lat = random.uniform(MIN_LAT, start_lat_max)
        self.lon = random.uniform(MIN_LON, MAX_LON)
        
        self.speed = 0.0
        self.course = random.uniform(0, 360) # Random heading
        
        self.target_boat = None
        
    def step_sim(self, dt: float):
        if not self.target_boat:
            return

        # 1. Determine tactical goal: Intercept
        target_lat = self.target_boat.lat
        target_lon = self.target_boat.lon
        
        # Calculate bearing to target
        desired_heading = calculate_bearing(self.lat, self.lon, target_lat, target_lon)
        
        # 2. Turn towards target
        heading_diff = (desired_heading - self.course + 180) % 360 - 180
        max_turn = FRIENDLY_TURN_RATE_DEG_PER_SEC * dt
        
        # Clamp turn
        turn = max(-max_turn, min(max_turn, heading_diff))
        self.course = (self.course + turn) % 360
        
        # 3. Set Speed
        # If we are facing strictly away or need to turn a lot, maybe slow down? 
        # Requirement says "can change velocity instantly". 
        # "natural interception" usually implies full speed until close.
        # Let's just go full speed for now to intercept.
        self.speed = FRIENDLY_MAX_SPEED_KNOTS
        
        # Stop if very close? "intercepting (hovering near)"
        dist_km = calculate_distance_km(self.lat, self.lon, target_lat, target_lon)
        if dist_km < 0.2: # Closer than 200m
             # Match speed to hover/follow? Or just circle?
             # Simplest: Match target speed + a bit of swarm noise
             self.speed = self.target_boat.speed
             self.course = self.target_boat.course # Align heading

        # 4. Move
        self.lat, self.lon = move_point(self.lat, self.lon, self.speed, self.course, dt)

    def to_dict(self, current_time: datetime) -> Dict:
        target_id = f"ADV-{self.target_boat.id}" if self.target_boat else None
        return {
            "timestamp": current_time.isoformat() + "Z",
            "boat_id": f"USV-{self.id}",
            "type": "friendly",
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "speed_knots": round(self.speed, 1),
            "course_deg": round(self.course, 1),
            "target_id": target_id
        }

def run_simulation():
    print(f"Generating simulation for {SIMULATION_DURATION_SEC} seconds...")
    
    # 1. Init boats
    adversaries = [AdversaryBoat(i) for i in range(1, NUM_ADVERSARY_BOATS + 1)]
    usvs = [USV(i) for i in range(1, NUM_FRIENDLY_BOATS + 1)]
    
    # 2. Assign Targets
    # "The first adversary is assigned the 5 closest USVs."
    # We need to calculate distances from Adversary 1 to all USVs to find the closest 5.
    if len(adversaries) >= 1:
        adv1 = adversaries[0]
        # Calculate all distances
        usv_dists = []
        for u in usvs:
            d = calculate_distance_km(adv1.lat, adv1.lon, u.lat, u.lon)
            usv_dists.append((d, u))
        
        # Sort by distance
        usv_dists.sort(key=lambda x: x[0])
        
        # Assign closest 5 to Adv 1
        group1 = [pair[1] for pair in usv_dists[:5]]
        # Assign rest to Adv 2 (if exists, else Adv 1 too?)
        # Requirement: "The remaining 5 USVs have the second adversary as their target."
        group2 = [pair[1] for pair in usv_dists[5:]]
        
        for u in group1:
            u.target_boat = adv1
            
        if len(adversaries) > 1:
            adv2 = adversaries[1]
            for u in group2:
                u.target_boat = adv2
        else:
             # Fallback if only 1 adversary
             for u in group2:
                 u.target_boat = adv1

    # 3. Sim Loop
    virtual_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    with open(LOG_FILE, "w") as f:
        # Initial State
        for boat in adversaries + usvs:
            f.write(json.dumps(boat.to_dict(virtual_time)) + "\n")

        for _ in range(int(SIMULATION_DURATION_SEC / SIMULATION_STEP_SEC)):
            virtual_time += timedelta(seconds=SIMULATION_STEP_SEC)
            
            # Step Adversaries
            for adv in adversaries:
                adv.step_sim(SIMULATION_STEP_SEC)
                
            # Step USVs
            for usv in usvs:
                usv.step_sim(SIMULATION_STEP_SEC)
            
            # Log
            for boat in adversaries + usvs:
                f.write(json.dumps(boat.to_dict(virtual_time)) + "\n")
                
    print(f"Simulation saved to {LOG_FILE}")

if __name__ == "__main__":
    run_simulation()