"""Redis のつなぎ方（spec 001 の research.md R-12）。

キーの決まり（ログインのセッションとキャッシュを同じ Redis に入れるため）：
- キーの先頭に用途の接頭辞を付ける（`session:`・`cache:disclosure:`・`ratelimit:inquiry:` など）
- **必ず期限を付ける**（`set(key, value, ex=秒)`）。
  期限のないキーは、Redis がいっぱいになっても消されない
  （`maxmemory-policy volatile-lru` は、期限のあるキーだけを消すため）
"""

from functools import cache

from redis import Redis

from app.config import get_settings


@cache
def get_redis() -> Redis:
    """最初に使うときに 1 回だけ作る（Redis がなくても、import するだけなら動くように）。"""
    redis_url = get_settings().redis_url
    if not redis_url:
        raise RuntimeError("REDIS_URL が設定されていません（キー名は env.example）")
    # decode_responses：読んだ値を bytes ではなく str で返す
    return Redis.from_url(redis_url, decode_responses=True)
