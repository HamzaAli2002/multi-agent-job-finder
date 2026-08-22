from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Explicitly load .env from the project root before validating settings
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings(BaseSettings):
    # Gemini Configuration — used ONLY for the single resume-analysis
    # call (Stage 2). Search (Stage 3) and scraping/extraction (Stage 4)
    # are pure Python and make zero LLM calls, per BRD's minimum-API-usage
    # requirement.
    GOOGLE_API_KEY: str
    MODEL_NAME: str = "gemini-3.6-flash"
    TEMPERATURE: float = 0.3

    # Search Configuration (Tavily — search API, not an LLM)
    TAVILY_API_KEY: str
    MAX_SEARCH_RESULTS: int = 5          # results per query
    MAX_QUERIES: int = 6                 # optimized queries generated per run
    SCRAPE_MAX_WORKERS: int = 6          # parallel page fetches

    # Paths (Dynamically derived using BASE_DIR)
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    SAMPLE_RESUME_DIR: Path = BASE_DIR / "data" / "sample_resumes"

    # Resume Formats
    SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx")

    # Modern Pydantic V2 Configuration
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        extra="ignore",
        env_file_encoding="utf-8",
    )


settings = Settings()
