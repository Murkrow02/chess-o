import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT.parent / ".env", ROOT / ".env"), extra="ignore")

    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "gemma4:e4b"
    llm_api_key: str = ""
    llm_timeout: float = 60.0
    # Sent as `reasoning_effort` to turn off "thinking" on hybrid models (Qwen3); empty to omit.
    llm_reasoning_effort: str = "none"

    embed_base_url: str = "http://localhost:11434"
    embed_model: str = "bge-m3"

    stockfish_path: str = "stockfish"
    engine_workers: int = 0
    engine_depth: int = 14
    engine_deep_depth: int = 20
    engine_multipv: int = 3
    engine_hash_mb: int = 64

    data_dir: Path = ROOT.parent / "data"
    knowledge_dir: Path = ROOT.parent / "knowledge"
    # Build the knowledge base in the background on first start (takes ~10 minutes on an iGPU).
    rag_auto_ingest: bool = True
    locale: str = "en"

    @property
    def workers(self) -> int:
        if self.engine_workers > 0:
            return self.engine_workers
        return max(1, (os.cpu_count() or 2) - 1)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "chess-o.sqlite"


settings = Settings()
