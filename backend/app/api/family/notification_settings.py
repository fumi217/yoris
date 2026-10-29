"""家族の通知設定の API（spec 001 の 001-T064。contracts の「家族」・FR-023）。

- `GET /api/family/notification-settings`：通知設定と、送り先のメールアドレスを返す。
  設定の行がなければ、初めの設定（返事は通知・meal/mood/sleep・毎日）を返す（行は作らない）
- `PUT /api/family/notification-settings`：通知設定を変える。行がなければ作る。
  頻度が daily／weekly／none 以外、記録項目が meal／mood／sleep 以外なら 422（何も変えない）

家族アカウントは、ログイン中の家族から決める（id は受け取らない）。
送り先は、ログイン用と同じメールアドレス（施設からの招待で登録した家族のもの。FR-023）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, StrictBool
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_family
from app.db import get_session
from app.errors import AppError, ErrorCode
from app.models.core import FamilyAccount, User
from app.models.notifications import (
    DEFAULT_FREQUENCY,
    DEFAULT_NOTIFY_ITEMS,
    NOTIFICATION_FREQUENCIES,
    NotificationSetting,
)
from app.models.records import ITEMS

router = APIRouter(prefix="/api/family", tags=["family"])


class NotificationSettingsOut(BaseModel):
    notify_reply: bool
    notify_items: list[str]
    frequency: str
    email: str  # 送り先（ログイン用と同じ）。メールが届かないとき、画面で確かめられるように


class NotificationSettingsIn(BaseModel):
    # "yes" や 1 を真偽に読み替えない
    notify_reply: StrictBool
    notify_items: list[str]
    frequency: str


def _family_account_and_email(session: Session, user: CurrentUser) -> tuple[int, str]:
    row = session.execute(
        select(FamilyAccount.id, User.email)
        .join(User, User.id == FamilyAccount.user_id)
        .where(FamilyAccount.user_id == user.user_id)
    ).one_or_none()
    # 家族のログインには、必ず家族アカウントとメールがある（見つからないのは、あり得ない状態）
    if row is None or row.email is None:
        raise AppError(ErrorCode.FORBIDDEN)
    return row.id, row.email


def _out(setting: NotificationSetting | None, email: str) -> NotificationSettingsOut:
    if setting is None:
        return NotificationSettingsOut(
            notify_reply=True,
            notify_items=list(DEFAULT_NOTIFY_ITEMS),
            frequency=DEFAULT_FREQUENCY,
            email=email,
        )
    return NotificationSettingsOut(
        notify_reply=setting.notify_reply,
        notify_items=list(setting.notify_items),
        frequency=setting.frequency,
        email=email,
    )


@router.get("/notification-settings")
def get_notification_settings(
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> NotificationSettingsOut:
    family_account_id, email = _family_account_and_email(session, user)
    return _out(session.get(NotificationSetting, family_account_id), email)


@router.put("/notification-settings")
def put_notification_settings(
    body: NotificationSettingsIn,
    user: Annotated[CurrentUser, Depends(require_family)],
    session: Annotated[Session, Depends(get_session)],
) -> NotificationSettingsOut:
    if body.frequency not in NOTIFICATION_FREQUENCIES or not set(body.notify_items) <= set(ITEMS):
        raise AppError(ErrorCode.VALIDATION_ERROR)
    # 同じ項目が重なっても 1 つにまとめる（ITEMS の並びにそろえる）
    items = [item for item in ITEMS if item in body.notify_items]

    family_account_id, email = _family_account_and_email(session, user)
    values = {
        "notify_reply": body.notify_reply,
        "notify_items": items,
        "frequency": body.frequency,
    }
    # 「なければ作る・あれば更新する」を 1 回の命令で行う。同じ家族から、ほぼ同時に初めて
    # 保存されても、2 つ目が一意制約違反（500）にならない（FOR UPDATE は、行がまだないと効かない）
    session.execute(
        insert(NotificationSetting)
        .values(family_account_id=family_account_id, **values)
        .on_conflict_do_update(
            index_elements=[NotificationSetting.family_account_id],
            set_={**values, "updated_at": func.now()},
        )
    )
    # 命令で書いたので、読み直して返す（すでに読んだ値が、残っていないように）
    setting = session.scalars(
        select(NotificationSetting)
        .where(NotificationSetting.family_account_id == family_account_id)
        .execution_options(populate_existing=True)
    ).one()
    out = _out(setting, email)
    session.commit()
    return out
