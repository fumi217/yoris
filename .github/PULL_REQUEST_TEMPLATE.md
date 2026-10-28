<!--
タイトルの形式: <type>(<scope>): #<Issue番号> <要約>（docs・chore は scope と Issue 番号を省いてよい）
例: feat(backend): #12 食事量の記録 API を追加 / docs: spec 001 の plan を追加
PR を作成したら、コメントに「@aitutor-review review」と書いて AI チューターにレビューを依頼する。
Approve のあとに指摘対応・main の取り込み・誤字修正をしたときは、何を変えたかをコメントに一言書けば再 Approve は不要。
動き・仕様・範囲を変えたときだけ、もう一度 Approve をもらう（.claude/skills/github-workflow/SKILL.md）。
-->

## 概要

<!-- 何を・なぜ変えたか。関係する spec・User Story・FR-・タスク番号 -->

Closes #

<!-- Issue の一部だけを進める PR は Refs # にする。Issue のない docs・chore の PR は消してよい -->

<!-- 関わる人は Reviewers に入れる（本文には書かない）。マージに必要なのは、そのうち誰か 1 名の Approve -->


## 変更内容

-

## チェックリスト

- [ ] `.env`・API キー・認証情報がコミットに含まれていない
- [ ] 実在の入居者・家族・職員の氏名・写真・記録が含まれていない（架空データだけを使っている）
- [ ] 差分が 1,100 行以内（`specs/` とロックファイルなどの自動生成ファイルは数えない。確かめ方は github-workflow スキルの「PR の大きさ」）
- [ ] constitution の原則 III（AI は医療判断をしない）・IV（開示の範囲）に反していない
- [ ] 技術選定（docs/技術選定.md）を変えた場合は、CLAUDE.md の「技術の前提」も合わせた（変えていなければチェック不要）
- [ ] CI（GitHub Actions）が緑
- [ ] （CI が動かないときだけ）理由と、手元で CI と同じコマンドを通した結果を書いた（`.claude/skills/github-workflow/SKILL.md` の「CI が動かないとき」）

## AI チューターレビューへの対応

<!-- 指摘ごとに「対応した / 対応しない（理由）」を書く -->
