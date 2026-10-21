"""環境変数の読み込み。キー名の一覧はリポジトリ直下の env.example に書く。

設定は `get_settings()` で読む。呼んだときの環境変数で Settings を作るので、
テストで環境変数を変えてから呼び直すと、新しい値になる。
"""

import os
from dataclasses import dataclass, field


def _env(name: str, default: str | None = None):
    """呼ばれたときに環境変数を読む（dataclass の default_factory 用）。"""
    return lambda: os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # APP_ENV が未設定なら production として扱う（開発用でない側に倒す。research.md R-02）
    app_env: str = field(default_factory=_env("APP_ENV", "production"))
    database_url: str | None = field(default_factory=_env("DATABASE_URL"))
    redis_url: str | None = field(default_factory=_env("REDIS_URL"))
    # メールの送り方：smtp（開発の Mailpit）／resend（本番の Resend の API）。research.md R-09
    mail_transport: str = field(default_factory=_env("MAIL_TRANSPORT", "smtp"))
    smtp_host: str | None = field(default_factory=_env("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(os.environ.get("SMTP_PORT", "1025")))
    # 秘密の値は repr に出さない（設定をログに出したときに漏れないように）
    resend_api_key: str | None = field(default_factory=_env("RESEND_API_KEY"), repr=False)
    mail_from: str | None = field(default_factory=_env("MAIL_FROM"))
    app_base_url: str | None = field(default_factory=_env("APP_BASE_URL"))
    upload_dir: str | None = field(default_factory=_env("UPLOAD_DIR"))
    openrouter_model: str | None = field(default_factory=_env("OPENROUTER_MODEL"))
    # 決まった時刻の処理の API（POST /api/internal/jobs/run）の合言葉。空なら API を登録しない
    jobs_token: str | None = field(default_factory=_env("JOBS_TOKEN"), repr=False)

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


def get_settings() -> Settings:
    """今の環境変数で Settings を作って返す。"""
    return Settings()
