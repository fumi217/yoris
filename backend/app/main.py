"""FastAPI の入口。各担当のルーターは、create_app() の中で登録する。"""

from fastapi import FastAPI

from app.config import get_settings


def create_app() -> FastAPI:
    """今の設定でアプリを作る。テストでは、環境変数を変えてから呼び直すと、その設定のアプリになる。"""
    settings = get_settings()

    # API の一覧（/docs・/openapi.json）は開発環境だけで公開する
    app = FastAPI(
        title="家族連絡アプリ API",
        docs_url="/docs" if settings.is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """起動確認用。フロントの中継（/api）が届いているかの確認にも使う。"""
        return {"status": "ok"}

    return app


app = create_app()
