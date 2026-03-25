from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.services.genai_service import GenAIService
from app.utils.logger import logger
import json
from typing import Any, Dict, List, Optional

from app.utils.file_utils import (
    save_temp_file,
    convert_docx_to_pdf,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt
)
from app.utils.validation_utils import (
    validate_project_type,
    validate_json_string,
)
from app.utils.ai_utils import parse_ai_json

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
    - If AI preserved the id field, trust it (verify it exists in originals)
    - Fallback: match by (issueType, summary) key
    - New tasks (no match): id = null
    - Deleted tasks: omitted from response
    """
    
    # Collect ALL valid IDs from previous data (tasks + subtasks)
    valid_ids = set()
    summary_map = {}  # (issueType, summary) -> id
    subtask_summary_map = {}  # (parent_summary, subtask_summary) -> id
    
    for task in previous_data.get("tasks", []):
        tid = task.get("id")
        if tid is not None:
            valid_ids.add(tid)
            key = (task.get("issueType", ""), task.get("summary", ""))
            summary_map[key] = tid
        
        for subtask in task.get("subTasks", []):
            sid = subtask.get("id")
            if sid is not None:
                valid_ids.add(sid)
                sub_key = (task.get("summary", ""), subtask.get("summary", ""))
                subtask_summary_map[sub_key] = sid
    
    # Apply IDs to updated data
    for task in updated_data.get("tasks", []):
        ai_id = task.get("id")
        
        # Strategy 1: AI preserved the ID and it's valid
        if ai_id is not None and ai_id in valid_ids:
            logger.info(f"AI preserved ID {ai_id} for task: {task.get('summary')}")
        else:
            # Strategy 2: Fallback to summary matching
            key = (task.get("issueType", ""), task.get("summary", ""))
            if key in summary_map:
                task["id"] = summary_map[key]
                logger.info(f"Summary-matched ID {summary_map[key]} for task: {task.get('summary')}")
            else:
                task["id"] = None
                logger.info(f"New task (id=null): {task.get('summary')}")
        
        # Handle subtasks
        for subtask in task.get("subTasks", []):
            sub_ai_id = subtask.get("id")
            
            if sub_ai_id is not None and sub_ai_id in valid_ids:
                logger.info(f"AI preserved ID {sub_ai_id} for subtask: {subtask.get('summary')}")
            else:
                sub_key = (task.get("summary", ""), subtask.get("summary", ""))
                if sub_key in subtask_summary_map:
                    subtask["id"] = subtask_summary_map[sub_key]
                    logger.info(f"Summary-matched ID {subtask_summary_map[sub_key]} for subtask: {subtask.get('summary')}")
                else:
                    subtask["id"] = None
                    logger.info(f"New subtask (id=null): {subtask.get('summary')}")
    
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

    extracted_text_content = ""
    if files:
        logger.info(f"Received {len(files)} files for edit-json")
        if len(files) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 files allowed.")

        for uploaded in files:
            try:
                content = await uploaded.read()
                logger.info(f"Read {len(content)} bytes from {uploaded.filename}")
                filename = uploaded.filename.lower()
                text = ""
                
                if filename.endswith(".pdf"):
                    text = await extract_text_from_pdf(content)
                elif filename.endswith(".docx"):
                    text = await extract_text_from_docx(content)
                elif filename.endswith(".txt"):
                    text = await extract_text_from_txt(content)
                
                if text:
                    extracted_text_content += f"\n\n--- Document Content ({uploaded.filename}) ---\n{text}\n"
                    logger.info(f"Extracted {len(text)} chars from {uploaded.filename}")
                else:
                    logger.warning(f"No text extracted or unsupported format for {uploaded.filename}")
            except Exception as e:
                logger.error(f"Failed to extract text from {uploaded.filename}: {e}")

    else:
        logger.info("No files received for edit-json")

    # Prepare document content string
    if extracted_text_content:
        document_content_str = extracted_text_content
    elif files:
        document_content_str = "Files were attached but no text could be extracted (possibly scanned PDFs or empty files)."
    else:
        document_content_str = "No document attached."

    prompt = EDIT_TASK_TEMPLATE \
        .replace("{previous_json}", json.dumps(previous_data, indent=2)) \
        .replace("{query}", query) \
        .replace("{document_content}", document_content_str)

    logger.info(f"Document content length: {len(document_content_str)}")
    logger.debug(f"Prompt end (last 500 chars):\n{prompt[-500:]}")

    response = await genai_service.client.get_task_breakdown(
        file_paths=[],  # No files to upload, text is in prompt
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
