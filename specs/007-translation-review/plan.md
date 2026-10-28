# Implementation Plan: 外国人職員が母国語で書いた様子を、整えた日本語で家族に届ける（D：翻訳・整文・訳し戻し・承認）

**Branch**: `docs/spec-007-plan` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/007-translation-review/spec.md`

## Summary

介護職員が母国語（インドネシア語・英語・日本語）で書いた「様子のメモ」を、AI がやさしい日本語に**整え**、整えた日本語を職員の言語に**訳し戻し**、
職員本人が確かめ、ほかのリーダーか施設長が**承認**してから、家族の連絡帳に出す（Constitution 原則 III の順番）。

AI へのつなぎ方は spec 004 の `inquiry/llm.py`（OpenRouter ＋ OpenAI Python SDK）を使い回す。設計の柱は次の 4 つ（詳しくは [research.md](./research.md)）。

1. **整える・訳し戻すは、別々に AI を呼ぶ**：訳し戻しの AI には原文を見せず、整えた日本語だけを渡す（原文に引っぱられず、整えた日本語が本当に何と言っているかが分かる）（R-02）
2. **「内容を足さない」は、人の目と機械の目の両方で守る**：本人の訳し戻しの確認・リーダーの承認に加えて、医療の言葉が増えた・長さが大きく変わったなどを機械で見つけて、注意の印を出す（R-03）
3. **状態の動きは、条件つきの 1 回の更新で進める**：同時に承認・戻す・取り下げる操作がぶつかってもずれない。本人は自分のメモを承認できない（R-05）
4. **家族に出すのは承認済みだけ**：家族の連絡帳・通知のまとめは、共通の関数 `get_disclosed_memos()`（承認済み かつ 開示設定で見せるもの）を必ず通す（R-07）

## Technical Context

**Language/Version**: Python 3.12、TypeScript 5（spec 001 と同じ）

**Primary Dependencies**: spec 001・spec 004 と同じ。新しいライブラリは足さない（AI は spec 004 で足す `openai` を使う）

**Storage**: PostgreSQL（様子のメモ・整えた履歴）。Redis は使わない

**Testing**: pytest（AI は spec 004 のテスト用の LLM（モック）に差し替える。FR-019）、Vitest。整える質（SC-003）は、評価のスクリプトで本物のモデルを手で流す（R-10）

**Target Platform**: spec 001 と同じ

**Project Type**: Web アプリケーション（`frontend/`・`backend/`）

**Performance Goals**: 「日本語にする」を押してから、整えた日本語と訳し戻しが出るまで 15 秒以内（10 回のうち 9 回。SC-001）。AI の呼び出しは 2 回（整える・訳し戻す）で、それぞれ 30 秒で打ち切る

**Constraints**:
- 承認されていないメモを、家族の連絡帳・通知のまとめ・問い合わせ AI のどこにも出さない（SC-004）
- 原文・訳し戻しは家族に出さない（SC-005）
- AI に入居者・家族の氏名やほかの記録を渡さない（FR-005）
- 自動テストで本物の AI を呼ばない（SC-007）

**Scale/Scope**: 外国人職員 3 人 × 担当の入居者 × 1 日 3 件まで → 多くて 1 日数十件。画面は職員向け 2（書く・承認待ちの一覧）、家族向けは spec 001 の連絡帳に足すだけ

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 の前

| 原則・制約 | 確認 | 結果 |
|---|---|---|
| I. 聞かずに知れる | 母を毎日見ている職員の気づきが、読みやすい日本語で連絡帳に届く | ✅ |
| II. 職員の入力負担を増やさない・割り込まない | 母国語で書けて、日本語で書くより手間が減る（SC-002）。承認待ちは通知・音なし、件数はリーダー・施設長だけ（FR-015）。外国人職員が母国語で入力できる手段（原則 II の SHOULD） | ✅ |
| III. 整文は記録に根拠がある内容に限る・承認の順番（例外なし） | AI は内容を足さない（FR-003）。訳し戻し → 本人の確認 → ほかのリーダー・施設長の承認 → 連絡帳、の順番を状態の動きで守る（FR-007〜013a）。原文・整えた日本語・訳し戻しを全部残す（FR-004） | ✅ |
| IV. 開示は施設が選ぶ | 「様子のメモ」を開示設定の記録項目にする（FR-012a）。家族に出す道は `get_disclosed_memos()` 1 つ | ✅ |
| V. 10 日間で動くもの | ミニマム版（Day 3）は「日本語にする」1 回まで。新しいライブラリなし | ✅ |
| 課題要件：プロンプトインジェクション | 原文は指示ではなくデータとして渡す（FR-006・R-04） | ✅ |
| 課題要件：セキュリティ・テスト・ログ | 文字としてのみ表示、LLM はモック、本番のログに文を出さない（FR-017〜019） | ✅ |

**違反なし**。

### Phase 1 のあと

| 確認したこと | 結果 |
|---|---|
| 家族に出す道（連絡帳・通知のまとめ）は `get_disclosed_memos()` を通り、`status = 'approved'` と開示設定の両方で絞る（[data-model.md](./data-model.md)） | ✅ |
| 問い合わせ AI（spec 004）は様子のメモを根拠にしない（spec 004 FR-002 は記録と返事だけ）。FR-012a の「問い合わせ AI に出さない」はそのまま満たす | ✅ |
| 承認する API は、書いた職員本人を受け付けない（[contracts/api.md](./contracts/api.md)） | ✅ |
| AI に渡すのは原文（または整えた日本語）と固定の指示だけ。入居者の呼び名も渡さない | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/007-translation-review/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api.md
├── checklists/
└── tasks.md             # /speckit-tasks で作る
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── memos/                    # 様子のメモ（みさき）
│   │   ├── prompts.py            # 整える・訳し戻すの指示（サーバーに固定）
│   │   ├── rewrite.py            # 整える・訳し戻す（spec 004 の inquiry/llm.py を使う）
│   │   ├── checks.py             # 機械の目（医療の言葉が増えた・長さ・名前など）
│   │   └── service.py            # 状態の動き・1 日 3 件・承認
│   ├── api/staff/memos.py        # 書く・整える・確かめる・取り下げる
│   ├── api/staff/memo_approvals.py # 承認待ちの一覧・承認・戻す・公開を取り下げる
│   ├── services/disclosure.py    # get_disclosed_memos() を足す（spec 001 のファイル。開示の判断はゆうの is_item_disclosed("memo") を呼ぶ）
│   └── models/memos.py
├── evals/memos/                  # 整える質の評価（本物のモデルで手で動かす）
└── tests/

frontend/src/
├── pages/staff/MemoEditor.tsx    # 書く・整える・訳し戻しを見る・確かめる
├── pages/staff/MemoApprovals.tsx # 承認待ちの一覧と詳細（リーダー・施設長）
└── i18n/ja.json ほか
```

