"""メールの文面（001-T057）のテスト。DB は使わない。"""

import re

import pytest

from app.templates.email import _TEXTS, UnknownTemplate, render


def test_reply_mail_has_only_kind_and_link():
    subject, body = render("reply", {"link": "http://app.test/family"}, "http://base.test")
    assert subject == "知りたいことへの返事が届きました"
    assert "http://app.test/family" in body


def test_link_falls_back_to_app_base_url():
    _, body = render("reply", {}, "http://base.test")
    assert "http://base.test" in body


def test_reply_mail_ignores_anything_but_the_link():
    # params に余計なものが入っていても、文面には出ない（SC-010 の最後の守り）
    _, body = render("reply", {"link": "http://app.test", "body": "ひみつの返事の中身"}, None)
    assert "ひみつの返事の中身" not in body


def test_announcement_mail_has_the_title():
    subject, body = render("announcement", {"title": "面会を一時中止します"}, "http://base.test")
    assert subject == "施設からのお知らせが届きました"
    assert "面会を一時中止します" in body


@pytest.mark.parametrize("template", ["daily_digest", "weekly_digest"])
def test_digest_mails_are_rendered(template):
    subject, body = render(template, {}, "http://base.test")
    assert "連絡帳がまとまりました" in subject
    assert "http://base.test" in body


@pytest.mark.parametrize("template", ["visit_confirmed", "visit_cancelled", "visit_reminder"])
def test_visit_mails_have_the_date_and_the_link(template):
    params = {"visit_at": "10月26日（月）13:00", "link": "http://app.test/family/visits"}
    _, body = render(template, params, "http://base.test")
    assert "10月26日（月）13:00" in body
    assert "http://app.test/family/visits" in body


def test_visit_reminder_asks_to_call_the_facility():
    # 前日 17 時を過ぎていて、アプリでは変えられないので、電話を案内する
    subject, body = render("visit_reminder", {"visit_at": "10月26日（月）13:00"}, None)
    assert subject == "明日は面会の予定があります"
    assert "変更・取り消しは、施設にお電話ください" in body


@pytest.mark.parametrize("template", ["visit_confirmed", "visit_cancelled", "visit_reminder"])
def test_visit_mails_never_show_resident_name_or_reason(template):
    # params に余計なものが入っていても、文面には出ない（FR-014 の最後の守り）
    params = {"visit_at": "10月26日（月）13:00", "resident": "佐藤さんの母", "reason": "体調不良"}
    _, body = render(template, params, "http://base.test")
    assert "佐藤さんの母" not in body
    assert "体調不良" not in body


@pytest.mark.parametrize("template", ["invitation", "owner_account", "nothing"])
def test_template_without_text_is_unknown(template):
    # 招待・施設長の ID のメールは、それぞれのタスクで文面を足す
    with pytest.raises(UnknownTemplate):
        render(template, {}, "http://base.test")


def test_staff_message_reply_mail_has_only_the_link():
    # 問い合わせ AI のメッセージへの職員の返事。返事の中身は、メールに入れない（SC-010）
    params = {"link": "http://app.test/family", "body": "ひみつの返事の中身"}
    subject, body = render("staff_message_reply", params, "http://base.test")
    assert subject == "施設からメッセージの返事が届きました"
    assert "http://app.test/family" in body
    assert "ひみつの返事の中身" not in body


# 家族の言語のメール（001-T084・FR-021）


def test_every_template_has_ja_id_en():
    for template, texts in _TEXTS.items():
        assert set(texts) == {"ja", "id", "en"}, template


@pytest.mark.parametrize("template", list(_TEXTS))
def test_japanese_mail_has_kanji_only_and_no_furigana(template):
    # 日本語のメールは漢字だけ。ふりがなの書き方 {漢字|かんじ} も、かっこの読みも入れない
    subject, body = render(
        template, {"lang": "ja", "visit_at": "10月26日（月）13:00"}, "http://b.test"
    )
    assert "{" not in subject + body
    assert not re.search(r"[一-龠]（[ぁ-ん]+）", subject + body)


