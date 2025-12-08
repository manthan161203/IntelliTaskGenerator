def calculate_total_estimate_hours(data: dict) -> float:
    """
    Calculates total estimated hours (sum of all task and sub-task 'originalEstimate' values).
    Returns float hours (e.g., 125.5 for 125h 30m).
    """
    def parse_estimate(estimate: str) -> float:
        if not estimate or not isinstance(estimate, str) or ":" not in estimate:
            return 0.0
        try:
            h, m = estimate.split(":")
            return int(h) + int(m) / 60
        except Exception:
            return 0.0

    total = 0.0
    tasks = data.get("tasks", [])
    for task in tasks:
        total += parse_estimate(task.get("originalEstimate"))
    return round(total, 2)