**Structure Decision**: spec 004 の `inquiry/` と同じく、様子のメモは `backend/app/memos/` にまとめる。AI のクライアントは `inquiry/llm.py` を使い回す（spec 004 の T003）。

## 担当とつながり

| つなぎ目 | 作る人 → 使う人 | 内容 |
|---|---|---|
| `LLMClient`・テスト用の LLM（モック） | みさき（spec 004 T003・T004）→ みさき | 同じクライアントとテスト用の LLM（モック）を使う |
| 開示設定の記録項目 `memo` | ゆう → みさき | spec 001 の `disclosure_settings` に `target_code = 'memo'`（初期値は見せる）を足し、設定の画面に出す |
| `get_disclosed_memos(resident_id, date_from, date_to, *, approved_from, approved_to)` | みさき → さとこ | `services/disclosure.py` に足す。開示の判断はゆうの `is_item_disclosed("memo")`（001-T038。開示設定のキャッシュを読む）を呼び、ゆうが確かめる |
| 家族の連絡帳に「様子のメモ」を出す | さとこ | spec 001 の連絡帳（001-T055・001-T059）で `get_disclosed_memos()` を呼ぶ。そばに「職員が書いた内容を、AI で読みやすい日本語に整えています」 |
| 通知の選択肢とまとめ | さとこ | spec 001 の通知設定（001-T064）の `notify_items` に `memo` を足し、まとめ（001-T065）で承認日時でメモを数え、書いた日の連絡帳へのリンクを付ける |
| 「様子のメモを書く」ボタン・承認待ちの件数 | みさき → ゆう | ゆうの入居者を選んだあとの画面にボタンを置き、みさきの画面に進む。件数は `count_pending_memos(user)` をゆうの画面から呼ぶ（リーダー・施設長だけ、施設全体の件数） |

## ミニマム版と作り込み

| ミニマム版（Day 3） | 作り込み（Day 4〜） |
|---|---|
| メモのテーブル、書く（下書き）、「日本語にする」1 回（整えるだけ）、原文と整えた日本語を並べて見る。家族には出さない | 訳し戻し、直してやり直す、確かめる、取り下げる、1 日 3 件、承認待ちの一覧・承認・戻す・公開を取り下げる、機械の目の注意、開示設定・連絡帳・通知のまとめとのつなぎ目、評価 |

## 未決定のこと

| 項目 | 仮に置いた内容 | 決める場 |
|---|---|---|
| 整える・訳し戻すモデル | spec 004 の評価（T043）で「要約・整文用」を決めるときに一緒に決める。それまでは `OPENROUTER_MODEL` と同じ（R-01） | みさき |
| 1 つのメモで「日本語にする」をやり直せる回数 | 5 回（共有のキーを使い切らないため。R-08） | 評価のあとで見直す |
