"""エラーのコードと HTTP の番号の対応に、足し忘れがないこと（T012）。"""

from app.errors import STATUS_CODES, ErrorCode


def test_every_error_code_has_a_status_code():
    assert set(STATUS_CODES) == set(ErrorCode)
