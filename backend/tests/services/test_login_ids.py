"""職員のログイン用の ID（002-T006）。本物の DB のシーケンスを使う。"""

import re

from app.auth.login_ids import next_login_ids
from app.models.core import User


def test_login_ids_are_s_and_5_digits_and_unique(session):
    login_ids = next_login_ids(session, 3)

    assert len(login_ids) == 3
    assert len(set(login_ids)) == 3
    assert all(re.fullmatch(r"s[0-9]{5}", login_id) for login_id in login_ids)


def test_login_ids_skip_numbers_already_used(session):
    # 次の番号を、手で入れた人がもう使っている
    [peek] = next_login_ids(session, 1)
    taken = f"s{int(peek[1:]) + 1:05d}"
    session.add(User(kind="staff", login_id=taken, password_hash="x"))
    session.flush()

    assert taken not in next_login_ids(session, 2)
