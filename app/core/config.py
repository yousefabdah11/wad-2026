from pydantic import BaseModel
from dotenv import load_dotenv
import os


load_dotenv()


class Settings(BaseModel):
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://wad_user:wad_password@localhost:5432/wad_app",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_ttl_seconds: int = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))
    refresh_token_ttl_days: int = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "30"))

    github_client_id: str = os.getenv("GITHUB_CLIENT_ID", "")
    github_client_secret: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    github_redirect_uri: str = os.getenv(
        "GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback"
    )

    llm_model_path: str = os.getenv("LLM_MODEL_PATH", "./model.gguf")
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "256"))
    # Larger default avoids KV / context init issues on many instruct GGUFs; override with LLM_N_CTX.
    llm_n_ctx: int = int(os.getenv("LLM_N_CTX", "4096"))
    llm_n_threads: int = int(os.getenv("LLM_N_THREADS", "4"))

    chat_cache_ttl_seconds: int = int(os.getenv("CHAT_CACHE_TTL_SECONDS", "120"))


settings = Settings()

