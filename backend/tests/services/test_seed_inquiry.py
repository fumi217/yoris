"""職員の返事の定型文の初期データ（spec 004 の 004-T011）。本物の DB に流して確かめる。"""

from sqlalchemy import select

from app.models.inquiry import StaffMessageTemplate
from app.seed.inquiry import STAFF_TEMPLATES, add_staff_message_templates

CODES = [code for _, codes in STAFF_TEMPLATES for code in codes]


def _templates(session) -> list[StaffMessageTemplate]:
    return list(
        session.scalars(select(StaffMessageTemplate).where(StaffMessageTemplate.code.in_(CODES)))
    )


def test_add_staff_message_templates_twice_adds_them_once(session):
    add_staff_message_templates(session)
    add_staff_message_templates(session)

    templates = _templates(session)
    assert sorted(t.code for t in templates) == sorted(CODES)
    # 並び順は種類の中で 1 から
    by_code = {t.code: t for t in templates}
    for category, codes in STAFF_TEMPLATES:
        assert [by_code[code].sort_order for code in codes] == list(range(1, len(codes) + 1))
        assert all(by_code[code].category == category for code in codes)
