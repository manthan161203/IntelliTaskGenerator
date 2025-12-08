from app.config.config import settings
from app.utils.logger import logger
from google import genai
import pathlib
from app.utils.file_utils import upload_files_to_genai
from app.utils.ai_utils import log_token_usage


class GenAIClient:
    def __init__(self):
        # Initialize with API key directly (required by google-genai)
        self.client = genai.Client(api_key=settings.GOOGLE_GENAI_API_KEY)
        self.model_name = "gemini-2.5-flash-lite"  # or whichever model you prefer

    async def get_task_breakdown(self, file_paths: list[str], prompt: str) -> dict:
        """
        Sends the prompt to Google GenAI along with up to 5 file uploads and returns both text output and token usage.
        """
        logger.info("Uploading files to Google GenAI File API")

        # --- Upload files ---
        uploaded_files = upload_files_to_genai(self.client, file_paths)

        logger.info(f"Uploaded {len(uploaded_files)} files")

        # --- Generate response ---
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=uploaded_files + [prompt]  # Combine files and prompt
        )

        usage = {
            "input_tokens": response.usage_metadata.prompt_token_count,
            "output_tokens": response.usage_metadata.candidates_token_count,
            "total_tokens": response.usage_metadata.total_token_count,
        }

        logger.info(f"Token usage: {usage}")

        return {
            "text": response.text,
            "usage": usage
        }