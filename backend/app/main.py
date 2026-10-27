"""FastAPI の入口。各担当のルーターは、create_app() の中で登録する。"""

from fastapi import FastAPI

from app.api import billing, dev
from app.api.admin import billing as admin_billing
from app.api.admin import disclosure as admin_disclosure
from app.api.admin import visits as admin_visits
from app.api.family import contact_book as family_contact_book
from app.api.family import inquiry as family_inquiry
from app.api.family import notifications as family_notifications
from app.api.family import requests as family_requests
from app.api.family import visits as family_visits
from app.api.staff import contact_book as staff_contact_book
from app.api.staff import memos as staff_memos
from app.api.staff import messages as staff_messages
from app.api.staff import records as staff_records
from app.api.staff import requests as staff_requests
from app.api.staff import residents as staff_residents
from app.api.staff import visits as staff_visits
from app.auth import routes as auth_routes
from app.auth.csrf import RequireFetchHeaderMiddleware
from app.config import get_settings
from app.errors import register_error_handlers
from app.logging import configure_logging


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

    register_error_handlers(app)
    app.add_middleware(RequireFetchHeaderMiddleware)

    app.include_router(auth_routes.router)
    app.include_router(billing.router)
    app.include_router(admin_billing.router)
    app.include_router(admin_disclosure.router)
    app.include_router(admin_visits.router)
    app.include_router(family_visits.router)
    app.include_router(family_requests.router)
    app.include_router(family_contact_book.router)
    app.include_router(family_notifications.router)
    app.include_router(family_inquiry.router)
    app.include_router(staff_contact_book.router)
    app.include_router(staff_memos.router)
    app.include_router(staff_messages.router)
    app.include_router(staff_records.router)
    app.include_router(staff_requests.router)
    app.include_router(staff_residents.router)
    app.include_router(staff_visits.router)
    # 開発用のユーザー切り替えは、開発環境だけで登録する（本番では 404。research.md R-02）
    if settings.is_development:
        app.include_router(dev.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        """起動確認用。フロントの中継（/api）が届いているかの確認にも使う。"""
        return {"status": "ok"}

    return app


configure_logging()
app = create_app()
