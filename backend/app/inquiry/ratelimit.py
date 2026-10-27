"""問い合わせ AI の 1 日の回数の制限（spec 004 の 004-T040・research.md R-07・FR-024・FR-027）。

学校の共有のキーを使い切らないために、家族ごと（初期値 10 回）と施設全体（初期値 300 回）で、
1 日（日本時間）に AI を呼べる回数を数える。数えるのは Redis（キーには用途の接頭辞と期限を付ける。
app/redis.py の決まり）。

- 発言を受け付ける前に、`INCR` で両方を 1 増やす。上限を超えたら、増やした分を `DECR` で戻して
  `InquiryLimit` を出す（AI は呼ばない。SC-009）。
  同時に送られても、`INCR` は 1 つずつ数えるので超えない
- AI が止まったときなど、答えが出なかったときは `release` で戻す（回数に数えない。FR-026）
- `INCR` と `EXPIRE` は、同じパイプラインで毎回行う（期限のないキーを残さない）
"""

from dataclasses import dataclass

from app.clock import today_jst
from app.config import get_settings
from app.redis import get_redis

# キーの期限（2 日。日付が変わったあとに数え直しても、古いキーが残り続けないように）
KEY_TTL_SECONDS = 2 * 24 * 60 * 60


class InquiryLimit(Exception):
    """家族の 1 日の回数、または施設全体の 1 日の回数を超えた（429 `inquiry_limit`）。"""


@dataclass(frozen=True)
class Ticket:
    """数えた回数の控え。答えが出なかったとき、同じキーから戻すために使う（日付をまたいでも同じ）。"""

    family_key: str
    facility_key: str


def _keys(family_account_id: int) -> Ticket:
    day = today_jst().strftime("%Y%m%d")
    return Ticket(
        family_key=f"ratelimit:inquiry:family:{family_account_id}:{day}",
        facility_key=f"ratelimit:inquiry:facility:{day}",
    )


def consume(family_account_id: int) -> Ticket:
    """発言を受け付ける前に、回数を 1 つ数える。上限を超えるときは、戻して InquiryLimit を出す。"""
    settings = get_settings()
    ticket = _keys(family_account_id)
    redis = get_redis()
    pipeline = redis.pipeline()
    for key in (ticket.family_key, ticket.facility_key):
        pipeline.incr(key)
        pipeline.expire(key, KEY_TTL_SECONDS)
    family_count, _, facility_count, _ = pipeline.execute()

    if (
        family_count > settings.inquiry_family_daily_limit
        or facility_count > settings.inquiry_facility_daily_limit
    ):
        release(ticket)
        raise InquiryLimit
    return ticket


def release(ticket: Ticket) -> None:
    """数えた回数を戻す（上限を超えた発言・AI が止まったとき。回数に数えない）。

    戻すときも期限を付ける。途中でキーが消えていたとき（Redis の再起動など）に `DECR` だけすると、
    期限のない -1 のキーができて、上限が 1 回分甘くなるため（app/redis.py の決まり）。
    """
    pipeline = get_redis().pipeline()
    for key in (ticket.family_key, ticket.facility_key):
        pipeline.decr(key)
        pipeline.expire(key, KEY_TTL_SECONDS)
    pipeline.execute()
