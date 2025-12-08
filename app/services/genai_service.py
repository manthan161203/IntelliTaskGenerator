from app.utils.logger import logger

from app.prompts.prompt_taskonly import TASK_TEMPLATE
from app.services.genai_client import GenAIClient
from app.models import ScrumProject, KanbanProject, Project
import json, re
from app.utils.validation_utils import sanitize_priorities
from app.utils.other_utils import calculate_total_estimate_hours
from app.utils.ai_utils import clean_ai_response


class GenAIService:
    """
    Service for interacting with Google GenAI to analyze FRS and return structured tasks.
    Includes token usage tracking, sanitization, and auto-truncation for safe schema validation.
    """

    def __init__(self):
        self.client = GenAIClient()

    async def analyze_frs(self, file_paths: list[str], project_type: str, tech_stack: list[str]) -> dict:
        
        tech_stack_str = ", ".join(tech_stack) if tech_stack else "Not specified"

        # --- Choose prompt ---
        if project_type == "Scrum":
            prompt = TASK_TEMPLATE.replace("{tech_stack}", tech_stack_str)
            logger.info("Using Scrum prompt for GenAI service.")
        elif project_type == "Kanban":
            prompt = TASK_TEMPLATE.replace("{tech_stack}", tech_stack_str)
            logger.info("Using Kanban prompt for GenAI service.")
        else:
            logger.error(f"Invalid project_type: {project_type}")
            raise ValueError("project_type must be 'Scrum' or 'Kanban'.")

        # --- Call GenAI model and unpack token usage ---
        try:
            response_data = await self.client.get_task_breakdown(file_paths=file_paths, prompt=prompt)

            if isinstance(response_data, dict):
                response_text = response_data.get("text", "")
                usage = response_data.get("usage", {})
            else:
                response_text = response_data
                usage = {"input_tokens": None, "output_tokens": None, "total_tokens": None}

            logger.info(f"GenAI response received. Token usage: {usage}")
        except Exception as e:
            logger.error(f"GenAI service error: {e}")
            raise ValueError("Error while calling GenAI service.")

        # --- Clean and parse AI response ---
        cleaned = clean_ai_response(response_text)
        if not cleaned or not cleaned.startswith("{"):
            logger.error(f"GenAI returned invalid JSON: {response_text[:200]}...")
            raise ValueError("GenAI did not return valid JSON.")

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e} | Raw text: {response_text[:300]}")
            raise ValueError("GenAI returned invalid JSON format.")

        # --- Sanitize + Truncate fields safely ---
        # parsed = self._sanitize_release_and_sprint_names(parsed)
        # --- Sanitize priorities before schema validation ---
        parsed = sanitize_priorities(parsed)

        # --- Schema validation ---
        try:
            validated = Project(**parsed) if project_type == "Scrum" else Project(**parsed)
        except Exception as e:
            logger.error(f"Schema validation failed for {project_type}: {e}")
            raise ValueError(f"Invalid structure returned by GenAI for {project_type} project.")

        logger.info(f"{project_type} project validated successfully.")

        # --- Calculate total estimated hours ---
        total_estimate_hours = calculate_total_estimate_hours(validated.model_dump())

        # --- Return structured result with token usage ---
        result = validated.model_dump()
        result["_meta"] = {
            "token_usage": usage,
            "model": self.client.model_name,
            "project_type": project_type,
            "total_estimate_hours": total_estimate_hours
        }

        return result