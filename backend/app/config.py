import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./evoting.db"
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-only-change-me-" + os.urandom(8).hex())
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    BALLOT_ENC_KEY: str = os.environ.get("BALLOT_ENC_KEY", "")  # base64, 32 bytes -> if empty, generated on first run
    FACE_MATCH_THRESHOLD: float = 0.35  # normalized HOG-descriptor euclidean distance - lower is stricter
    FACE_DUP_THRESHOLD: float = 0.22    # stricter threshold to flag duplicate enrollment
    TOTP_ISSUER: str = "SecureEVote"

settings = Settings()
