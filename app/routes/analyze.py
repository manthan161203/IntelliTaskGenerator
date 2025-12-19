from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.services.genai_service import GenAIService
from app.utils.logger import logger
import json
from typing import Any, Dict, List, Optional

# Import new utils
from app.utils.file_utils import save_temp_file, convert_docx_to_pdf
from app.utils.validation_utils import (
    validate_project_type,
    validate_json_string,
    parse_tech_stack,
)
from app.utils.ai_utils import parse_ai_json

import os
import json

router = APIRouter()
genai_service = GenAIService()

@router.post("/analyze/")
async def analyze(
    files: list[UploadFile] = File(None, description="Upload up to 5 files (PDF, DOCX)"),
    project_type: str = Form(..., description="Project methodology: Scrum or Kanban"),
    tech_stack: str = Form(None, description="Comma-separated list of technologies used in the project"),
):
    logger.info(f"Analyze request: project_type={project_type}")

    if not files:
        raise HTTPException(status_code=400, detail="You must upload at least one file.")
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 files allowed.")

    validate_project_type(project_type)

    temp_files = []

    for uploaded in files:
        temp_path = save_temp_file(uploaded)

        if temp_path.endswith(".docx"):
            pdf_path = convert_docx_to_pdf(temp_path)
            temp_files.append(pdf_path)
        else:
            temp_files.append(temp_path)

    result = await genai_service.analyze_frs(
        temp_files,
        project_type=project_type,
        tech_stack=tech_stack
    )

    return JSONResponse(content=result)

def validate_and_preserve_ids(previous_data: Dict[str, Any], updated_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    ID Strategy:
    - CREATE: id = null
    - UPDATE: preserve existing id
    - DELETE: omit from response
    """
    
    existing_map = {}
    
    # Build map from previous data
    for task in previous_data.get("tasks", []):
        # Use summary as unique key (combine with issueType for better uniqueness)
        key = (task.get("issueType", ""), task.get("summary", ""))
        existing_map[key] = task.get("id")
        
        # Map subtasks with their parent summary for context
        for subtask in task.get("subTasks", []):
            sub_key = ("subtask", task.get("summary", ""), subtask.get("summary", ""))
            existing_map[sub_key] = subtask.get("id")
    
    # Apply IDs to updated data
    for task in updated_data.get("tasks", []):
        key = (task.get("issueType", ""), task.get("summary", ""))
        
        if key in existing_map:
            task["id"] = existing_map[key]
            logger.info(f"Preserved ID {existing_map[key]} for task: {task.get('summary')}")
        else:
            task["id"] = None
            logger.info(f"New task created (id=null): {task.get('summary')}")
        
        # Handle subtasks
        for subtask in task.get("subTasks", []):
            sub_key = ("subtask", task.get("summary", ""), subtask.get("summary", ""))
            
            if sub_key in existing_map:
                subtask["id"] = existing_map[sub_key]
                logger.info(f"Preserved ID {existing_map[sub_key]} for subtask: {subtask.get('summary')}")
            else:
                subtask["id"] = None
                logger.info(f"New subtask created (id=null): {subtask.get('summary')}")
    
    return updated_data


@router.post("/edit-json/")
async def edit_json(
    files: Optional[List[UploadFile]] = File(None, description="Upload up to 5 files (PDF, DOCX)"),
    previous_json: str = Form(...),
    query: str = Form(...),
):
    from app.prompts.prompt_editor import EDIT_TASK_TEMPLATE

    # Validate and normalize previous_json (handles both array and dict formats)
    previous_data = validate_json_string(previous_json)

    temp_files = []
    if files:
        logger.info(f"Received {len(files)} files for edit-json")
        if len(files) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 files allowed.")

        for uploaded in files:
            temp_path = await save_temp_file(uploaded)
            logger.info(f"Saved temp file: {temp_path}")

            if temp_path.endswith(".docx"):
                pdf_path = await convert_docx_to_pdf(temp_path)
                temp_files.append(pdf_path)
                logger.info(f"Converted to PDF: {pdf_path}")
            else:
                temp_files.append(temp_path)
    else:
        logger.info("No files received for edit-json")

    prompt = EDIT_TASK_TEMPLATE \
        .replace("{previous_json}", json.dumps(previous_data, indent=2)) \
        .replace("{query}", query)

    response = await genai_service.client.get_task_breakdown(
        file_paths=temp_files,
        prompt=prompt
    )

    response_text = response.get("text", "") if isinstance(response, dict) else response
    ai_response = parse_ai_json(response_text)
    
    # Handle the wrapper structure from prompt_editor
    if isinstance(ai_response, dict) and "updated_json" in ai_response:
        inner_data = ai_response["updated_json"]
        
        # Normalize inner data if it comes as array
        if isinstance(inner_data, list):
            inner_data = {"tasks": inner_data}
            
        # Preserve IDs on the inner data
        inner_data = validate_and_preserve_ids(previous_data, inner_data)
        
        # Update the wrapper with processed data
        ai_response["updated_json"] = inner_data
        
        logger.info(f"Returning wrapper with {len(inner_data.get('tasks', []))} tasks")
        return ai_response

    # Fallback for legacy behavior (if AI returns just the project data)
    updated_json = ai_response
    
    # Normalize updated_json if it comes as array
    if isinstance(updated_json, list):
        updated_json = {"tasks": updated_json}

    # Preserve IDs from previous data
    updated_json = validate_and_preserve_ids(previous_data, updated_json)

    logger.info(f"Returning {len(updated_json.get('tasks', []))} tasks with preserved IDs")
    return updated_json
