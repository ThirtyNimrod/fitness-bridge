import json

def format_set(set_data: dict) -> str:
    """Formats an exercise set dictionary into a human-readable string."""
    if set_data.get("type") == "duration":
        return f"Set {set_data.get('set_number')}: {set_data.get('duration_str')}"
    if set_data.get("type") == "weighted":
        tag = f" [{set_data['tag']}]" if set_data.get("tag") else ""
        return f"Set {set_data.get('set_number')}: {set_data.get('weight_kg')} kg x {set_data.get('reps')}{tag}"
    if set_data.get("type") == "bodyweight":
        tag = f" [{set_data['tag']}]" if set_data.get("tag") else ""
        return f"Set {set_data.get('set_number')}: {set_data.get('reps')} reps{tag}"
    return f"Set {set_data.get('set_number')}"

def parse_json_list(raw_value: str | None) -> list:
    """Safely parses a JSON string into a list."""
    if not raw_value:
        return []
    try:
        data = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []
