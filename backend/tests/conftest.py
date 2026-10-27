"""全部のテストで使える準備（fixture）。spec 001 の T020・research.md R-19。

本物の PostgreSQL と Redis を使う
（モックにすると、期限や一意制約が正しく動くかを確かめられないため）。

- `session`：DB のセッション。テストごとに外のトランザクションを開き、最後に取り消すので、
  テストで入れたデータは残らない（API の中の `session.commit()` も、取り消し地点の確定になるだけ）
- `redis`：テスト用の番号（/15）の Redis。テストの前後で空にする（開発のログイン /0 は消さない）
- `client`：API を呼ぶクライアント。API の中の DB は `session` を使う。本番の設定で動かし、
  書き込みの確認のヘッダー（`X-Requested-With: fetch`）は最初から付けている
- `facility`：施設（施設は 1 つの決まりなので、開発の DB にあればそれを使い、なければ作る）
- `make_staff`・`make_family`：架空の職員・家族を作る
- `login_as`：`client`（または渡したクライアント）を、その人としてログインした状態にする

使い方：

    def test_me(client, make_family, login_as):
        family = make_family()
        login_as(family.user_id)
        assert client.get("/api/me").json()["kind"] == "family"

テストでは AI を呼ばない：`OPENROUTER_API_KEY` は、どのテストでも必ず空にする
（学校配布のキーを使わない。CLAUDE.md・技術選定 5 章）。
AI を使う処理（問い合わせ AI など）のテストは、引数に `fake_llm` を書くと、
本物の AI の代わりにテスト用の LLM（モック。tests/fakes/llm.py）が使われる。
返す応答は先に足しておく：

    from tests.fakes.llm import tool_call_response

    def test_answer(fake_llm, ...):
        fake_llm.add(tool_call_response("get_care_records", {...}), tool_call_response(...))
        ...
        assert fake_llm.calls[0].tools  # 呼ばれた中身も確かめられる

AI を呼ぶ側（app の中）は、`from app.inquiry import llm as llm_module` として、
`llm_module.get_llm_client()` の形で呼ぶ。`from app.inquiry.llm import get_llm_client` で
取り込むと、`fake_llm` の差し替えが効かず、テストが 503 になる
（差し替えるのは `app.inquiry.llm.get_llm_client` そのものなので）。

DATABASE_URL・REDIS_URL がないとき、手元ではテストを飛ばし、CI では失敗にする
（CI で DB が起動しないまま緑になるのを防ぐ）。
手元では `docker compose exec backend python -m pytest`。

注意：
- 手元では、開発の初期データが入った DB で動く。件数を確かめるときは、テストで作った行だけを数える
  （テーブル全体を数えると、手元と CI（空の DB）で結果が変わる）
- `make_client` は APP_ENV を書き換える。1 つのテストで、本番用と開発用のクライアントを混ぜない
- 取り消されるのは `session` を通した書き込みだけ。`with Session(get_engine())` で自分で開く処理
  （応答のあとの処理・20 時のまとめなど）は、テストの外で本当に書き込む（T057 で対応を決める）。
"""

import itertools
import os
from collections.abc import Callable, Iterator
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.orm import Session

from app.auth.sessions import SESSION_COOKIE, create_session
from app.db import get_session
from app.main import create_app
from app.models.core import Facility, FamilyAccount, Resident, Staff, User
from app.redis import get_redis
from tests.fakes.llm import FakeLLM
from tests.fakes.stripe import TEST_SIGNING_KEY, FakeStripe

# テストで使う Redis の番号（開発のログインは 0 番）
TEST_REDIS_DB = 15


def _require(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    if os.environ.get("CI"):
        pytest.fail(f"{name} がありません（CI では .github/workflows/ci.yml で入れる）")
    pytest.skip(f"{name} がない（手元では docker compose の中で動かす）")


@pytest.fixture(autouse=True)
def _no_ai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # .env にキーがあっても、テストから本物の AI を呼ばないように
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """本物の LLMClient の代わりに、テスト用の LLM（モック）を使う（spec 004 の T004・T014）。

    問い合わせ AI（app.inquiry.llm.get_llm_client）と、様子のメモの整える用
    （app.memos.rewrite.get_rewrite_client。spec 007）の、どちらも差し替える。
    """
    fake = FakeLLM()
    monkeypatch.setattr("app.inquiry.llm.get_llm_client", lambda: fake)
    monkeypatch.setattr("app.memos.rewrite.get_rewrite_client", lambda: fake)
    return fake


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch) -> FakeStripe:
    """Stripe を呼ぶ関数を偽物にする（spec 002 の R-11）。Webhook の署名の秘密もテスト用にする。"""
    fake = FakeStripe()
    for name in (
        "create_checkout_session",
        "expire_checkout_session",
        "retrieve_subscription",
        "cancel_subscription",
        "create_portal_session",
        "set_customer_name",
    ):
        monkeypatch.setattr(f"app.services.stripe_client.{name}", getattr(fake, name))
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", TEST_SIGNING_KEY)
    monkeypatch.setenv("APP_BASE_URL", "https://app.example.test")
    return fake


