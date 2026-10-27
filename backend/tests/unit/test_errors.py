"""エラーのコードと HTTP の番号・画面の文言の対応に、足し忘れがないこと（T012）。"""

import json
from pathlib import Path

from app.errors import STATUS_CODES, ErrorCode


def test_every_error_code_has_a_status_code():
    assert set(STATUS_CODES) == set(ErrorCode)


# フロントの辞書。CI はリポジトリ全体を取ってくるので backend/ から見て ../frontend、
# 手元の Docker は docker-compose.yml で /frontend/src/i18n に読むだけで見せている
# （どちらも同じ形で届く）
JA_JSON = Path(__file__).resolve().parents[3] / "frontend" / "src" / "i18n" / "ja.json"


def test_every_error_code_has_a_message_in_ja_json():
    # 文言がないと、画面に error.<code> のようなキーがそのまま出る（#168・#62）
    assert JA_JSON.exists(), (
        f"{JA_JSON} がありません。辞書を移したらここも直す。"
        "手元では docker compose up -d で backend を作り直す（辞書のフォルダを見せる設定が入る）"
    )

    messages = json.loads(JA_JSON.read_text(encoding="utf-8")).get("error", {})
    missing = sorted(
        code.value
        for code in ErrorCode
        if not (isinstance(messages.get(code), str) and messages[code].strip())
    )

    assert missing == [], f"ja.json の error に文言がないコード：{missing}"


def test_details_are_added_only_when_given():
    # 画面が文言に使う値（件数など）だけを details で返す（面会の visit_day_has_reservations など）
    import json

    from app.errors import error_response

    plain = json.loads(error_response(ErrorCode.NOT_FOUND).body)
    with_count = json.loads(
        error_response(ErrorCode.VISIT_DAY_HAS_RESERVATIONS, details={"count": 2}).body
    )

    assert plain == {"error": {"code": "not_found", "message_key": "error.not_found"}}
    assert with_count["error"]["details"] == {"count": 2}
