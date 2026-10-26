"""職員のログイン用の ID（spec 002 の T006・research.md R-06）。

形は `s` ＋ 5 桁の数字（`s00001`〜`s99999`）。
番号は PostgreSQL のシーケンス（`staff_login_id_seq`）が配るので、
2 人が同時に作ってもぶつからない（「いちばん大きい番号＋1」を自分で数えない）。
職員のアカウント（001-T088）・初期データ（001-T015）・決済の申し込み（002）が使う。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.core import User, staff_login_id_seq


def next_login_ids(session: Session, count: int = 1) -> list[str]:
    """次のログイン用の ID を count 個返す。手で入れた人と同じ番号は飛ばす。

    番号は 1 回の問い合わせでまとめてもらい、使われているかも 1 回で確かめる
    （人数分の問い合わせにしない）。
    シーケンスの番号は取り消しても戻らないので、番号が飛ぶことがある（ID が重ならなければよい）。
    """
    login_ids: list[str] = []
    while len(login_ids) < count:
        needed = count - len(login_ids)
        numbers = session.scalars(
            select(staff_login_id_seq.next_value()).select_from(func.generate_series(1, needed))
        )
        candidates = [f"s{number:05d}" for number in numbers]
        used = set(session.scalars(select(User.login_id).where(User.login_id.in_(candidates))))
        login_ids += [login_id for login_id in candidates if login_id not in used]
    return login_ids
