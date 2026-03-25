MUSCLE_MAP = {
    "push up": "chest", "bench press": "chest", "incline bench": "chest", "chest press": "chest", "fly": "chest",
    "pull up": "back",  "lat pulldown": "back", "row": "back", "deadlift": "back",
    "squat": "legs",    "leg press": "legs", "lunge": "legs", "calf raise": "legs", "leg extension": "legs", "leg curl": "legs",
    "bicep curl": "biceps", "hammer curl": "biceps",
    "triceps extension": "triceps", "triceps pushdown": "triceps", "skullcrusher": "triceps",
    "shoulder press": "shoulders", "lateral raise": "shoulders", "front raise": "shoulders",
    "plank": "core", "crunch": "core", "sit up": "core",
    "stretching": "mobility", "yoga": "mobility"
}

def parse_set_line(line):
    """
    Parses an individual Hevy set line.
    Examples:
      "Set 1: 25 kg x 12"
      "Set 2: 15 kg x 5 [Drop]"
      "Set 3: 10 reps"
      "Set 1: 7min 55s"
    """
    if not line.startswith("Set"): 
        return None
    
    parts = line.split(":", 1)
    if len(parts) < 2: 
        return None
    
    set_number_str = parts[0].replace("Set", "").strip()
    try:
        set_number = int(set_number_str)
    except ValueError:
        return None
        
    remainder = parts[1].strip()
    
    # 1. Check for duration
    # "min" or "s" usually indicates time (unless it's just 'reps' with an 's')
    if "min" in remainder or ("s" in remainder and "reps" not in remainder):
        return {"type": "duration", "set_number": set_number, "duration_str": remainder}
        
    # 2. Check for weighted sets
    elif "kg x" in remainder:
        tag = None
        if "[" in remainder and "]" in remainder:
            tag = remainder.split("[")[1].split("]")[0].strip()
            remainder = remainder.split("[")[0].strip()
            
        weight_str, reps_str = remainder.split("kg x")
        try:
            return {
                "type": "weighted",
                "set_number": set_number,
                "weight_kg": float(weight_str.strip()),
                "reps": int(reps_str.strip()),
                "tag": tag
            }
        except ValueError:
            return None
            
    # 3. Check for bodyweight sets
    elif "reps" in remainder:
        tag = None
        if "[" in remainder and "]" in remainder:
            tag = remainder.split("[")[1].split("]")[0].strip()
            remainder = remainder.split("[")[0].strip()
            
        reps_str = remainder.replace("reps", "").strip()
        try:
            return {
                "type": "bodyweight", 
                "set_number": set_number, 
                "reps": int(reps_str),
                "tag": tag
            }
        except ValueError:
            return None
            
    return None


def calculate_exercise_volume(sets):
    total = 0
    for s in sets:
        if s.get("type") == "weighted":
            total += s.get("weight_kg", 0) * s.get("reps", 0)
    return round(total, 2)


def tag_muscle_group(name):
    name_lower = name.lower()
    for keyword, group in MUSCLE_MAP.items():
        if keyword in name_lower:
            return group
    return "other"


def parse_description(text):
    """
    Converts a Hevy plaintext description into structured exercise data.
    """
    if not text: 
        return []
    
    # Hevy separates exercises by double newline
    exercise_blocks = text.strip().split("\n\n")
    exercises = []
    
    for block in exercise_blocks:
        lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
        if not lines: 
            continue
        
        exercise_name = lines[0]
        sets = []
        
        for line in lines[1:]:
            if line.startswith("Set"):
                parsed_set = parse_set_line(line)
                if parsed_set: 
                    sets.append(parsed_set)
                    
        muscle_group = tag_muscle_group(exercise_name)
        volume = calculate_exercise_volume(sets)
        
        exercises.append({
            "name": exercise_name,
            "muscle_group": muscle_group,
            "sets": sets,
            "total_volume_kg": volume,
            "set_count": len(sets)
        })
        
    return exercises
