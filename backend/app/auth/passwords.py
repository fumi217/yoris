"""パスワードの決まりとハッシュ（spec 002 の T007・spec 001 の research.md R-03）。

決まり（職員・家族・施設長のすべてで共通。spec 002 の申し込みページも同じ）：
- 8 文字以上、64 文字まで。文字の種類の組み合わせ（大文字・数字・記号など）は求めない
- よく使われるパスワード・漏れたパスワードの一覧（`common_passwords.txt.gz`）にあれば使わせない
- 使える文字は、半角の英数字と記号（空白も含む）だけ。かな・全角は使わせない
  （日本語の入力のまま打った全角の文字などで、ログインできなくなるのを防ぐ。
  半角だけなら 64 文字で 64 バイトなので、bcrypt の 72 バイトの上限も超えない）

一覧の出どころ：SecLists（MIT ライセンス。著作権の表示とライセンスの文は、
隣の `common_passwords.LICENSE.txt`）の
`Passwords/Common-Credentials/100k-most-used-passwords-NCSC.txt`
（イギリスの NCSC が、漏れたパスワードから作った上位 10 万件）。
決まりで弾かれない 8〜64 文字のものだけを残し、小文字にそろえて並べた（46,483 件）。
照らし合わせも小文字で行う。4.6 万行あり、PR の差分で読み切れないので、gzip で圧縮して置く（#65）。
中身が差し替えられていないかは、元のファイルから次のように作り直し、
`zcat common_passwords.txt.gz | sha256sum` と比べて確かめられる（どちらも 20696c50…aca656 になる）:

    out = set()
    for raw in open("100k-most-used-passwords-NCSC.txt", "rb").read().splitlines():
        try:
            line = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            continue
        if 8 <= len(line) <= 64:
            out.add(line.lower())
    sys.stdout.write("".join(x + "\\n" for x in sorted(out)))  # これを sha256sum に渡す

ログイン（001-T022）・職員のアカウント（001-T088）・家族の招待（001-T089）・申し込み（002）が使う。
"""

import gzip
import secrets
import string
from functools import cache
from pathlib import Path

import bcrypt

from app.errors import AppError, ErrorCode

MIN_LENGTH = 8
MAX_LENGTH = 64
MAX_BYTES = 72
# bcrypt の計算の重さ（2 の 12 乗回）。上げるほど、盗まれたハッシュを破るのに時間がかかる
BCRYPT_ROUNDS = 12

_COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt.gz")


@cache
def _common_passwords() -> frozenset[str]:
    with gzip.open(_COMMON_PASSWORDS_FILE, "rt", encoding="utf-8") as file:
        return frozenset(file.read().splitlines())


def password_problem(password: str) -> str | None:
    """決まりに合わない理由を返す。合っていれば None。"""
    if len(password) < MIN_LENGTH:
        return "too_short"
    if len(password) > MAX_LENGTH:
        return "too_long"
    if not all(" " <= char <= "~" for char in password):
        return "invalid_characters"
    if password.lower() in _common_passwords():
        return "too_common"
    return None


def validate_password(password: str) -> None:
    """決まりに合わなければ 422 `validation_error`（新しいパスワードを決めるときに使う）。"""
    if password_problem(password) is not None:
        raise AppError(ErrorCode.VALIDATION_ERROR)


def hash_password(password: str) -> str:
    """bcrypt のハッシュにする。決まりを確かめてから呼ぶ。"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("ascii")


# 初期パスワードに使う文字（半角の英数字。紙や口で伝えるときに読み違えやすい 0・O・1・l・I は除く）
_INITIAL_PASSWORD_CHARS = "".join(
    c for c in string.ascii_letters + string.digits if c not in "0O1lI"
)
INITIAL_PASSWORD_LENGTH = 8


def generate_initial_password() -> str:
    """職員のアカウントを作るときの初期パスワードを、暗号用の乱数で作る（001-T088）。

    決まり（8 文字以上・よく使われるものは不可）に通るものだけを返す
    （一覧に当たった場合は作り直す）。
    """
    while True:
        password = "".join(
            secrets.choice(_INITIAL_PASSWORD_CHARS) for _ in range(INITIAL_PASSWORD_LENGTH)
        )
        if password_problem(password) is None:
            return password


@cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def verify_password(password: str, password_hash: str | None) -> bool:
    """パスワードがハッシュと合うか。

    ハッシュがない（その ID の人がいない）とき・ログインできない値（初期データの `!` など、
    bcrypt のハッシュでないもの）のときも、ダミーのハッシュで同じだけ計算してから False を返す
    （答えが返るまでの時間で、ID があるかどうかを知られないように。PR #199 みさき）。
    """
    encoded = password.encode("utf-8")
    if len(encoded) > MAX_BYTES:
        # bcrypt は 72 バイトを超えると受け付けない（決まりで作ったハッシュとは合わない）
        return False
    if password_hash is not None:
        try:
            return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))
        except ValueError:
            pass
    bcrypt.checkpw(encoded, _dummy_hash().encode("ascii"))
    return False