@pytest.mark.parametrize("lang", ["id", "en"])
@pytest.mark.parametrize("template", list(_TEXTS))
def test_other_language_mail_has_no_japanese(template, lang):
    params = {"lang": lang, "visit_at": "Mon, Oct 26 13:00", "title": "Notice"}
    subject, body = render(template, params, "http://b.test")
    assert not re.search(r"[ぁ-んァ-ヶ一-龠]", subject + body)
    assert "http://b.test" in body


@pytest.mark.parametrize("lang", ["id", "en"])
def test_visit_mail_in_other_language_has_the_date_and_the_link(lang):
    params = {
        "lang": lang,
        "visit_at": "Mon, Oct 26 13:00",
        "link": "http://app.test/family/visits",
    }
    _, body = render("visit_confirmed", params, "http://base.test")
    assert "Mon, Oct 26 13:00" in body
    assert "http://app.test/family/visits" in body


@pytest.mark.parametrize("lang", [None, "", "fr"])
def test_missing_or_unknown_language_falls_back_to_japanese(lang):
    params = {} if lang is None else {"lang": lang}
    subject, _ = render("reply", params, "http://base.test")
    assert subject == "知りたいことへの返事が届きました"


def test_curly_braces_in_the_title_do_not_break_the_mail():
    _, body = render("announcement", {"title": "{link} {visit_at} {x}"}, "http://base.test")
    assert "{link} {visit_at} {x}" in body


# ---- まとめに写真が入るとき（005-T027。FR-018・FR-019） ----

ALBUM_ONLY = {"has_album": True, "has_records": False}
ALBUM_AND_RECORDS = {"has_album": True, "has_records": True}


def test_digest_mail_without_album_stays_the_same():
    subject, body = render("daily_digest", {"lang": "ja"}, "http://base.test")
    assert subject == "今日の連絡帳がまとまりました"
    assert "写真" not in subject + body


def test_digest_mail_with_photos_only():
    subject, body = render("daily_digest", {**ALBUM_ONLY, "lang": "ja"}, "http://base.test")
    assert subject == "アルバムに新しい写真が載りました"
    assert "http://base.test" in body
    subject, _ = render("weekly_digest", {**ALBUM_ONLY, "lang": "ja"}, "http://base.test")
    assert subject == "今週、アルバムに新しい写真が載りました"


@pytest.mark.parametrize("template", ["daily_digest", "weekly_digest"])
def test_digest_mail_with_records_and_photos(template):
    subject, _ = render(template, {**ALBUM_AND_RECORDS, "lang": "ja"}, "http://base.test")
    assert "連絡帳がまとまりました" in subject
    assert "アルバムに新しい写真が載りました" in subject


@pytest.mark.parametrize("template", ["daily_digest", "weekly_digest"])
@pytest.mark.parametrize("language", ["ja", "id", "en"])
@pytest.mark.parametrize("flags", [ALBUM_ONLY, ALBUM_AND_RECORDS])
def test_digest_album_mails_exist_in_every_language(template, language, flags):
    subject, body = render(template, {**flags, "lang": language}, "http://base.test")
    assert subject
    assert "http://base.test" in body
    # 記録だけの文面とは別の文面になっている
    plain_subject, _ = render(template, {"lang": language}, "http://base.test")
    assert subject != plain_subject


def test_digest_album_mails_show_only_the_link():
    # params に余計なものが入っていても、文面には出ない（FR-019 の最後の守り）
    params = {
        **ALBUM_AND_RECORDS,
        "lang": "ja",
        "comment": "ひみつのコメント",
        "file_name": "photo-secret.png",
        "resident": "佐藤さんの母",
    }
    subject, body = render("daily_digest", params, "http://base.test")
    for secret in ("ひみつのコメント", "photo-secret.png", "佐藤さんの母"):
        assert secret not in subject + body


@pytest.mark.parametrize("template", ["reply", "announcement", "visit_confirmed"])
def test_album_flag_does_not_change_other_kinds(template):
    plain = render(template, {"lang": "ja", "title": "題", "visit_at": "月曜"}, None)
    flagged = render(
        template, {**ALBUM_ONLY, "lang": "ja", "title": "題", "visit_at": "月曜"}, None
    )
    assert flagged == plain
