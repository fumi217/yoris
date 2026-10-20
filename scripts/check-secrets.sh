#!/bin/sh
# .env・認証情報ファイル・トークンらしき値がコミットに含まれていないかを確認する。
# 判定のルールはこのファイルに置く（.claude/hooks と .githooks からはこれを呼ぶだけ）。
# 秘密ファイルの種類を増やしたら、.gitignore と .claude/settings.json の Read の deny もそろえる。
#
# 使い方:
#   sh scripts/check-secrets.sh                    ステージ済みの差分を確認する
#   sh scripts/check-secrets.sh HEAD               ステージ済み＋未ステージの変更を確認する
#   sh scripts/check-secrets.sh HEAD --untracked   上に加えて、未追跡のファイル（.gitignore 対象外）も確認する
#   sh scripts/check-secrets.sh A...B              指定した範囲の差分を確認する（CI 用）
#
# 終了コード: 0 = 問題なし / 1 = 見つかった / 2 = 使い方の誤り・git のエラー
# 見つかった値そのものは表示しない（チャットやログに秘密情報を出さないため）。

target="${1:---cached}"
untracked="$2"

usage() {
  echo "使い方: sh scripts/check-secrets.sh [--cached | HEAD | A...B] [--untracked]" >&2
  exit 2
}

case "$target" in
  --cached | HEAD) ;;
  *)
    printf '%s\n' "$target" | grep -qE '^[A-Za-z0-9_/][A-Za-z0-9_./^~-]*\.\.\.?[A-Za-z0-9_./^~-]+$' || usage
    ;;
esac
case "$untracked" in
  "" | --untracked) ;;
  *) usage ;;
esac

# コミットが1つもないリポジトリでは HEAD がないので、ステージ済みだけを見る（未ステージの追跡ファイルも存在しない）
if [ "$target" = HEAD ] && ! git rev-parse --verify -q HEAD >/dev/null; then
  target=--cached
fi

# 利用者の git 設定に左右されないよう、色・外部 diff・パスの引用・接頭辞を固定する
gitdiff() {
  git -c core.quotePath=false diff --no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ "$target" "$@"
}
fail_git() {
  echo "🚨 git の実行に失敗したため、確認できませんでした" >&2
  exit 2
}

# 未追跡のファイル（git add と git commit を1つのコマンドで実行する場合に備える。.gitignore の対象は除く）
new_files=""
if [ "$untracked" = --untracked ]; then
  new_files=$(git -c core.quotePath=false ls-files --others --exclude-standard) || fail_git
fi

# 1. ファイル名
names=$(gitdiff --name-only --diff-filter=d) || fail_git
names=$(printf '%s\n%s\n' "$names" "$new_files")

secret_files=$(printf '%s\n' "$names" \
  | grep -E '(^|/)(\.env($|\.)|credentials[^/]*\.json$|token\.json$|client_secret[^/]*\.json$|service[-_]?account[^/]*\.json$|[^/]*\.pem$|[^/]*\.p12$)' \
  | grep -v '\.env\.example$' | sort -u)
if [ -n "$secret_files" ]; then
  echo "🚨 .env または認証情報ファイルが含まれているため、コミットを止めました:" >&2
  printf '%s\n' "$secret_files" | sed 's/^/  /' >&2
  echo "外す: git restore --staged <ファイル名>（未追跡なら .gitignore に追加する）" >&2
  exit 1
fi

# 2. 追加された行の中身（「ファイル名<TAB>行」の形にしてから調べる）
diff_out=$(gitdiff -U0) || fail_git
added=$(printf '%s\n' "$diff_out" | awk '/^\+\+\+ /{ f = substr($0, 7); next } /^\+/{ print f "\t" substr($0, 2) }')
if [ -n "$new_files" ]; then
  # 未追跡のファイルは、テキストのファイルだけ全行を追加された行として扱う
  added_new=$(printf '%s\n' "$new_files" | while IFS= read -r f; do
    [ -f "$f" ] && grep -Iq . "$f" 2>/dev/null && awk -v f="$f" '{ print f "\t" $0 }' "$f"
  done)
  added=$(printf '%s\n%s\n' "$added" "$added_new")
fi


# 「キーと値の組み合わせ」で、値が環境変数・設定の参照になっている行は対象外（正しい書き方のため）
env_ref='[:=][[:space:]]*["'"'"']?(process\.env|import\.meta\.env|os\.|settings\.|config\.|env\.)'

tab=$(printf '\t')
found=""
# ルール: 名前<TAB>大文字小文字の区別（i = 区別しない / s = 区別する）<TAB>正規表現（ループの下のヒアドキュメント）
# macOS の /bin/sh（bash 3.2）は、$( ) の中のヒアドキュメントに ' があると構文エラーになるため、ループに直接渡す
while IFS="$tab" read -r name cs re; do
  if [ "$cs" = i ]; then opt=-iE; else opt=-E; fi
  hits=$(printf '%s\n' "$added" | cut -f2- | grep -n $opt -e "$re")
  if [ "$cs" = i ]; then
    hits=$(printf '%s\n' "$hits" | grep -viE -e "$env_ref")
  fi
  files=$(printf '%s\n' "$hits" | cut -d: -f1 | grep -E '^[0-9]+$' \
    | while read -r n; do printf '%s\n' "$added" | sed -n "${n}p" | cut -f1; done | sort -u)
  if [ -n "$files" ]; then
    # macOS の sed は UTF-8 の環境で日本語の置き換えが化けるため、printf で組み立てる
    found="$found$(printf '%s\n' "$files" | while IFS= read -r f; do printf '  %s（%s）\n' "$f" "$name"; done)
"
  fi
done <<'EOF'
キーと値の組み合わせ	i	(access[_-]?token|client[_-]?secret|api[_-]?key|refresh[_-]?token|signing[_-]?secret|webhook[_-]?secret|secret[_-]?key|session[_-]?secret)["']?[[:space:]]*[:=][[:space:]]*["']?[A-Za-z0-9+/=_.-]{16,}
Anthropic の API キー	s	sk-ant-[A-Za-z0-9_-]{20,}
OpenAI・OpenRouter の API キー	s	sk-(proj-|or-v1-)?[A-Za-z0-9_-]{32,}
Stripe のシークレットキー	s	(sk|rk)_(test|live)_[A-Za-z0-9]{20,}
Stripe の Webhook シークレット	s	whsec_[A-Za-z0-9]{20,}
Slack のトークン	s	xox[abposr]-[A-Za-z0-9-]{10,}
Slack の Webhook URL	s	hooks\.slack\.com/services/[A-Za-z0-9/]+
Google の API キー	s	AIza[0-9A-Za-z_-]{35}
Google のクライアントシークレット	s	GOCSPX-[A-Za-z0-9_-]{20,}
GitHub のトークン	s	gh[pousr]_[A-Za-z0-9]{36}
秘密鍵	s	-----BEGIN [A-Z ]*PRIVATE KEY-----
EOF

if [ -n "$found" ]; then
  echo "🚨 トークン・API キーらしき値が含まれているため、コミットを止めました（値は表示しません）:" >&2
  printf '%s' "$found" >&2
  echo "値は .env に書き、コードでは環境変数から読むように直してください。" >&2
  exit 1
fi

exit 0
