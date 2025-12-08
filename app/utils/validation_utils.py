import json
from fastapi import HTTPException
from app.utils.logger import logger


def validate_project_type(project_type: str):
    try:
        if project_type not in ("Scrum", "Kanban"):
            logger.warning(f"Invalid project_type: {project_type}")
            raise HTTPException(status_code=400, detail="project_type must be 'Scrum' or 'Kanban'.")
        logger.info("Project type validated successfully.")
    except Exception as e:
        logger.error(f"Error validating project type: {e}")
        raise


def validate_json_string(json_str: str) -> dict:
    """
    Validates JSON string and normalizes it to a dictionary format.
    
    Handles both:
    - Direct dictionary: {"tasks": [...]}
    - Array format: [...] (converts to {"tasks": [...]})
    """
    try:
        data = json.loads(json_str)
        
        # If it's an array, wrap it in a dictionary
        if isinstance(data, list):
            logger.info("Detected array format, converting to dictionary with 'tasks' key")
            data = {"tasks": data}
        
        # Validate it's now a dictionary
        if not isinstance(data, dict):
            logger.warning("JSON must be an object (dictionary) or array.")
            raise HTTPException(status_code=400, detail="JSON must be an object (dictionary) or array.")
        
        logger.info("JSON string validated and normalized successfully.")
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON string: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON. Must be a valid JSON string.")
    except Exception as e:
        logger.error(f"Unexpected error validating JSON string: {e}")
        raise


def parse_tech_stack(tech_stack: str | None) -> list[str]:
    try:
        if not tech_stack:
            logger.info("No tech stack provided. Returning empty list.")
            return []

        if not isinstance(tech_stack, str):
            logger.warning("tech_stack must be a comma-separated string.")
            raise HTTPException(status_code=400, detail="tech_stack must be comma-separated string.")

        parsed_stack = [t.strip() for t in tech_stack.split(",") if t.strip()]
        logger.info("Tech stack parsed successfully.")
        return parsed_stack
    except Exception as e:
        logger.error(f"Error parsing tech stack: {e}")
        raise


def sanitize_priorities(data: dict) -> dict:
    """
    Ensures all task and subtask priorities are strictly one of: None, Low, Medium, High.
    Any other value is replaced with 'None'.
    """
    valid_values = {"None", "Low", "Medium", "High"}

    def normalize(value):
        if isinstance(value, str):
            v = value.strip().capitalize()
            return v if v in valid_values else "None"
        return "None"

    if "tasks" in data and isinstance(data["tasks"], list):
        for task in data["tasks"]:
            task["priority"] = normalize(task.get("priority"))
            if "subTasks" in task and isinstance(task["subTasks"], list):
                for sub in task["subTasks"]:
                    sub["priority"] = normalize(sub.get("priority"))

    return data


def sanitize_release_and_sprint_names(data: dict) -> dict:
    """
    Cleans and truncates release.version (max 50) and sprint.name (max 45).
    Only allows letters, numbers, spaces, dots, and hyphens.
    """
    import re

    # --- Handle Kanban releases ---
    if "releases" in data and isinstance(data["releases"], list):
        for release in data["releases"]:
            if "version" in release and isinstance(release["version"], str):
                original = release["version"]
                sanitized = re.sub(r"[^A-Za-z0-9 .-]", "", original).strip()
                if len(sanitized) > 50:
                    sanitized = sanitized[:50]
                    logger.warning(f"Truncated release version >50 chars: '{original}' -> '{sanitized}'")
                elif sanitized != original:
                    logger.warning(f"Sanitized release version: '{original}' -> '{sanitized}'")
                release["version"] = sanitized

    # --- Handle Scrum sprints ---
    if "sprints" in data and isinstance(data["sprints"], list):
        for sprint in data["sprints"]:
            if "name" in sprint and isinstance(sprint["name"], str):
                original = sprint["name"]
                sanitized = re.sub(r"[^A-Za-z0-9 .-]", "", original).strip()
                if len(sanitized) > 45:
                    sanitized = sanitized[:45]
                    logger.warning(f"Truncated sprint name >45 chars: '{original}' -> '{sanitized}'")
                elif sanitized != original:
                    logger.warning(f"Sanitized sprint name: '{original}' -> '{sanitized}'")
                sprint["name"] = sanitized

    return data
