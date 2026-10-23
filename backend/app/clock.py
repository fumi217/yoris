"""時刻と「今日」（spec 001 の research.md R-14、spec 003 の 003-T002）。

DB には UTC で保存し、「当日」「前日 17 時」などは日本時間で判断する。判断はバックエンドだけで行い、
タブレットやスマートフォンの時計は使わない。

テストで時刻を固定するときは、関数に now を渡すか、`app.clock.now` を差し替える
（例：`monkeypatch.setattr("app.clock.now", lambda: datetime(2026, 10, 23, 3, tzinfo=UTC))`）。
"""

from datetime import UTC, date, datetime, timedelta, timezone

# 日本は夏時間がないので、+9 時間で決める
JST = timezone(timedelta(hours=9), "Asia/Tokyo")


def now() -> datetime:
    """今（UTC・タイムゾーン付き）。テストではこの関数を差し替える。"""
    return datetime.now(UTC)


def now_jst(at: datetime | None = None) -> datetime:
    """日本時間の今。at はテスト用（タイムゾーン付きの日時）。"""
    return (at or now()).astimezone(JST)


def today_jst(at: datetime | None = None) -> date:
    """日本時間の今日。"""
    return now_jst(at).date()
