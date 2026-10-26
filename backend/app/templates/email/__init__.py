"""メールの文面（種類ごと）。001-T057。spec 001 の research.md R-09。

文面に渡すのは、種類・お知らせのタイトル・面会の日時（visit_at）・アプリへのリンクだけ
（email_outbox.params と同じ）。
記録・返事・本文・入居者名・取り消しの理由は渡さない（SC-010・FR-014）。
そのため、文面に中身が入る失敗は、そもそも起こらない。
"""

from collections.abc import Mapping


class UnknownTemplate(Exception):
    """文面がまだない種類（招待・施設長の ID は、それぞれのタスクで足す）。"""


def _reply(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    return (
        "知りたいことへの返事が届きました",
        f"知りたいことへの返事が届きました。アプリを開いて確かめてください。\n{link}\n",
    )


def _daily_digest(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    return (
        "今日の連絡帳がまとまりました",
        f"今日の連絡帳がまとまりました。アプリを開いて確かめてください。\n{link}\n",
    )


def _weekly_digest(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    return (
        "今週の連絡帳がまとまりました",
        f"今週の連絡帳がまとまりました。アプリを開いて確かめてください。\n{link}\n",
    )


def _announcement(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    title = params.get("title", "")
    return (
        "施設からのお知らせが届きました",
        f"施設からのお知らせが届きました。\n{title}\nアプリを開いて確かめてください。\n{link}\n",
    )


def _visit_confirmed(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    visit_at = params.get("visit_at", "")
    return (
        "面会の予約が確定しました",
        f"面会の予約が確定しました。\n{visit_at}\nアプリを開いて確かめてください。\n{link}\n",
    )


def _visit_cancelled(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    visit_at = params.get("visit_at", "")
    # 取り消しの理由は、メールには書かない。アプリの予約の画面で見せる（spec 003 の R-07）
    return (
        "面会の予約が取り消されました",
        f"面会の予約が取り消されました。\n{visit_at}\nくわしくは、アプリを開いて確かめてください。\n{link}\n",
    )


def _visit_reminder(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    visit_at = params.get("visit_at", "")
    return (
        "明日は面会の予定があります",
        f"明日は面会の予定があります。\n{visit_at}\n変更・取り消しは、施設にお電話ください。\n{link}\n",
    )


def _staff_message_reply(link: str, params: Mapping[str, str]) -> tuple[str, str]:
    return (
        "施設からメッセージの返事が届きました",
        f"施設からメッセージの返事が届きました。アプリを開いて確かめてください。\n{link}\n",
    )


_RENDERERS = {
    "reply": _reply,
    "staff_message_reply": _staff_message_reply,
    "daily_digest": _daily_digest,
    "weekly_digest": _weekly_digest,
    "announcement": _announcement,
    "visit_confirmed": _visit_confirmed,
    "visit_cancelled": _visit_cancelled,
    "visit_reminder": _visit_reminder,
}


def render(template: str, params: Mapping[str, str], base_url: str | None) -> tuple[str, str]:
    """(件名, 本文) を返す。リンクは params の "link"、なければアプリの URL。"""
    renderer = _RENDERERS.get(template)
    if renderer is None:
        raise UnknownTemplate(template)
    link = params.get("link") or base_url or ""
    return renderer(link, params)
