"""記録のサンプル（数日分）。spec 001 の 001-T030。

初期データの仕組み（001-T015 の `python -m app.seed`）から呼ぶ。入居者と職員を入れたあとに呼ぶこと。
値は架空で、毎回同じになるように入居者の順番から決める（デモのたびに変わらないように）。
未記録の欄も見せられるよう、今日の夜ごはん・おやつは付けない。
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.records import CareRecord

MEAL_VALUES = ("10", "8", "8", "5", "10", "2")
MOOD_VALUES = ("smile", "normal", "normal", "smile", "low")
SLEEP_VALUES = ("good", "normal", "good", "poor")


def add_sample_records(
    session: Session, *, resident_ids: list[int], staff_id: int, today: date, days: int = 3
) -> int:
    """今日を含む days 日分の記録を足し、足した件数を返す。commit は呼んだ側が行う。"""
    count = 0
    for day_index in range(days):
        record_date = today - timedelta(days=day_index)
        is_today = day_index == 0
        for n, resident_id in enumerate(resident_ids):
            k = n + day_index
            rows = [
                ("meal", "breakfast", MEAL_VALUES[k % len(MEAL_VALUES)]),
                ("meal", "lunch", MEAL_VALUES[(k + 1) % len(MEAL_VALUES)]),
                ("mood", "day", MOOD_VALUES[k % len(MOOD_VALUES)]),
                ("sleep", "day", SLEEP_VALUES[k % len(SLEEP_VALUES)]),
            ]
            if not is_today:
                rows += [
                    ("meal", "dinner", MEAL_VALUES[(k + 2) % len(MEAL_VALUES)]),
                    ("meal", "snack", MEAL_VALUES[(k + 3) % len(MEAL_VALUES)]),
                ]
            for item, slot, value in rows:
                session.add(
                    CareRecord(
                        resident_id=resident_id,
                        date=record_date,
                        item=item,
                        slot=slot,
                        value=value,
                        recorded_by=staff_id,
                    )
                )
                count += 1
    session.flush()
    return count
