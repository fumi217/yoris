"""開示設定の API（spec 001 の 001-T039。contracts の `GET`・`PUT /api/admin/disclosure`）。

記録項目（食事・機嫌・眠り）と「知りたいこと」のテーマごとに、家族に見せるかを決める（FR-009）。
変えられるのは生活相談員・施設長だけ（事務員・介護職員・リーダーは 403）。
設定の行がない項目・テーマは「見せない」として返す（家族に出す共通の関数と同じ。services/disclosure.py）。
保存したら、commit のあとに開示設定のキャッシュを必ず消す
（次に家族が開いたときに反映する。FR-012・R-12）。
変更履歴（FR-011・001-T041）は作り込みで足す。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import Staff
from app.models.disclosure import DisclosureSetting, Theme
from app.models.records import ITEMS
from app.services.disclosure import clear_disclosure_cache

router = APIRouter(prefix="/api/admin", tags=["admin"])

DISCLOSURE_EDITORS = require_staff(("counselor", "director"))


class ItemSetting(BaseModel):
    code: str  # "meal" / "mood" / "sleep"
    visible: bool


class ThemeSetting(BaseModel):
    code: str  # 例："theme.daily_life"
    emoji: str
    visible: bool


class DisclosureResponse(BaseModel):
    items: list[ItemSetting]
    themes: list[ThemeSetting]


class DisclosureUpdate(BaseModel):
    # 変えるものだけを送ればよい（送らなかったものはそのまま）。決まりの外の項目は受け付けない
    model_config = ConfigDict(extra="forbid")

    # "yes" や 1 を真偽に読み替えない
    items: dict[str, StrictBool] = {}
    themes: dict[str, StrictBool] = {}


def _facility_id(session: Session, user: CurrentUser) -> int:
    return session.scalars(select(Staff.facility_id).where(Staff.id == user.staff_id)).one()


def _response(session: Session, facility_id: int) -> DisclosureResponse:
    visible = {
        (setting.target_type, setting.target_code): setting.visible
        for setting in session.scalars(
            select(DisclosureSetting).where(DisclosureSetting.facility_id == facility_id)
        )
    }
    themes = session.scalars(select(Theme).order_by(Theme.sort_order, Theme.id))
    return DisclosureResponse(
        items=[
            ItemSetting(code=item, visible=visible.get(("item", item), False)) for item in ITEMS
        ],
        themes=[
            ThemeSetting(
                code=theme.code,
                emoji=theme.emoji,
                visible=visible.get(("theme", theme.code), False),
            )
            for theme in themes
        ],
    )


@router.get("/disclosure")
def get_disclosure(
    user: Annotated[CurrentUser, Depends(DISCLOSURE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> DisclosureResponse:
    """記録項目とテーマの、見せる／見せない（並びは記録の項目の順・テーマの順）。"""
    return _response(session, _facility_id(session, user))


@router.put("/disclosure")
def put_disclosure(
    body: DisclosureUpdate,
    user: Annotated[CurrentUser, Depends(DISCLOSURE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> DisclosureResponse:
    """見せる／見せないを変える。知らない項目・テーマのコードがあれば 422（何も変えない）。"""
    theme_codes = set(session.scalars(select(Theme.code)))
    if not set(body.items) <= set(ITEMS) or not set(body.themes) <= theme_codes:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    facility_id = _facility_id(session, user)
    existing = {
        (setting.target_type, setting.target_code): setting
        for setting in session.scalars(
            select(DisclosureSetting).where(DisclosureSetting.facility_id == facility_id)
        )
    }
    changes = [("item", code, visible) for code, visible in body.items.items()] + [
        ("theme", code, visible) for code, visible in body.themes.items()
    ]
    for target_type, code, visible in changes:
        setting = existing.get((target_type, code))
        if setting is None:
            session.add(
                DisclosureSetting(
                    facility_id=facility_id,
                    target_type=target_type,
                    target_code=code,
                    visible=visible,
                    updated_by=user.staff_id,
                )
            )
        elif setting.visible != visible:
            setting.visible = visible
            setting.updated_by = user.staff_id
            setting.updated_at = func.now()
    session.commit()
    # commit の前に消すと、まだ保存されていない古い設定がまたキャッシュに入る
    clear_disclosure_cache(facility_id)
    return _response(session, facility_id)
