"""開示設定の API（spec 001 の 001-T039。contracts の `GET`・`PUT /api/admin/disclosure`）。

記録項目（食事・機嫌・眠り）と「知りたいこと」のテーマごとに、家族に見せるかを決める（FR-009）。
変えられるのは生活相談員・施設長だけ（事務員・介護職員・リーダーは 403）。
設定の行がない項目・テーマは「見せない」として返す（家族に出す共通の関数と同じ。services/disclosure.py）。
保存したら、commit のあとに開示設定のキャッシュを必ず消す
（次に家族が開いたときに反映する。FR-012・R-12）。
変えたものは、変更履歴（disclosure_setting_histories）に残す（いつ・誰が・何を。FR-011・001-T041）。
`GET /api/admin/disclosure/history` で、新しい順に見られる。
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_staff
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import Staff
from app.models.disclosure import (
    DISCLOSURE_FEATURES,
    DISCLOSURE_ITEMS,
    DisclosureSetting,
    DisclosureSettingHistory,
    Theme,
)
from app.models.records import ITEMS
from app.services.disclosure import clear_disclosure_cache

router = APIRouter(prefix="/api/admin", tags=["admin"])

DISCLOSURE_EDITORS = require_staff(("counselor", "director"))

# 関係しそうな組み合わせ（FR-009・001-T042。data-model.md）：
# この記録の項目を「見せない」にしたのに、組のテーマを「見せる」のままにしていたら、注意書きを出す
# （職員の返事で、その項目のことが伝わることがあるため）。止めはしない（連動させない）
RELATED_PAIRS: tuple[tuple[str, str], ...] = (
    ("meal", "theme.meals"),
    ("mood", "theme.enjoying"),
    ("mood", "theme.daily_life"),
    ("sleep", "theme.daily_life"),
)


class ItemSetting(BaseModel):
    code: str  # "meal" / "mood" / "sleep"
    visible: bool


class ThemeSetting(BaseModel):
    code: str  # 例："theme.daily_life"
    emoji: str
    visible: bool


class FeatureSetting(BaseModel):
    code: str  # "album"
    visible: bool


class RelatedPair(BaseModel):
    item: str
    theme: str


class DisclosureResponse(BaseModel):
    items: list[ItemSetting]
    themes: list[ThemeSetting]
    # 機能（アルバム。spec 005 の 005-T022）
    features: list[FeatureSetting]
    # 関係しそうな組み合わせの一覧（画面は、まだ保存していない選び方でもここから注意書きを出す）
    related: list[RelatedPair]
    # 保存した設定で当てはまる組（記録の項目は見せないのに、テーマは見せる）
    warnings: list[RelatedPair]


class DisclosureUpdate(BaseModel):
    # 変えるものだけを送ればよい（送らなかったものはそのまま）。決まりの外の項目は受け付けない
    model_config = ConfigDict(extra="forbid")

    # "yes" や 1 を真偽に読み替えない
    items: dict[str, StrictBool] = {}
    themes: dict[str, StrictBool] = {}
    features: dict[str, StrictBool] = {}


def _facility_id(session: Session, user: CurrentUser) -> int:
    return session.scalars(select(Staff.facility_id).where(Staff.id == user.staff_id)).one()


def _response(session: Session, facility_id: int) -> DisclosureResponse:
    visible = {
        (setting.target_type, setting.target_code): setting.visible
        for setting in session.scalars(
            select(DisclosureSetting).where(DisclosureSetting.facility_id == facility_id)
        )
    }
    themes = list(session.scalars(select(Theme).order_by(Theme.sort_order, Theme.id)))
    theme_codes = {theme.code for theme in themes}
    related = [
        RelatedPair(item=item, theme=theme)
        for item, theme in RELATED_PAIRS
        if item in ITEMS and theme in theme_codes
    ]
    return DisclosureResponse(
        items=[
            ItemSetting(code=item, visible=visible.get(("item", item), False))
            for item in DISCLOSURE_ITEMS
        ],
        themes=[
            ThemeSetting(
                code=theme.code,
                emoji=theme.emoji,
                visible=visible.get(("theme", theme.code), False),
            )
            for theme in themes
        ],
        features=[
            FeatureSetting(code=feature, visible=visible.get(("feature", feature), False))
            for feature in DISCLOSURE_FEATURES
        ],
        related=related,
        warnings=[
            pair
            for pair in related
            if not visible.get(("item", pair.item), False)
            and visible.get(("theme", pair.theme), False)
        ],
    )


@router.get("/disclosure")
def get_disclosure(
    user: Annotated[CurrentUser, Depends(DISCLOSURE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> DisclosureResponse:
    """記録項目・テーマ・機能の、見せる／見せない（並びは記録の項目の順・テーマの順）。"""
    return _response(session, _facility_id(session, user))


@router.put("/disclosure")
def put_disclosure(
    body: DisclosureUpdate,
    user: Annotated[CurrentUser, Depends(DISCLOSURE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> DisclosureResponse:
    """見せる／見せないを変える。知らない項目・テーマのコードがあれば 422（何も変えない）。"""
    theme_codes = set(session.scalars(select(Theme.code)))
    if (
        not set(body.items) <= set(DISCLOSURE_ITEMS)
        or not set(body.themes) <= theme_codes
        or not set(body.features) <= set(DISCLOSURE_FEATURES)
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR)

    facility_id = _facility_id(session, user)
    existing = {
        (setting.target_type, setting.target_code): setting
        for setting in session.scalars(
            select(DisclosureSetting).where(DisclosureSetting.facility_id == facility_id)
        )
    }
    changes = (
        [("item", code, visible) for code, visible in body.items.items()]
        + [("theme", code, visible) for code, visible in body.themes.items()]
        + [("feature", code, visible) for code, visible in body.features.items()]
    )
    for target_type, code, visible in changes:
        setting = existing.get((target_type, code))
        # 行がないものは「見せない」として扱っているので、前の値は False（FR-011）
        old_visible = setting.visible if setting is not None else False
        if old_visible != visible:
            session.add(
                DisclosureSettingHistory(
                    facility_id=facility_id,
                    target_type=target_type,
                    target_code=code,
                    old_visible=old_visible,
                    new_visible=visible,
                    changed_by=user.staff_id,
                )
            )
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


# 履歴を一度に返す件数（新しいものから）
HISTORY_LIMIT = 100


class HistoryOut(BaseModel):
    id: int
    target_type: str  # "item" / "theme" / "feature"
    target_code: str
    old_visible: bool
    new_visible: bool
    changed_by_name: str
    changed_at: datetime


@router.get("/disclosure/history")
def get_disclosure_history(
    user: Annotated[CurrentUser, Depends(DISCLOSURE_EDITORS)],
    session: Annotated[Session, Depends(get_session)],
) -> list[HistoryOut]:
    """開示設定の変更履歴（いつ・誰が・何を）を、新しい順に返す（多くても HISTORY_LIMIT 件）。"""
    rows = session.execute(
        select(DisclosureSettingHistory, Staff.display_name)
        .join(Staff, Staff.id == DisclosureSettingHistory.changed_by)
        .where(DisclosureSettingHistory.facility_id == _facility_id(session, user))
        .order_by(DisclosureSettingHistory.changed_at.desc(), DisclosureSettingHistory.id.desc())
        .limit(HISTORY_LIMIT)
    )
    return [
        HistoryOut(
            id=history.id,
            target_type=history.target_type,
            target_code=history.target_code,
            old_visible=history.old_visible,
            new_visible=history.new_visible,
            changed_by_name=name,
            changed_at=history.changed_at,
        )
        for history, name in rows
    ]
