"""メールの文面（種類ごと）。001-T057・T084。spec 001 の research.md R-09。

文面に渡すのは、種類・お知らせのタイトル・面会の日時（visit_at）・アプリへのリンク・言語（lang）だけ
（email_outbox.params と同じ）。
記録・返事・本文・入居者名・取り消しの理由は渡さない（SC-010・FR-014）。
そのため、文面に中身が入る失敗は、そもそも起こらない。

言語は家族の表示言語（ja・id・en）。日本語のメールは漢字だけで、ふりがなは付けない（FR-021）。
lang がない・知らない言語のときは、日本語にする。
"""

from collections.abc import Mapping

DEFAULT_LANGUAGE = "ja"


class UnknownTemplate(Exception):
    """文面がまだない種類（招待・施設長の ID は、それぞれのタスクで足す）。"""


# 種類 → 言語 → (件名, 本文)。本文の {link}・{title}・{visit_at} は、render が埋める
_TEXTS: dict[str, dict[str, tuple[str, str]]] = {
    "reply": {
        "ja": (
            "知りたいことへの返事が届きました",
            "知りたいことへの返事が届きました。アプリを開いて確かめてください。\n{link}\n",
        ),
        "id": (
            "Balasan untuk hal yang ingin Anda ketahui telah masuk",
            "Balasan untuk hal yang ingin Anda ketahui telah masuk. "
            "Silakan buka aplikasi untuk memeriksanya.\n{link}\n",
        ),
        "en": (
            "A reply to what you wanted to know has arrived",
            "A reply to what you wanted to know has arrived. "
            "Please open the app to check it.\n{link}\n",
        ),
    },
    "staff_message_reply": {
        "ja": (
            "施設からメッセージの返事が届きました",
            "施設からメッセージの返事が届きました。アプリを開いて確かめてください。\n{link}\n",
        ),
        "id": (
            "Balasan pesan dari fasilitas telah masuk",
            "Balasan pesan dari fasilitas telah masuk. "
            "Silakan buka aplikasi untuk memeriksanya.\n{link}\n",
        ),
        "en": (
            "A reply to your message from the facility has arrived",
            "A reply to your message from the facility has arrived. "
            "Please open the app to check it.\n{link}\n",
        ),
    },
    "daily_digest": {
        "ja": (
            "今日の連絡帳がまとまりました",
            "今日の連絡帳がまとまりました。アプリを開いて確かめてください。\n{link}\n",
        ),
        "id": (
            "Buku harian hari ini sudah siap",
            "Buku harian hari ini sudah siap. Silakan buka aplikasi untuk memeriksanya.\n{link}\n",
        ),
        "en": (
            "Today's daily notes are ready",
            "Today's daily notes are ready. Please open the app to check them.\n{link}\n",
        ),
    },
    "weekly_digest": {
        "ja": (
            "今週の連絡帳がまとまりました",
            "今週の連絡帳がまとまりました。アプリを開いて確かめてください。\n{link}\n",
        ),
        "id": (
            "Buku harian minggu ini sudah siap",
            "Buku harian minggu ini sudah siap. "
            "Silakan buka aplikasi untuk memeriksanya.\n{link}\n",
        ),
        "en": (
            "This week's daily notes are ready",
            "This week's daily notes are ready. Please open the app to check them.\n{link}\n",
        ),
    },
    "announcement": {
        "ja": (
            "施設からのお知らせが届きました",
            "施設からのお知らせが届きました。\n{title}\nアプリを開いて確かめてください。\n{link}\n",
        ),
        "id": (
            "Pemberitahuan dari fasilitas telah masuk",
            "Pemberitahuan dari fasilitas telah masuk.\n{title}\n"
            "Silakan buka aplikasi untuk memeriksanya.\n{link}\n",
        ),
        "en": (
            "A notice from the facility has arrived",
            "A notice from the facility has arrived.\n{title}\n"
            "Please open the app to check it.\n{link}\n",
        ),
    },
    "visit_confirmed": {
        "ja": (
            "面会の予約が確定しました",
            "面会の予約が確定しました。\n{visit_at}\nアプリを開いて確かめてください。\n{link}\n",
        ),
        "id": (
            "Reservasi kunjungan telah dikonfirmasi",
            "Reservasi kunjungan telah dikonfirmasi.\n{visit_at}\n"
            "Silakan buka aplikasi untuk memeriksanya.\n{link}\n",
        ),
        "en": (
            "Your visit reservation is confirmed",
            "Your visit reservation is confirmed.\n{visit_at}\n"
            "Please open the app to check it.\n{link}\n",
        ),
    },
    # 取り消しの理由は、メールには書かない。アプリの予約の画面で見せる（spec 003 の R-07）
    "visit_cancelled": {
        "ja": (
            "面会の予約が取り消されました",
            "面会の予約が取り消されました。\n{visit_at}\nくわしくは、アプリを開いて確かめてください。\n{link}\n",
        ),
        "id": (
            "Reservasi kunjungan telah dibatalkan",
            "Reservasi kunjungan telah dibatalkan.\n{visit_at}\n"
            "Untuk lebih jelasnya, silakan buka aplikasi.\n{link}\n",
        ),
        "en": (
            "Your visit reservation has been cancelled",
            "Your visit reservation has been cancelled.\n{visit_at}\n"
            "For details, please open the app.\n{link}\n",
        ),
    },
    "visit_reminder": {
        "ja": (
            "明日は面会の予定があります",
            "明日は面会の予定があります。\n{visit_at}\n変更・取り消しは、施設にお電話ください。\n{link}\n",
        ),
        "id": (
            "Besok ada jadwal kunjungan",
            "Besok ada jadwal kunjungan.\n{visit_at}\n"
            "Untuk mengubah atau membatalkan, silakan hubungi fasilitas melalui telepon.\n{link}\n",
        ),
        "en": (
            "You have a visit scheduled for tomorrow",
            "You have a visit scheduled for tomorrow.\n{visit_at}\n"
            "To change or cancel, please call the facility.\n{link}\n",
        ),
    },
}


def render(template: str, params: Mapping[str, str], base_url: str | None) -> tuple[str, str]:
    """(件名, 本文) を返す。リンクは params の "link"（なければアプリの URL）、言語は "lang"。"""
    texts = _TEXTS.get(template)
    if texts is None:
        raise UnknownTemplate(template)
    subject, body = texts.get(params.get("lang", ""), texts[DEFAULT_LANGUAGE])
    link = params.get("link") or base_url or ""
    # str.format は使わない（タイトルに { } が入っても壊れないように、1 つずつ置き換える）。
    # 利用者が書いた title は、置き換えた文をもう一度置き換えないよう、最後にする
    for key, value in (
        ("{link}", link),
        ("{visit_at}", params.get("visit_at", "")),
        ("{title}", params.get("title", "")),
    ):
        body = body.replace(key, value)
    return subject, body
