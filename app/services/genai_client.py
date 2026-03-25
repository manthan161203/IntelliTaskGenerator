from app.config.config import settings
from app.utils.logger import logger
from google import genai
from app.utils.file_utils import upload_files_to_genai


class GenAIClient:
    def __init__(self):
        # Initialize with API key directly (required by google-genai)
        self.client = genai.Client(api_key=settings.GOOGLE_GENAI_API_KEY)
        self.model_name = "gemini-2.5-flash-lite"  # or whichever model you prefer

    async def get_task_breakdown(self, file_paths: list[str], prompt: str) -> dict:
        """
        Sends the prompt to Google GenAI along with up to 5 file uploads and returns both text output and token usage.
        """
        logger.info(f"GenAIClient.get_task_breakdown called with {len(file_paths)} files")
        logger.debug(f"File paths: {file_paths}")
        logger.info("Uploading files to Google GenAI File API")

        # --- Upload files ---
        uploaded_files = upload_files_to_genai(self.client, file_paths)

        logger.info(f"Uploaded {len(uploaded_files)} files to GenAI")
        for uf in uploaded_files:
            logger.debug(f"Uploaded file: {uf.name} (URI: {uf.uri})")

        logger.info(f"Sending prompt to model (Length: {len(prompt)} chars)")
        
        # --- Generate response (force JSON output to prevent markdown wrapping) ---
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=uploaded_files + [prompt],
            config={
                "response_mime_type": "application/json",
                "max_output_tokens": 65536,
            },
        )

        usage = {
            "input_tokens": response.usage_metadata.prompt_token_count,
            "output_tokens": response.usage_metadata.candidates_token_count,
            "total_tokens": response.usage_metadata.total_token_count,
        }

        logger.info(f"Token usage: {usage}")
        logger.info(f"RAW AI RESPONSE:\n{response.text}")

        # Warn if output may have been truncated
        if usage["output_tokens"] and usage["output_tokens"] >= 65000:
            logger.warning(f"AI response may be truncated (output_tokens={usage['output_tokens']}). Response may contain incomplete JSON.")

        return {
            "text": response.text,
            "usage": usage
        }