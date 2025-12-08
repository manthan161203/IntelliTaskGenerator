import json
from fastapi import HTTPException
from app.utils.logger import logger


def clean_ai_response(text: str) -> str:
    """
    Removes markdown fences and extracts JSON.
    """
    try:
        text = text.strip()

        if text.startswith("```"):
            text = text.split("```")[1].strip()
        if text.startswith("json"):
            text = text.replace("json", "", 1).strip()

        logger.info("AI response cleaned successfully.")
        return text
    except Exception as e:
        logger.error(f"Failed to clean AI response: {e}")
        raise HTTPException(status_code=500, detail="Error cleaning AI response.")


def parse_ai_json(text: str) -> dict:
    try:
        cleaned = clean_ai_response(text)
        data = json.loads(cleaned)

        if not isinstance(data, dict):
            logger.error("AI returned JSON, but it is not an object.")
            raise HTTPException(status_code=500, detail="AI returned JSON, but it must be an object.")

        logger.info("AI JSON parsed successfully.")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding failed: {e}")
        raise HTTPException(status_code=500, detail="AI returned invalid JSON output.")
    except Exception as e:
        logger.error(f"Unexpected error while parsing AI JSON: {e}")
        raise HTTPException(status_code=500, detail="Error parsing AI JSON.")


def log_token_usage(usage_metadata) -> dict:
    """
    Extracts and logs token usage from the response metadata.
    """
    usage = {
        "input_tokens": usage_metadata.prompt_token_count,
        "output_tokens": usage_metadata.candidates_token_count,
        "total_tokens": usage_metadata.total_token_count,
    }

    logger.info(f"Token usage: {usage}")
    return usage
