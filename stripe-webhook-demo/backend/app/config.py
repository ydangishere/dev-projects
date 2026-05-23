from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    stripe_webhook_secret: str = "whsec_test_secret"
    database_url: str = "sqlite:///./stripe_events.db"
    app_name: str = "Stripe Webhook Demo"


settings = Settings()
