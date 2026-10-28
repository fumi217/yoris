"""家族に出すときの共通の関数（spec 001 の 001-T038、research.md R-06・R-12）。

家族に出すもの（連絡帳・テーマのボタン・通知のまとめ・F の AI のツール）は、必ずここの関数を通す。
職員向け（記録の画面・見返し・E）は、非開示の項目も含めて直接読んでよい。

- 開示設定は Redis の `cache:disclosure:<施設ID>`（期限 5 分）から読む。
  開示設定を保存したら、必ず clear_disclosure_cache() でキャッシュを消す。
  Redis につながらないときは、DB から読む
  （Redis だけが止まっても、家族の画面が開けるように。PR #166 みさき）
- 開示設定に行がない項目・テーマは「見せない」として扱う（足し忘れで見えてしまわないように）。
  初期データでは、すべての項目・テーマを「見せる」で入れる（001-T037）
- 施設は 1 つなので、施設の id は入居者から決める（入居者がないときは、その 1 つの施設）
- 関数の中では commit しない。resident_id は、呼ぶ側がログイン中の家族から決める（FR-020）
"""

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.core import Facility, Resident, Staff
from app.models.disclosure import DisclosureSetting, ReplyTemplate, Theme
from app.models.records import ITEMS, MEAL_SLOTS, CareRecord
from app.models.replies import Reply
from app.models.requests import Request
from app.redis import get_redis

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 5 * 60  # 開発前MTG の決定事項（R-12）


def _cache_key(facility_id: int) -> str:
    return f"cache:disclosure:{facility_id}"


@dataclass(frozen=True)
class DisclosedRecord:
    id: int  # care_records.id（F の source_id に使える）
    date: date  # 連絡帳の日付（日本時間。眠りは記録した朝の日付）
    item: str  # "meal" / "mood" / "sleep"
    slot: str  # 食事は "breakfast" / "lunch" / "dinner" / "snack"、機嫌・眠りは "day"
    value: str  # app.models.records.VALUES のコード
    recorded_at: datetime  # 記録した時刻（タイムゾーン付き）
    recorded_by_name: str  # 記録した職員の表示名


@dataclass(frozen=True)
class DisclosedTheme:
    id: int
    code: str  # 辞書のキー（例："theme.daily_life"）
    emoji: str
    sort_order: int


@dataclass(frozen=True)
class DisclosedReply:
    id: int  # replies.id（既読にするとき・F の source_id に使える）
    request_id: int
    contact_book_date: date  # 返事が入る連絡帳の日付（返事をした日、日本時間）
    theme_code: str  # 辞書のキー（例："theme.daily_life"）
    theme_emoji: str
    template_codes: list[str]  # 選んだ定型文の辞書のキー（選んだ順）
    note: str | None  # 書き足した短い文。辞書を通さず、文字としてだけ出す
    replied_by_name: str  # 返事をした職員の表示名
    # 返事をした職員の職種のコード（辞書の occupation.*。#263）。空なら名前だけを出す
    replied_by_occupation: str | None
    replied_at: datetime
    edited: bool  # 当日中に直したか
    read: bool  # 家族が読んだか（家族で共有）


# --- 開示設定（キャッシュつき） ---


def _facility_id(session: Session, resident_id: int | None = None) -> int | None:
    if resident_id is not None:
        return session.scalar(select(Resident.facility_id).where(Resident.id == resident_id))
    return session.scalar(select(Facility.id).order_by(Facility.id).limit(1))


def _visible_targets(session: Session, facility_id: int) -> dict[str, set[str]]:
    """{"item": {見せる項目}, "theme": {見せるテーマの code}, "feature": {見せる機能}}。

    キャッシュになければ DB から読む。
    """
    try:
        cached = get_redis().get(_cache_key(facility_id))
    except Exception:
        # Redis につながらないときは、DB から読む
        # （開示設定は数行なので、毎回読んでも負担はほぼない）
        logger.warning("開示設定のキャッシュを読めませんでした facility_id=%s", facility_id)
        cached = None
    if cached is not None:
        return {target_type: set(codes) for target_type, codes in json.loads(cached).items()}

    rows = session.execute(
        select(DisclosureSetting.target_type, DisclosureSetting.target_code).where(
            DisclosureSetting.facility_id == facility_id, DisclosureSetting.visible.is_(True)
        )
    )
    visible: dict[str, set[str]] = {"item": set(), "theme": set(), "feature": set()}
    for target_type, target_code in rows:
        visible.setdefault(target_type, set()).add(target_code)
    try:
        get_redis().set(
            _cache_key(facility_id),
            json.dumps({target_type: sorted(codes) for target_type, codes in visible.items()}),
            ex=CACHE_TTL_SECONDS,
        )
    except Exception:
        logger.warning("開示設定のキャッシュに書けませんでした facility_id=%s", facility_id)
    return visible


def clear_disclosure_cache(facility_id: int) -> None:
    """開示設定を保存したら、必ず呼ぶ（古いキャッシュで非開示のものが見えないように。R-12）。

    保存の commit のあとに呼ぶ（前に消すと、まだ保存されていない古い設定がまたキャッシュに入る）。
    """
    try:
        get_redis().delete(_cache_key(facility_id))
    except Exception:
        # 消せなかったときは、期限（5 分）で消えるまで古い設定が残る。気づけるように記録する
        logger.error("開示設定のキャッシュを消せませんでした facility_id=%s", facility_id)


