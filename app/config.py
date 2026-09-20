from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    downstream_url: str = "http://localhost:8001"
    downstream_failure_rate: float = 0.20
    downstream_latency_mu: float = 5.7
    downstream_latency_sigma: float = 0.55
    db_path: str = "./data/dlq.sqlite3"
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.05
    max_backoff_seconds: float = 1.0
    jitter_ratio: float = 0.20
    circuit_failure_threshold: int = 3
    circuit_recovery_timeout_seconds: float = 5.0
    circuit_half_open_probes: int = 1
    http_timeout_seconds: float = 5.0
    dlq_backend: str = "sqlite"
    aws_dlq_table: str = ""
    aws_dlq_queue_url: str = ""
    aws_region: str = "ap-south-1"
    publish_cloudwatch_metrics: bool = False
    cloudwatch_namespace: str = "CollectionsChallenge"
    service_name: str = "collections-inference"
    provider_backend: str = "mock"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
