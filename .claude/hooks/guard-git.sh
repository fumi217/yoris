#!/bin/bash
# Claude が git を実行する直前に、次の2つを確認する。.claude/settings.json の PreToolUse から呼ばれ、clone するだけで全員の Claude に効く。
#   1. git commit: scripts/check-secrets.sh で秘密情報が含まれていないか
#   2. git push: main への push・強制 push でないか（ブランチ保護が使えないプランのため、ここで止める）
# ホストに jq などがなくても動くよう、標準入力の JSON は grep で取り出す。
# 対応しないもの: git のエイリアス（git ci など）、引用符で囲んだ場所への cd（CLAUDE.md の「hook を回避しない」で補う）

input=$(cat)

# JSON から文字列の値を取り出す（エスケープは解かないが、判定と cd には足りる）
json_value() {
  printf '%s' "$input" | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*\"([^\"\\\\]|\\\\.)*\"" | head -1 \
    | sed -E "s/^\"$1\"[[:space:]]*:[[:space:]]*\"//; s/\"\$//"
}

cmd=$(json_value command)

# コマンドの先頭（行頭・&&・;・| などの直後）にある git の、サブコマンドが commit・push のときだけ対象にする
# （git -c x=y commit のようなオプションは許す）。文章の途中の「git push」（コミットメッセージ・PR 本文など）には反応しない。
# JSON の中では改行が \n という2文字になっているので、それも行頭として扱う
cmd_start='(^|[;&|(`]|\\n)[[:space:]]*'
git_sub="${cmd_start}git([[:space:]]+(-[cC][[:space:]]+[^[:space:]]+|-[^[:space:]]+))*[[:space:]]+"
is_commit=false
is_push=false
printf '%s' "$cmd" | grep -qE "${git_sub}commit\\b" && is_commit=true
printf '%s' "$cmd" | grep -qE "${git_sub}push\\b" && is_push=true
[ "$is_commit" = true ] || [ "$is_push" = true ] || exit 0

# コマンドが実行される場所（cwd）で確認する。取り出せなければプロジェクトの場所を使う
cwd=$(json_value cwd)
cd "$cwd" 2>/dev/null || cd "$CLAUDE_PROJECT_DIR" || exit 2

# コマンドの中で git の前に cd していれば（cd ../section9-xxx && git push など）、その場所で確認する。git -C <場所> も同じ。
# git worktree で別の場所に作業ブランチを置くと、Claude の cwd は main のままのことがある。section8 ではこれを見ずに
# cwd のブランチ（main）で判定したため、作業ブランチへの push まで止まっていた（秘密情報の確認も別の場所を見ていた）
path_token='[^;&|[:space:]\\"]+'
printf '%s\n' "$cmd" | grep -oE "${cmd_start}cd[[:space:]]+${path_token}|${git_sub}(commit|push)\\b" | while IFS= read -r m; do
  if printf '%s' "$m" | grep -qE "${cmd_start}cd[[:space:]]"; then
    printf 'cd\t%s\n' "$(printf '%s' "$m" | sed -E 's/^.*cd[[:space:]]+//')"
  else
    printf 'git\t%s\n' "$(printf '%s' "$m" | grep -oE -- "-C[[:space:]]+${path_token}" | tail -1 | sed -E 's/^-C[[:space:]]+//')"
    break
  fi
done > "${TMPDIR:-/tmp}/guard-git.$$"
while IFS="$(printf '\t')" read -r kind d; do
  [ -n "$d" ] || continue
  d=$(printf '%s' "$d" | sed -E "s/^'(.*)'\$/\\1/; s#^~(/|\$)#$HOME\\1#")
  cd "$d" 2>/dev/null || true
done < "${TMPDIR:-/tmp}/guard-git.$$"
rm -f "${TMPDIR:-/tmp}/guard-git.$$"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# 1. main への push を止める（main を明示した push と、main にいるときの送り先を書かない git push）
if [ "$is_push" = true ]; then
  # push の引数だけを見る（次の区切り記号・改行（JSON では \n）まで）
  push_args=$(printf '%s' "$cmd" | grep -oE "${git_sub}push\\b[^|;&\\\\]*" | head -1)
  # オプション（-u など）とリダイレクト（2>&1 など）を除いた引数。1つ目はリモート名、2つ目以降が送るブランチ
  set -f
  refspecs=""
  n=0
  for t in ${push_args#*push}; do
    case "$t" in -* | *'>'* | *'<'*) continue ;; esac
    n=$((n + 1))
    [ "$n" -ge 2 ] && refspecs="$refspecs $t"
  done
  set +f
  to_main=false
  if [ -z "$refspecs" ]; then
    # 送り先を書かない git push / git push origin は、今のブランチを送る
    [ "$(git branch --show-current)" = main ] && to_main=true
  else
    for r in $refspecs; do
      dst=${r#+}
      dst=${dst##*:}
      [ "$dst" = HEAD ] && dst=$(git branch --show-current)
      case "$dst" in main | refs/heads/main) to_main=true ;; esac
    done
  fi
  if [ "$to_main" = true ]; then
    echo "🚨 main への push は禁止です。作業ブランチを作り、PR を出してください（github-workflow スキル）" >&2
    exit 2
  fi
  # 強制 push を止める（オプションの位置に関係なく。--force-with-lease、-uf のようなまとめ書き、+ブランチ名 の形も含む）
  if printf '%s' "$push_args" | grep -qE '[[:space:]](--force(-with-lease|-if-includes)?(=[^[:space:]]*)?|-[a-zA-Z]*f[a-zA-Z]*|\+[^[:space:]]+)([[:space:]]|$)'; then
    echo "🚨 強制 push は禁止です。履歴を書き換える必要がある場合は、ユーザーに相談してください" >&2
    exit 2
  fi
fi

# 2. コミットに秘密情報が含まれていないかを確認する
#   - git commit <ファイル名> や -a は未ステージの変更もコミットするため、HEAD との差分を見る
#   - git add <ファイル> && git commit を1つのコマンドで実行すると、hook の時点ではまだ未追跡なので、未追跡のファイルも見る
#   - .githooks を有効にしていても --no-verify で飛ばされるので、ここは常に実行する
# check-secrets.sh は 1 か 2 を返すが、Claude の hook は exit 2 でないとコマンドを止めない
if [ "$is_commit" = true ]; then
  sh "$CLAUDE_PROJECT_DIR/scripts/check-secrets.sh" HEAD --untracked || exit 2
fi

exit 0