@pytest.fixture
def no_facility(session: Session) -> None:
    """施設がまだない状態にする（申し込みで最初の施設を作るテスト用。spec 002 の R-04）。

    テストのトランザクションの中で、施設とそれを指す行、受け取った Stripe の知らせを全部消す。
    最後に取り消されるので、開発の初期データは残る
    （TRUNCATE も PostgreSQL ではトランザクションの中で取り消せる）。
    """
    session.execute(text("TRUNCATE facilities, billing_events CASCADE"))


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    engine = create_engine(_require("DATABASE_URL"))
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with engine.connect() as connection:
        transaction = connection.begin()
        # API やサービスの commit・begin_nested が、
        # 外のトランザクションの中の SAVEPOINT になるように
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield db
        finally:
            db.close()
            transaction.rollback()


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> Iterator[Redis]:
    url = urlsplit(_require("REDIS_URL"))._replace(path=f"/{TEST_REDIS_DB}").geturl()
    # アプリの get_redis() も、テスト用の番号につなぐ
    monkeypatch.setenv("REDIS_URL", url)
    get_redis.cache_clear()
    client = get_redis()
    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()
        get_redis.cache_clear()


@pytest.fixture
def make_client(
    session: Session, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., TestClient]:
    """API を呼ぶクライアントを作る。開発用の API を試すときだけ app_env="development" にする。"""

    def make(app_env: str = "production") -> TestClient:
        monkeypatch.setenv("APP_ENV", app_env)
        app = create_app()
        app.dependency_overrides[get_session] = lambda: session
        # https にする（本番の設定では Cookie に Secure が付き、http では送られないため）
        return TestClient(app, base_url="https://testserver", headers={"X-Requested-With": "fetch"})

    return make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


@pytest.fixture
def facility(session: Session) -> Facility:
    # 施設は 1 つだけ（spec 002 の R-04）。手元と CI で、施設の数が変わらないように
    existing = session.scalars(select(Facility).order_by(Facility.id)).first()
    if existing is not None:
        return existing
    facility = Facility(name="テスト施設")
    session.add(facility)
    session.flush()
    return facility


# 架空の職員のログイン用の ID・家族のメールアドレスの番号
# （開発の初期データとぶつからないよう 9 万台から）
_numbers = itertools.count(90001)


@pytest.fixture
def make_staff(session: Session, facility: Facility) -> Callable[..., Staff]:
    """架空の職員を作る。返す Staff の user_id でログインでき、id が staff_id になる。"""

    def make(
        role: str = "care_worker", display_name: str = "テスト職員", language: str = "ja"
    ) -> Staff:
        user = User(
            kind="staff",
            login_id=f"s{next(_numbers):05d}",
            password_hash="x",
            language=language,
        )
        session.add(user)
        session.flush()
        staff = Staff(
            user_id=user.id, facility_id=facility.id, display_name=display_name, role=role
        )
        session.add(staff)
        session.flush()
        return staff

    return make


@pytest.fixture
def make_family(session: Session, facility: Facility) -> Callable[..., FamilyAccount]:
    """架空の入居者と、その家族を作る。

    返す FamilyAccount の user_id でログインでき、resident_id を持つ。
    """

    def make(display_name: str = "テストさんの母") -> FamilyAccount:
        number = next(_numbers)
        resident = Resident(
            facility_id=facility.id,
            name=f"架空 {number}",
            display_name=display_name,
            room=str(number),
        )
        user = User(kind="family", email=f"family{number}@example.test", password_hash="x")
        session.add_all([resident, user])
        session.flush()
        family = FamilyAccount(user_id=user.id, resident_id=resident.id)
        session.add(family)
        session.flush()
        return family

    return make


@pytest.fixture
def login_as(request: pytest.FixtureRequest) -> Callable[..., None]:
    """その user_id の人としてログインした状態にする（Redis に本物のセッションを作る）。

    make_client で作ったクライアントでは、`login_as(user_id, dev_client)` のように渡す。
    """

    def login(user_id: int, target: TestClient | None = None) -> None:
        # 渡されなかったときだけ client を作る（開発用のクライアントのテストで、本番用を作らない）
        if target is None:
            target = request.getfixturevalue("client")
        target.cookies.set(SESSION_COOKIE, create_session(user_id))

    return login
