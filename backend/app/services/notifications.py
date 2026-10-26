"""返事のお知らせとメールの送る予定を作る（spec 001 の 001-T051。research.md R-09）。

- ゆうの返事の保存（001-T052）が、同じ DB のセッションを渡して呼ぶ。
  返事の保存と同じトランザクションで確定するので、返事だけ保存されてお知らせが消える、ということが起きない
- 関数の中では commit しない（呼んだ API が最後に 1 回だけ commit する）
- 作った email_outbox の id を返す。呼んだ側は、コミットのあとに send_email_now(outbox_id) で
  その場でも送ってみる
- メールの文面に渡すのは、種類とリンクだけ。返事の中身・職員の名前・入居者の名前は渡さない（SC-010）
- 返事のお知らせは、家族の通知設定にかかわらず作る
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.core import FamilyAccount, User
from app.models.inquiry import StaffMessage
from app.models.notifications import EmailOutbox, Notification
from app.models.replies import Reply
from app.models.requests import Request


def create_reply_notice(session: Session, reply_id: int) -> int:
    """返事のお知らせ（アプリ内）とメールの送る予定を作り、email_outbox の id を返す。"""
    family_account_id, email = session.execute(
        select(FamilyAccount.id, User.email)
        .join(User, User.id == FamilyAccount.user_id)
        .join(Request, Request.resident_id == FamilyAccount.resident_id)
        .join(Reply, Reply.request_id == Request.id)
        .where(Reply.id == reply_id)
    ).one()

    session.add(Notification(family_account_id=family_account_id, kind="reply", reply_id=reply_id))

    # アプリの URL が決まっていないときは、リンクを入れない（文面の側が、アプリの URL に戻る）
    base_url = get_settings().app_base_url
    params = {"link": f"{base_url}/family"} if base_url else {}
    outbox = EmailOutbox(to_email=email, template="reply", params=params)
    session.add(outbox)
    session.flush()
    return outbox.id


def create_staff_message_reply_notice(session: Session, staff_message_id: int) -> int:
    """職員の返事（問い合わせ AI のメッセージへの返事）のお知らせとメールの送る予定を作り、
    email_outbox の id を返す（spec 004 の 004-T028。research.md R-09）。

    create_reply_notice と同じ形：commit しない（みさきの返事の API が、同じトランザクションで呼び、
    commit のあとに send_email_now を呼ぶ）。返事の中身は渡さない。通知設定にかかわらず作る。
    """
    family_account_id, email = session.execute(
        select(FamilyAccount.id, User.email)
        .join(User, User.id == FamilyAccount.user_id)
        .join(StaffMessage, StaffMessage.resident_id == FamilyAccount.resident_id)
        .where(StaffMessage.id == staff_message_id)
    ).one()

    session.add(
        Notification(
            family_account_id=family_account_id,
            kind="staff_message_reply",
            staff_message_id=staff_message_id,
        )
    )

    base_url = get_settings().app_base_url
    params = {"link": f"{base_url}/family"} if base_url else {}
    outbox = EmailOutbox(to_email=email, template="staff_message_reply", params=params)
    session.add(outbox)
    session.flush()
    return outbox.id
