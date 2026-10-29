"""変化の目印を付け直す・入居者一覧に返す（spec 006 の 006-T007・T010）。

`evaluate_change_flags` は、記録の保存・押し直し・取り消し（services/records.py）と
同じセッションで呼ぶ。
関数の中では commit しない（記録と目印が同じトランザクションで確定する。research.md R-03）。
決まりそのものは services/change_rules.py（DB に触らない関数）にある。

ログには、目印の id・決まりのコード・入居者の id・付いた／消えたの別だけを出す。
入居者の氏名・記録の値・ひとことは出さない（FR-014）。
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.change_flags import ChangeFlag, ChangeFlagConfirmation, ChangeRule
from app.models.core import Resident
from app.models.records import CareRecord
from app.services.change_rules import LOOKBACK_DAYS, RULES, RuleRecord, evaluate_rule

logger = logging.getLogger(__name__)


def evaluate_change_flags(session: Session, resident_id: int) -> None:
    """その入居者の目印を、今の記録に合わせて付ける・直す・消す。何度呼んでも同じになる。

    - 当てはまる・目印なし → 作る（まだ確かめていない）
    - 当てはまる・目印あり → もとの記録と続いた数を上書きする。確かめ済みで、続いた数が
      確かめたときより増えたら、まだ確かめていないに戻す（FR-010）
    - 当てはまらない・目印あり → 消す（status・cleared_at・cleared_reason を 1 回の更新で入れる）

    決まりがオフのあいだは調べない（オフにしたときの目印は、オフにする処理が消す。006-T020）。
    非開示の項目も含めて記録を直接読む（職員向けの機能。spec 001 の R-06）。
    読むのは、項目ごとのいちばん新しい記録の日から 6 日前まで（今日からではない。R-02）。
    """
    # 同じ入居者の調べ直しを順番にする。目印がまだなくても効くよう、目印ではなく入居者の行を押さえる
    # （2 人が同時に記録して、同じ目印を 2 つ作って一意制約に当たらないように。R-03）
    # FOR NO KEY UPDATE（key_share=True）にする。記録を新しく足すと、外部キーの確認で入居者の行に
    # FOR KEY SHARE が付く。FOR UPDATE だと、2 人が同時に新しく記録したとき、お互いの KEY SHARE の
    # 終わりを待ち合って止まる。NO KEY UPDATE は KEY SHARE と両立し、NO KEY UPDATE どうしは待つ
    session.scalars(
        select(Resident.id).where(Resident.id == resident_id).with_for_update(key_share=True)
    ).one()

    enabled_codes = set(session.scalars(select(ChangeRule.code).where(ChangeRule.enabled)))
    # 項目ごとに、いちばん新しい記録の日から 6 日前までを読む（決まりの関数も同じ範囲に絞る）
    newest = session.execute(
        select(CareRecord.item, func.max(CareRecord.date))
        .where(CareRecord.resident_id == resident_id, CareRecord.deleted_at.is_(None))
        .group_by(CareRecord.item)
    ).all()
    window = [
        and_(CareRecord.item == item, CareRecord.date >= latest - timedelta(days=LOOKBACK_DAYS - 1))
        for item, latest in newest
    ]
    records = (
        [
            RuleRecord(r.id, r.date, r.item, r.slot, r.value)
            for r in session.scalars(
                select(CareRecord).where(
                    CareRecord.resident_id == resident_id,
                    CareRecord.deleted_at.is_(None),
                    or_(*window),
                )
            )
        ]
        if window
        else []
    )
    current = {
        flag.rule_code: flag
        for flag in session.scalars(
            select(ChangeFlag)
            .where(ChangeFlag.resident_id == resident_id, ChangeFlag.cleared_at.is_(None))
            .with_for_update()
        )
    }

    for code in RULES:
        if code not in enabled_codes:
            continue
        result = evaluate_rule(code, records)
        flag = current.get(code)
        evidence = [e.as_json() for e in result.evidence]
        if result.matches and flag is None:
            flag = ChangeFlag(
                resident_id=resident_id,
                rule_code=code,
                streak=result.streak,
                evidence=evidence,
                status="unconfirmed",
            )
            session.add(flag)
            session.flush()
            logger.info("目印が付いた: flag=%s rule=%s resident=%s", flag.id, code, resident_id)
        elif result.matches:
            _update(session, flag, streak=result.streak, evidence=evidence)
        elif flag is not None:
            now = datetime.now(UTC)
            flag.status = "cleared"
            flag.cleared_at = now
            flag.cleared_reason = "not_matching"
            flag.updated_at = now
            session.flush()
            logger.info("目印が消えた: flag=%s rule=%s resident=%s", flag.id, code, resident_id)


def _update(session: Session, flag: ChangeFlag, *, streak: int, evidence: list[dict]) -> None:
    """続いている目印の、続いた数ともとの記録を直す。変わらなければ何もしない。"""
    status = flag.status
    if status == "confirmed":
        confirmed_streak = session.scalar(
            select(ChangeFlagConfirmation.streak_at_confirmation)
            .where(ChangeFlagConfirmation.change_flag_id == flag.id)
            .order_by(ChangeFlagConfirmation.confirmed_at.desc(), ChangeFlagConfirmation.id.desc())
            .limit(1)
        )
        # 確かめたときより増えたら、まだ確かめていないに戻す（FR-010）。
        # 数えるのは 7 日分までなので、7 日（食事は 21 食）を超えて続いても戻らない
        if confirmed_streak is not None and streak > confirmed_streak:
            status = "unconfirmed"
    if (flag.streak, flag.evidence, flag.status) == (streak, evidence, status):
        return
    flag.streak = streak
    flag.evidence = evidence
    flag.status = status
    flag.updated_at = datetime.now(UTC)
    session.flush()


@dataclass(frozen=True)
class ResidentFlag:
    """入居者一覧の 1 人分。今の目印があるときだけ作る。"""

    has_flag: bool
    has_unconfirmed: bool


@dataclass(frozen=True)
class FlagSummary:
    # 今の目印がある入居者だけ
    residents: dict[int, ResidentFlag]
    # まだ確かめていない目印がある入居者の人数（research.md R-04）
    unconfirmed_resident_count: int


def get_flag_summary(session: Session) -> FlagSummary:
    """入居者一覧に返す目印と件数。入居者一覧を開けるのは事務員以外の職員だけなので、役割では分けない。"""
    rows = session.execute(
        select(ChangeFlag.resident_id, ChangeFlag.status).where(ChangeFlag.cleared_at.is_(None))
    ).all()
    unconfirmed = {resident_id for resident_id, status in rows if status == "unconfirmed"}
    return FlagSummary(
        residents={
            resident_id: ResidentFlag(has_flag=True, has_unconfirmed=resident_id in unconfirmed)
            for resident_id in {resident_id for resident_id, _ in rows}
        },
        unconfirmed_resident_count=len(unconfirmed),
    )
