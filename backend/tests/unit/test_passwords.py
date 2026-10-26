"""パスワードの決まりとハッシュ（spec 002 の T007・T008、spec 001 の research.md R-03）。"""

import pytest

from app.auth import passwords
from app.auth.passwords import hash_password, password_problem, validate_password, verify_password
from app.errors import AppError, ErrorCode


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    # テストでは計算を軽くする（決まりの確かめには関係しない）
    monkeypatch.setattr(passwords, "BCRYPT_ROUNDS", 4)


def test_seven_characters_is_too_short():
    assert password_problem("abcdefg") == "too_short"


def test_eight_characters_without_symbols_is_ok():
    # 文字の種類の組み合わせは求めない
    assert password_problem("kumoyama") is None


def test_sixty_four_characters_is_ok_and_sixty_five_is_too_long():
    assert password_problem("a" * 63 + "b") is None
    assert password_problem("a" * 64 + "b") == "too_long"


def test_common_password_list_is_the_one_we_built():
    # 一覧は圧縮していて PR の差分で中身が見えないので、
    # 空になったり、すり替わったりしていないかを確かめる（作り直し方は app/auth/passwords.py）
    common = passwords._common_passwords()
    assert len(common) == 46483
    assert {"password", "12345678", "iloveyou", "qwertyuiop"} <= common
    assert all(8 <= len(p) <= 64 and p == p.lower() for p in common)


def test_common_password_is_rejected_ignoring_case():
    assert password_problem("password") == "too_common"
    assert password_problem("PassWord1") == "too_common"


@pytest.mark.parametrize("password", ["くもやまそらうみ", "kumoyamaＡ", "kumo　yama"])
def test_kana_and_full_width_are_rejected(password):
    # かな・全角の英字・全角の空白
    assert password_problem(password) == "invalid_characters"


def test_half_width_symbols_and_space_are_ok():
    assert password_problem("kumo yama!~") is None


def test_validate_password_raises_validation_error():
    with pytest.raises(AppError) as error:
        validate_password("short")
    assert error.value.code == ErrorCode.VALIDATION_ERROR


def test_hash_and_verify():
    password_hash = hash_password("kumoyama-sora")

    assert password_hash.startswith("$2b$")
    assert verify_password("kumoyama-sora", password_hash)
    assert not verify_password("kumoyama-umi", password_hash)


def test_same_password_gets_different_hashes():
    # ソルトが毎回変わる（同じパスワードの人がいても、ハッシュからは分からない）
    assert hash_password("kumoyama-sora") != hash_password("kumoyama-sora")


def test_values_that_are_not_bcrypt_hashes_never_match():
    # 初期データの「ログインできない値」・テストの仮の値・その人がいないとき
    assert not verify_password("!", "!")
    assert not verify_password("x", "x")
    assert not verify_password("kumoyama-sora", None)


@pytest.mark.parametrize("password_hash", [None, "!"])
def test_missing_or_unusable_hash_still_does_the_dummy_calculation(monkeypatch, password_hash):
    # ID がない人・パスワードのない人も、同じだけ計算してから答える
    # （時間の差で ID の有無を知られない。PR #199 みさき）
    calls = []
    real = passwords._dummy_hash
    monkeypatch.setattr(passwords, "_dummy_hash", lambda: calls.append(1) or real())

    assert not verify_password("kumoyama-sora", password_hash)
    assert calls == [1]


def test_over_72_bytes_never_matches():
    assert not verify_password("あ" * 25, hash_password("kumoyama-sora"))
