import os
import io
import uuid
import subprocess
from docx import Document
from PyPDF2 import PdfReader
from fastapi import UploadFile, HTTPException
from app.utils.logger import logger


ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def save_temp_file(uploaded: UploadFile) -> str:
    ext = os.path.splitext(uploaded.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Attempted to upload unsupported file type: {ext}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    temp_filename = f"{uuid.uuid4()}{ext}"
    temp_path = f"/tmp/{temp_filename}"

    try:
        with open(temp_path, "wb") as f:
            f.write(uploaded.file.read())
        logger.info(f"File saved successfully: {temp_path}")
    except Exception as e:
        logger.error(f"Failed to save file {uploaded.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Unable to save {uploaded.filename}")

    return temp_path


def convert_docx_to_pdf(docx_path: str) -> str:
    try:
        pdf_path = docx_path.replace(".docx", ".pdf")
        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                docx_path,
                "--outdir",
                os.path.dirname(docx_path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"DOCX successfully converted to PDF: {pdf_path}")
        return pdf_path

    except subprocess.CalledProcessError as e:
        logger.error(f"LibreOffice conversion failed for {docx_path}: {e.stderr.decode(errors='ignore')}")
        raise HTTPException(status_code=500, detail="Failed to convert DOCX to PDF.")

    except Exception as e:
        logger.exception(f"Unexpected error during DOCX → PDF conversion for {docx_path}: {e}")
        raise HTTPException(status_code=500, detail="Error converting DOCX to PDF.")


async def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        logger.info("Text successfully extracted from PDF")
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {e}")
        raise HTTPException(status_code=500, detail="Error extracting text from PDF.")


async def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join([para.text for para in doc.paragraphs])
        logger.info("Text successfully extracted from DOCX")
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from DOCX: {e}")
        raise HTTPException(status_code=500, detail="Error extracting text from DOCX.")


async def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode(errors="ignore")
        logger.info("Text successfully extracted from TXT file")
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from TXT file: {e}")
        raise HTTPException(status_code=500, detail="Error extracting text from TXT file.")


def upload_files_to_genai(client, file_paths: list[str], limit: int = 5) -> list:
    """
    Uploads files to Google GenAI File API.
    Limits the number of files uploaded to the specified limit.
    """
    import pathlib

    uploaded_files = []
    for file_path in file_paths[:limit]:
        file = pathlib.Path(file_path)
        uploaded_file = client.files.upload(file=file)
        uploaded_files.append(uploaded_file)

    logger.info(f"Uploaded {len(uploaded_files)} files")
    return uploaded_files
