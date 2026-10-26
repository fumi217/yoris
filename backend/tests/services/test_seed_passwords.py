"""初期データの人に SEED_PASSWORD を入れる（spec 001 の T022・app/seed/people.py）。"""

import pytest

from app.auth import passwords
from app.auth.passwords import verify_password
from app.models.core import User
from app.seed.people import NO_PASSWORD, set_seed_passwords


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(passwords, "BCRYPT_ROUNDS", 4)


def test_sets_password_only_for_users_without_one(session, make_staff):
    seeded = session.get(User, make_staff().user_id)
    seeded.password_hash = NO_PASSWORD
    other = session.get(User, make_staff().user_id)
    other.password_hash = "x"
    session.flush()

    assert set_seed_passwords(session, "kumoyama-sora") >= 1

    session.refresh(seeded)
    session.refresh(other)
    assert verify_password("kumoyama-sora", seeded.password_hash)
    # パスワードを持っている人は変えない
    assert other.password_hash == "x"


def test_does_nothing_without_password(session, make_staff):
    seeded = session.get(User, make_staff().user_id)
    seeded.password_hash = NO_PASSWORD
    session.flush()

    assert set_seed_passwords(session, None) == 0
    assert set_seed_passwords(session, "") == 0

    session.refresh(seeded)
    assert seeded.password_hash == NO_PASSWORD


def test_rejects_password_that_breaks_the_rules(session):
    with pytest.raises(ValueError, match="too_common"):
        set_seed_passwords(session, "password")