def is_item_disclosed(session: Session, code: str) -> bool:
    """その記録項目（"meal"・"memo" など）を家族に見せる設定か。知らないコードは False。"""
    facility_id = _facility_id(session)
    if facility_id is None:
        return False
    return code in _visible_targets(session, facility_id)["item"]


def is_feature_disclosed(session: Session, code: str) -> bool:
    """その機能（"album" など）を家族に見せる設定か。知らないコード・行がないものは False。

    spec 005 の 005-T003。アルバムの API・写真のファイル・家族のメニューが、これで判断する。
    """
    facility_id = _facility_id(session)
    if facility_id is None:
        return False
    return code in _visible_targets(session, facility_id).get("feature", set())


# --- 記録 ---


def get_disclosed_records(
    session: Session,
    resident_id: int,
    date_from: date,
    date_to: date,
    items: Iterable[str] | None = None,
) -> list[DisclosedRecord]:
    """開示している項目の、取り消していない記録を、日付 → 項目 → 区分の順に返す。

    items で項目を絞れる（非開示の項目を指定しても返らない）。未記録の欄は返さない。
    """
    facility_id = _facility_id(session, resident_id)
    if facility_id is None:
        return []
    allowed = _visible_targets(session, facility_id)["item"] & set(ITEMS)
    if items is not None:
        allowed &= set(items)
    if not allowed:
        return []

    item_order = case({item: n for n, item in enumerate(ITEMS)}, value=CareRecord.item)
    slot_order = case(
        {slot: n for n, slot in enumerate(MEAL_SLOTS)}, value=CareRecord.slot, else_=len(MEAL_SLOTS)
    )
    rows = session.execute(
        select(CareRecord, Staff.display_name)
        .join(Staff, Staff.id == CareRecord.recorded_by)
        .where(
            CareRecord.resident_id == resident_id,
            CareRecord.date >= date_from,
            CareRecord.date <= date_to,
            CareRecord.deleted_at.is_(None),
            CareRecord.item.in_(allowed),
        )
        .order_by(CareRecord.date, item_order, slot_order)
    )
    return [
        DisclosedRecord(
            id=record.id,
            date=record.date,
            item=record.item,
            slot=record.slot,
            value=record.value,
            recorded_at=record.recorded_at,
            recorded_by_name=staff_name,
        )
        for record, staff_name in rows
    ]


# --- テーマ ---


def _to_theme(theme: Theme) -> DisclosedTheme:
    return DisclosedTheme(
        id=theme.id, code=theme.code, emoji=theme.emoji, sort_order=theme.sort_order
    )


def get_disclosed_themes(session: Session) -> list[DisclosedTheme]:
    """開示しているテーマを、sort_order の順に返す（「知りたいこと」を選ぶ画面で使う）。"""
    facility_id = _facility_id(session)
    if facility_id is None:
        return []
    visible = _visible_targets(session, facility_id)["theme"]
    if not visible:
        return []
    themes = session.scalars(
        select(Theme).where(Theme.code.in_(visible)).order_by(Theme.sort_order, Theme.id)
    )
    return [_to_theme(theme) for theme in themes]


def get_requested_themes(session: Session, theme_ids: Iterable[int]) -> list[DisclosedTheme]:
    """家族がすでに送ったリクエストのテーマを、開示の設定に関わらず返す（issue #111 さとこ）。

    送ったあとにテーマが非開示になっても、送ったリクエストは残る（spec 001 の US2）ので、
    「送ったリクエスト」の一覧にテーマ名を出すときだけ使う。テーマを選ぶ画面では使わない。
    """
    ids = set(theme_ids)
    if not ids:
        return []
    themes = session.scalars(select(Theme).where(Theme.id.in_(ids)).order_by(Theme.sort_order))
    return [_to_theme(theme) for theme in themes]


# --- 返事（001-T054） ---


def get_active_replies(
    session: Session, resident_id: int, date_from: date, date_to: date
) -> list[DisclosedReply]:
    """その入居者への職員の返事を、返事の時刻の順に返す。

    連絡帳の日付（contact_book_date）が date_from〜date_to のものだけ。

    返事は取り消さないので、保存されたものはすべて有効（R-06）。
    """
    rows = session.execute(
        select(
            Reply,
            Theme.code,
            Theme.emoji,
            Staff.display_name,
            Staff.occupation,
        )
        .join(Request, Request.id == Reply.request_id)
        .join(Theme, Theme.id == Request.theme_id)
        .join(Staff, Staff.id == Reply.replied_by)
        .where(
            Request.resident_id == resident_id,
            Reply.contact_book_date >= date_from,
            Reply.contact_book_date <= date_to,
        )
        .order_by(Reply.replied_at, Reply.id)
    ).all()
    template_ids = {template_id for reply, *_ in rows for template_id in reply.template_ids}
    codes = (
        dict(
            session.execute(
                select(ReplyTemplate.id, ReplyTemplate.code).where(
                    ReplyTemplate.id.in_(template_ids)
                )
            ).all()
        )
        if template_ids
        else {}
    )
    return [
        DisclosedReply(
            id=reply.id,
            request_id=reply.request_id,
            contact_book_date=reply.contact_book_date,
            theme_code=theme_code,
            theme_emoji=theme_emoji,
            template_codes=[codes[t] for t in reply.template_ids if t in codes],
            note=reply.note,
            replied_by_name=staff_name,
            replied_by_occupation=occupation,
            replied_at=reply.replied_at,
            edited=reply.edited_at is not None,
            read=reply.read_at is not None,
        )
        for reply, theme_code, theme_emoji, staff_name, occupation in rows
    ]
