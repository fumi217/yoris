"""様子のメモのテーブルの初期値と制約（spec 007 の 007-T002・data-model.md）。

DB は tests/conftest.py の session（テストごとに取り消す）を使う。
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.memos import CareMemo, CareMemoRevision


@pytest.fixture
def memo_args(make_staff, make_family) -> dict:
    staff = make_staff(language="id")
    family = make_family()
    return {
        "resident_id": family.resident_id,
        "author_staff_id": staff.id,
        "memo_date": date(2026, 10, 26),
        "source_lang": "id",
        "original_text": "Hari ini makan siangnya habis.",
    }


def test_new_memo_is_draft_with_no_warnings(session, memo_args):
    memo = CareMemo(**memo_args)
    session.add(memo)
    session.flush()
    session.refresh(memo)

    assert memo.status == "draft"
    assert memo.warnings == []
    assert memo.written_at is not None
    assert memo.rewritten_text is None

    revision = CareMemoRevision(
        memo_id=memo.id,
        original_text=memo.original_text,
        rewritten_text="今日はお昼ごはんを全部召し上がりました。",
        model="fake",
        latency_ms=10,
    )
    session.add(revision)
    session.flush()
    assert revision.id is not None


@pytest.mark.parametrize(
    "override",
    [
        {"original_text": "あ" * 501},
        {"original_text": ""},
        {"source_lang": "vi"},
        {"status": "deleted"},
        {"return_reason": "あ" * 201},
    ],
)
def test_constraints_reject_bad_values(session, memo_args, override):
    session.add(CareMemo(**{**memo_args, **override}))

    with pytest.raises(IntegrityError):
        session.flush()
