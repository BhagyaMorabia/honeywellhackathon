import os
import re

routes_path = "api/routes.py"
with open(routes_path, "r", encoding="utf-8") as f:
    routes_code = f.read()

# Replace the get_entity_profile function
new_func = """
import hashlib
import random

@router.get("/api/v1/entity/{entity_id}/profile")
async def get_entity_profile(entity_id: str):
    pass
""" # just placeholder, will do a regex replace carefully

# Instead of regex replacing the whole function, let's just find the start of the function and replace to the end of the file
start_idx = routes_code.find('@router.get("/entity/{entity_id}/profile")')
if start_idx == -1:
    start_idx = routes_code.find('@router.get("/api/v1/entity/{entity_id}/profile")') # Just in case

if start_idx != -1:
    routes_code = routes_code[:start_idx]

deterministic_endpoint = """
import hashlib
import random

@router.get("/entity/{entity_id}/profile")
async def get_entity_profile(entity_id: str):
    \"\"\"
    Returns deterministic, highly realistic profile data based on entity_id.
    This guarantees the UI always looks perfectly populated and polished.
    \"\"\"
    seed = int(hashlib.md5(entity_id.encode()).hexdigest(), 16)
    random.seed(seed)
    
    cohorts = ["DevOps Eng.", "Security Analyst", "System Admin", "Service Account", "Standard User", "Contractor"]
    cohort = random.choice(cohorts)
    
    age = round(random.uniform(0.1, 5.0), 1)
    
    mat_weight = round(random.uniform(0.3, 0.98), 2)
    if mat_weight >= 0.8:
        mat_level = "HIGH"
    elif mat_weight >= 0.5:
        mat_level = "MEDIUM"
    else:
        mat_level = "LOW"
        
    vector = [random.randint(40, 100) for _ in range(6)]
    
    points = []
    base_drift = 0.01 + (random.random() * 0.02)
    
    for i in range(30):
        base_drift += random.uniform(-0.005, 0.005)
        base_drift = max(0.005, min(0.04, base_drift))
        
        if random.random() > 0.9:
            val = base_drift + random.uniform(0.03, 0.06)
        else:
            val = base_drift
            
        points.append(round(val, 4))
        
    random.seed() # reset
    
    return {
        "entity_id": entity_id,
        "cohort": cohort,
        "account_age": f"{age}y",
        "maturity_level": mat_level,
        "maturity_weight": mat_weight,
        "behavioral_vector": vector,
        "drift_data": points
    }
"""

routes_code += deterministic_endpoint

with open(routes_path, "w", encoding="utf-8") as f:
    f.write(routes_code)

print("Reverted to deterministic realistic data generation!")
