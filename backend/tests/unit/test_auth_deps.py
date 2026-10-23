"""役割のチェック（T010）のテスト。DB と Redis を使わず、ログイン中の人を直接渡して確かめる。"""

import pytest

from app.auth.deps import CurrentUser, require_family, require_staff
from app.errors import AppError, ErrorCode

FAMILY = CurrentUser(
    user_id=1,
    kind="family",
    role=None,
    staff_id=None,
    resident_id=10,
    language="ja",
    display_name="x",
)
CARE_WORKER = CurrentUser(
    user_id=2,
    kind="staff",
    role="care_worker",
    staff_id=20,
    resident_id=None,
    language="ja",
    display_name="x",
)
COUNSELOR = CurrentUser(
    user_id=3,
    kind="staff",
    role="counselor",
    staff_id=30,
    resident_id=None,
    language="ja",
    display_name="x",
)


def test_require_family_passes_family():
    assert require_family(FAMILY) == FAMILY


def test_require_family_rejects_staff():
    with pytest.raises(AppError) as error:
        require_family(CARE_WORKER)
    assert error.value.code == ErrorCode.FORBIDDEN


def test_require_staff_without_roles_passes_any_staff():
    check = require_staff()
    assert check(CARE_WORKER) == CARE_WORKER
    assert check(COUNSELOR) == COUNSELOR


def test_require_staff_rejects_family():
    with pytest.raises(AppError) as error:
        require_staff()(FAMILY)
    assert error.value.code == ErrorCode.FORBIDDEN


def test_require_staff_with_roles_passes_only_those_roles():
    check = require_staff(("counselor", "director"))
    assert check(COUNSELOR) == COUNSELOR
    with pytest.raises(AppError) as error:
        check(CARE_WORKER)
    assert error.value.code == ErrorCode.FORBIDDEN


def test_require_staff_rejects_unknown_role_name():
    with pytest.raises(ValueError):
        require_staff(("counsellor",))


def test_require_staff_rejects_empty_roles():
    # 書き忘れで、だれも入れない API にしない
    with pytest.raises(ValueError):
        require_staff(())
