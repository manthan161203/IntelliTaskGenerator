import json
import re
from fastapi import HTTPException
from app.utils.logger import logger


def _repair_truncated_json(text: str) -> str | None:
    """
    Attempt to repair truncated JSON by removing the last incomplete value
    and closing all unclosed brackets/braces.
    Returns the repaired JSON string, or None if repair fails.
    """
    text = text.strip()
    start = text.find('{')
    if start == -1:
        return None

    candidate = text[start:]

    # Strip trailing incomplete string/value: find the last complete key-value or array element
    # Remove partial trailing content after the last complete structure
    # Try progressively stripping from the end to find a repairable point
    for trim in range(min(500, len(candidate)), 0, -1):
        trimmed = candidate[:len(candidate) - trim]

        # Find a good cut point: last comma, closing brace/bracket, or colon+value
        last_good = max(
            trimmed.rfind(','),
            trimmed.rfind('}'),
            trimmed.rfind(']'),
        )
        if last_good == -1:
            continue

        fragment = trimmed[:last_good + 1]

        # Remove trailing comma before we close brackets
        fragment = fragment.rstrip().rstrip(',')

        # Count unclosed braces and brackets
        open_braces = fragment.count('{') - fragment.count('}')
        open_brackets = fragment.count('[') - fragment.count(']')

        if open_braces < 0 or open_brackets < 0:
            continue

        # Close unclosed structures
        repaired = fragment + (']' * open_brackets) + ('}' * open_braces)

        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            continue

    return None


def _extract_json_string(text: str) -> str:
    """
    Tries multiple strategies to extract a valid JSON string from AI output.
    Raises ValueError if none succeed.
    """
    text = text.strip()

    # Strategy 1: already valid JSON
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Strategy 2: markdown code fence  ```json ... ```  or  ``` ... ```
    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Strategy 3: extract outermost JSON object { ... }
    start = text.find('{')
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break

    # Strategy 4: extract outermost JSON array [ ... ]
    start = text.find('[')
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        break

    # Strategy 5: repair truncated JSON (output cut off by token limit)
    repaired = _repair_truncated_json(text)
    if repaired is not None:
        logger.warning("AI response was truncated. Repaired JSON by closing unclosed brackets.")
        return repaired

    raise ValueError("No valid JSON found in AI response")


def clean_ai_response(text: str) -> str:
    """Extract JSON string from AI response (backward-compatible wrapper)."""
    try:
        result = _extract_json_string(text)
        logger.info("AI response cleaned successfully.")
        return result
    except ValueError as e:
        logger.error(f"Failed to extract JSON from AI response: {e}")
        raise HTTPException(status_code=500, detail="Error cleaning AI response.")


def parse_ai_json(text: str) -> dict:
    """
    Extract and parse a JSON object from raw AI response text.
    Tries multiple extraction strategies before giving up.
    """
    try:
        json_str = _extract_json_string(text)
    except ValueError as e:
        logger.error(f"Could not extract JSON from AI response: {e}\nRaw (first 500 chars): {text[:500]}")
        raise HTTPException(status_code=500, detail="AI returned invalid JSON output.")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding failed after extraction: {e}")
        raise HTTPException(status_code=500, detail="AI returned invalid JSON output.")

    if not isinstance(data, (dict, list)):
        logger.error("AI returned JSON but it is not an object or array.")
        raise HTTPException(status_code=500, detail="AI returned unexpected JSON type.")

    logger.info("AI JSON parsed successfully.")
    return data
