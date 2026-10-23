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


@pytest.mark.parametrize("template", ["invitation", "owner_account", "nothing"])
def test_template_without_text_is_unknown(template):
    # 招待・施設長の ID のメールは、それぞれのタスクで文面を足す
    with pytest.raises(UnknownTemplate):
        render(template, {}, "http://base.test")
