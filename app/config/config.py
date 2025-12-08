import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """
    Application configuration loaded from environment variables.
    """
    GOOGLE_GENAI_API_KEY: str = os.getenv("GOOGLE_GENAI_API_KEY", "")

settings = Settings()
