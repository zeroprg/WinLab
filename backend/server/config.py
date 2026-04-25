from __future__ import annotations

from typing import List
import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./chat.db"
    # Directory for SQLite volume files (dev: chat_data; Docker bind-mount often: /app/data).
    CHAT_DATA_DIR: str = "chat_data"
    # Accept raw env strings (JSON array or comma-separated) — parsed by `cors_list`.
    # Include common local dev origins (vite, nginx on :80, etc.). If you set
    # `CORS_ORIGINS` in your .env, that value will override this default.
    CORS_ORIGINS: str = '["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost", "http://127.0.0.1", "http://localhost:5173", "http://localhost:80"]'
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str = ""
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    OPENAI_REALTIME_MODEL: str = "gpt-4o-realtime-preview"
    OPENAI_REALTIME_VOICE: str = "marin"
    OPENAI_REALTIME_URL: str = "https://api.openai.com/v1/realtime/calls"
    # "ru" = append Russian-only directive to interview prompts (voice + text). "" = off.
    CHATBOT_DEFAULT_LOCALE: str = "ru"
    # Server VAD: longer silence = wait for user to finish; interrupt_response=false = assistant can finish speaking.
    # End-of-speech: silence (ms) before user's turn ends (VAD). Lower = faster replies; higher = wait longer.
    REALTIME_VAD_SILENCE_MS: int = 4000
    REALTIME_VAD_PREFIX_MS: int = 450
    REALTIME_VAD_THRESHOLD: float = 0.48
    REALTIME_INTERRUPT_RESPONSE: bool = False
    OPENAI_REALTIME_INSTRUCTIONS: str = (
        "You are an AI recruiter conducting a structured voice interview for a sales agent role. "
        "You MUST begin the conversation immediately by introducing yourself and the role.\n\n"
        "IMPORTANT: As soon as the call starts, say your greeting and first question WITHOUT waiting for the candidate to speak first.\n\n"
        "Follow these steps strictly in order:\n\n"
        "STEP 1 — INTRODUCTION (say this immediately when the call starts):\n"
        'Say: "Hello! Thank you for applying for the sales agent position. '
        "My name is Alex, and I'll be conducting your interview today. "
        "The role involves selling airline tickets and assisting customers. It is a permanent position. "
        'Let\'s start with a few questions about your background. Tell me, do you have any previous sales experience?"\n\n'
        "STEP 2 — EXPERIENCE:\n"
        "Listen to their answer about sales experience. If the answer is too short or vague, "
        'ask: "Could you please add more details about your sales experience?" '
        "Then move to the next question.\n\n"
        "STEP 3 — EDUCATION:\n"
        'Ask: "What is your education level?"\n\n'
        "STEP 4 — AVAILABILITY:\n"
        'Ask: "What is your availability, location, and current commitments?"\n\n'
        "STEP 5 — SALARY:\n"
        'Ask: "What are your salary expectations and approximate monthly expenses?"\n\n'
        "STEP 6 — ROLEPLAY:\n"
        "If the candidate has sales experience, do a short roleplay. "
        'Say: "Now let\'s do a brief role-play. I\'m an unhappy customer. '
        'Here is the situation: I want to buy a flight, but the price is too high." '
        "Then respond as the unhappy customer for up to 3 turns:\n"
        '- Turn 1: "Still too expensive. What else can you offer?"\n'
        '- Turn 2: "What information do you need from me?"\n'
        '- Turn 3: "Thanks, that will be all."\n'
        "If the candidate has no sales experience, skip the roleplay.\n\n"
        "STEP 7 — CLOSING:\n"
        'Say: "Thank you for your time. We will review your answers and contact you about the next steps. Have a great day!"\n'
        "Then stop responding.\n\n"
        "RULES:\n"
        "- Follow the steps in order, do not skip or reorder them.\n"
        "- Adapt your questions naturally based on the candidate's answers.\n"
        "- If an answer is incomplete, ask a clarifying follow-up before moving on.\n"
        "- Stay concise, professional, and empathetic.\n"
        "- After each candidate answer, internally rate 1-5 on: Solutions, Empathy, Information.\n"
        "- If the candidate speaks in a specific language, respond in that same language.\n"
        "- Do NOT reveal the scoring to the candidate."
    )
    # Secret key used for JWT signing (change for production!)
    SECRET_KEY: str = "change-me"
    JWT_EXPIRY_HOURS: int = 24
    SUPERADMIN_EMAIL: str = ""
    SUPERADMIN_PASSWORD: str = ""
    # Port the app expects (matches APP_PORT in .env)
    APP_PORT: int = 8000
    # Frontend vite API base (used by the client build). Present to avoid extra env errors.
    VITE_API_BASE: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Give priority to .env file over system environment variables
        extra="ignore"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """
        Custom source order: .env file values take priority over system env variables.
        Order: init_settings → dotenv_settings → env_settings
        """
        return (
            init_settings,
            dotenv_settings,  # .env file has priority over system environment
            env_settings,     # system environment variables
        )


settings = Settings()


    
def _cors_list_from(settings: Settings) -> List[str]:
    """Return CORS origins as a list, tolerant to JSON array or comma-separated string."""
    raw = settings.CORS_ORIGINS
    if not raw:
        return []
    raw = raw.strip()
    # If it looks like JSON, try to parse
    if raw.startswith("["):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
    # Otherwise split on commas
    return [item.strip() for item in raw.split(",") if item.strip()]

