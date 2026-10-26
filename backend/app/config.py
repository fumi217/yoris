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
    # AI：学校配布の OpenRouter のキー（ログに出さない）と、使うモデル。spec 004 の research.md R-01
    openrouter_api_key: str | None = field(default_factory=_env("OPENROUTER_API_KEY"), repr=False)
    openrouter_model: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_MODEL") or "openai/gpt-oss-120b"
    )
    # 様子のメモを整える・訳し戻すモデル。未設定なら OPENROUTER_MODEL。spec 007 の research.md R-01
    openrouter_rewrite_model: str = field(
        default_factory=lambda: (
            os.environ.get("OPENROUTER_REWRITE_MODEL")
            or os.environ.get("OPENROUTER_MODEL")
            or "openai/gpt-oss-120b"
        )
    )
    # 様子のメモの上限（spec 007 の research.md R-06・R-08）。環境変数では変えない
    # 1 人の職員が 1 人の入居者について 1 日に書ける件数（取り下げたものは数えない）
    memo_daily_limit: int = 3
    # 1 つのメモで「日本語にする」をやり直せる回数（care_memo_revisions の数）
    memo_rewrite_limit: int = 5
    # 問い合わせ AI の 1 日の回数の上限（家族ごと・施設全体）。spec 004 の research.md R-07
    inquiry_family_daily_limit: int = field(
        default_factory=lambda: int(os.environ.get("INQUIRY_FAMILY_DAILY_LIMIT") or "10")
    )
    inquiry_facility_daily_limit: int = field(
        default_factory=lambda: int(os.environ.get("INQUIRY_FACILITY_DAILY_LIMIT") or "300")
    )
    # 決まった時刻の処理の API（POST /api/internal/jobs/run）の合言葉。空なら API を登録しない
    jobs_token: str | None = field(default_factory=_env("JOBS_TOKEN"), repr=False)
    # 初期データの人（職員・家族）のパスワード。空なら入れない（ログインできないまま）。T022
    seed_password: str | None = field(default_factory=_env("SEED_PASSWORD"), repr=False)
    # 決済：Stripe のテスト環境の秘密の鍵と、Webhook の署名の秘密（ログに出さない）。spec 002
    stripe_secret_key: str | None = field(default_factory=_env("STRIPE_SECRET_KEY"), repr=False)
    stripe_webhook_secret: str | None = field(
        default_factory=_env("STRIPE_WEBHOOK_SECRET"), repr=False
    )

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


def get_settings() -> Settings:
    """今の環境変数で Settings を作って返す。"""
    return Settings()


# 決済のプラン（spec 002 の FR-022・R-01）。画面に出すプラン名と金額はここから出す。
# Stripe では、この lookup key の価格を探す（価格の ID は環境変数に書かない）
PLAN_NAME = "月額プラン"
PLAN_AMOUNT_JPY = 10000
PLAN_LOOKUP_KEY = "monthly_standard"
