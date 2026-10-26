"""メールの文面（001-T057）のテスト。DB は使わない。"""

import pytest

from app.templates.email import UnknownTemplate, render


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
