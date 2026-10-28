# Implementation Plan: 家族の質問に、記録をもとに答える問い合わせ AI（F：問い合わせ AI エージェント）

**Branch**: `docs/spec-004-plan` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-inquiry-agent/spec.md`

## Summary

家族が「質問する」画面で AI と 1 本の会話を続け、AI は**その家族に開示された連絡帳の記録と職員の返事だけ**を調べて答える。
医療・苦情・お金など AI が答えてはいけない質問は、**質問の種類**を付けて職員の「家族からのメッセージ」に渡し、職員が「自分が対応する」で引き受けて、
定型文のボタン（＋短い書き足し）か電話で返す。苦情は生活相談員と施設長だけが見られる。

技術は技術選定 5 章のとおり、OpenRouter ＋ OpenAI Python SDK のツール呼び出しで、**ループは自前で書く**。設計の柱は次の 4 つ（詳しくは [research.md](./research.md)）。

1. **AI が見られる範囲は、サーバーが最初から絞る**：ツールは spec 001 の共通の関数（`get_disclosed_records`・`get_active_replies`）を通し、入居者はログイン中の家族から決める。AI に書き換えの操作はさせない（R-02・R-04）
2. **答えは「答えるツール」で返させ、根拠の id をサーバーが確かめる**：AI が調べていない記録を根拠にした答えは出さない（R-03）
3. **医療・苦情などは二重に守る**：言葉で引っかけて必ず職員に渡す決まり（サーバー側）と、AI の判断の両方（R-05）
4. **職員への引き継ぎは、条件つきの 1 回の更新で「最初の 1 人」を決める**：担当の引き受け・返事・家族の続きの書き込みが重なってもずれない（R-08）

## Technical Context

**Language/Version**: Python 3.12（バックエンド）、TypeScript 5（フロントエンド）。spec 001 と同じ

**Primary Dependencies**:
- バックエンド：FastAPI、SQLAlchemy 2、Alembic、Pydantic 2、redis-py、**openai**（OpenAI Python SDK。接続先を OpenRouter に向ける）
- フロントエンド：React 18（Vite）、React Router、TanStack Query、react-i18next（spec 001 と同じ）
- 新しく足すライブラリは `openai` だけ（技術選定の表にあり、R-01 に理由）

**Storage**:
- PostgreSQL：会話・発言・職員へのメッセージ・その履歴・返事の定型文
- Redis：家族ごと・施設全体の 1 日の発言の回数（R-07）

**Testing**: pytest ＋ httpx（AI はテスト用の LLM（モック）に差し替える。FR-030・SC-011）、Vitest、Playwright。
AI の答えの質（SC-002〜006）は、本物のモデルに質問の例を流す**評価のスクリプト**で確かめる（手で動かす。CI では動かさない。R-11）

**Target Platform**: spec 001 と同じ（Docker Compose ／ Render、`/api` は同じオリジンで中継） （10/28 の会議で決定：今回の開発ではデプロイしないので、Render の部分は作らない）

**Project Type**: Web アプリケーション（`frontend/`・`backend/`）

**Performance Goals**: 質問から答えまで 15 秒以内（10 回のうち 9 回。SC-001）。AI への 1 回の呼び出しは 30 秒で打ち切る（FR-026）

**Constraints**:
- 家族に出す道・AI に渡す道に、非開示の記録・ほかの入居者の記録を 1 件も入れない（SC-005）
- AI のサービスには、入居者・家族の氏名やメールアドレスを渡さない（呼び名だけ。FR-031）
- 自動テストで本物の AI を 1 回も呼ばない（SC-011）。学校配布の共有のキーを使い切らない（FR-024・FR-027）
- 苦情は、生活相談員・施設長以外には、あるかどうかも分からないようにする（404。FR-018）

**Scale/Scope**: 家族アカウント 30、1 家族 1 日 10 回 → 施設全体で多くて 1 日 300 回の質問。画面は家族向け 1（質問する）、職員向け 2（一覧・詳細）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 の前

| 原則・制約 | 確認 | 結果 |
|---|---|---|
| I. 聞かずに・遠慮せずに知れる | 事務所の時間に関係なく、自分の言葉で質問でき、記録から答えが返る。答えられないものは職員に渡ったことが分かり、返事も同じ会話に届く | ✅ |
| II. 職員の入力負担を増やさない・割り込まない | 記録で答えられる質問に職員の入力はない。職員への通知・音は出さない（FR-013）。返事は定型文のボタンで 3 タップ以内（FR-014）。だれが対応するかは職員が決める（3.0.0 の原則 II） | ✅ |
| III. AI は医療判断をせず、記録にないことは答えない（例外なし） | 医療・服薬・体調の解釈は答えず職員に渡す（FR-009）。言葉による決まりとの二重の守り（R-05）。答えの根拠の id をサーバーが確かめ、保存する（FR-004・R-03）。緊急は電話を案内（Edge Cases） | ✅ |
| IV. 開示は施設が選ぶ | AI のツールは spec 001 の共通の関数を通す（FR-002）。入居者はサーバーがログイン中の家族から決める（FR-020） | ✅ |
| V. 10 日間で動くもの | ミニマム版（Day 2〜4）は US1・US2 の正常な流れとツール 2〜3 個、US4 の 1 日の回数の制限（学校の共有キーを使い切らないため）。US3 の攻撃の例の評価は作り込み。課題要件の MUST（F）を 1 週目に動かす | ✅ |
| 課題要件：AI Agent | ツール呼び出しのループ（自前）で、記録を調べる・職員に渡す・答える、を AI が選ぶ | ✅ |
| 課題要件：プロンプトインジェクション（ADVANCE だが F では MUST） | 入力はデータとして扱う、AI が見られる範囲をサーバーで絞る、書き換えの操作をさせない、攻撃の例 10 件以上で評価（FR-019〜023・R-04） | ✅ |
| 課題要件：キャッシュサーバー | Redis を回数の制限に使う（spec 001 のセッション・開示設定に加えて） | ✅ |
| 課題要件：セキュリティ・テスト・ログ | AI の答え・職員の返事は文字として表示。LLM はモック。本番のログに発言・記録・氏名を出さない（FR-028〜031） | ✅ |
| 利用者と権限 | 家族・職員を分け、苦情は生活相談員・施設長だけ（FR-012・FR-018） | ✅ |

**違反なし**。

### Phase 1 のあと（設計後の確認）

| 確認したこと | 結果 |
|---|---|
| AI のツールは、記録・返事を spec 001 の共通の関数からだけ読む。ツールの引数に入居者 id がない（[contracts/agent-tools.md](./contracts/agent-tools.md)） | ✅ |
| AI に渡すツールは読み取りと「渡す」「答える」だけで、データを書き換えるツールがない | ✅ |
| 苦情の見え方を 1 つの関数（`visible_staff_messages`）に集め、一覧・件数・詳細・操作のすべてがそこを通る（[data-model.md](./data-model.md)） | ✅ |
| 家族への返事のお知らせは spec 001 の仕組み（`notifications`・`email_outbox`）を使い、メールに中身を入れない | ✅ |
| 新しいライブラリは `openai` だけ | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/004-inquiry-agent/
├── spec.md
├── plan.md              # この文書
├── research.md          # 調べて決めたこと（Phase 0）
├── data-model.md        # テーブルの形・状態の動き（Phase 1）
├── quickstart.md        # 動かし方と確認の手順（Phase 1）
├── contracts/
│   ├── api.md           # 画面と API の決まりごと
│   └── agent-tools.md   # AI に渡すツールの決まりごと
├── checklists/
└── tasks.md             # /speckit-tasks で作る
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── inquiry/                 # 問い合わせ AI（みさき）
│   │   ├── llm.py               # OpenRouter のクライアント（差し替えられる形。テストはモック）
│   │   ├── prompts.py           # AI への指示（サーバーに固定。家族に出さない）
│   │   ├── tools.py             # ツールの定義と実行（spec 001 の共通の関数を呼ぶ）
│   │   ├── agent.py             # 自前のループ（上限 5 回・30 秒）
│   │   ├── guard.py             # 言葉による決まり（医療・苦情などは必ず渡す）
│   │   ├── ratelimit.py         # 1 日の回数（Redis）
│   │   ├── service.py           # 会話・発言・職員へのメッセージの保存、担当・返事
│   │   └── visibility.py        # 苦情の見え方（visible_staff_messages）
│   ├── api/
│   │   ├── family/inquiry.py    # 家族の「質問する」
│   │   └── staff/messages.py    # 職員の「家族からのメッセージ」
│   ├── models/inquiry.py        # テーブル
│   └── seed/inquiry.py          # 返事の定型文（質問の種類ごと）
├── evals/inquiry/               # 評価の質問の例と、評価のスクリプト（本物のモデルで手で動かす）
└── tests/
    ├── unit/test_inquiry_*.py
    └── api/test_inquiry_*.py

frontend/src/
├── pages/family/Inquiry.tsx         # 質問する（会話）
├── pages/staff/FamilyMessages.tsx   # 家族からのメッセージの一覧（職員の画面 /staff/messages と、管理画面 /admin/messages の両方から開く）
├── pages/staff/FamilyMessage.tsx    # 詳細・担当・返事（同じく両方から。一覧と詳細は、開いた側の URL の下でつなぐ）
└── i18n/ja.json ほか                # 文言・質問の種類・返事の定型文
```

**Structure Decision**: spec 001 の構成（`backend/app/api/<利用者>/`・`services/`・`models/`）に合わせ、AI まわりの部品は `backend/app/inquiry/` にまとめる。
spec 007（D：翻訳）からも `inquiry/llm.py` を使い回せるようにする。

## 担当とつながり

| つなぎ目 | 作る人 → 使う人 | 内容 |
|---|---|---|
| `get_disclosed_records`・`get_active_replies` | ゆう → みさき | AI のツールの中から呼ぶ（spec 001 T038・T054） |
| `CurrentUser`・役割のチェック | ようこ → みさき | 家族か職員か、職員の役割（spec 001 T010） |
| 対応待ちの件数を数える関数 `count_waiting_staff_messages(session, user, resident_id=None)`・入居者ごとに 1 回で数える `count_waiting_staff_messages_by_resident(session, user)` | みさき → ゆう | 職員の入居者一覧（spec 001 T028・T053）から呼ぶ |
| 職員の返事のお知らせ `create_staff_message_reply_notice(session, staff_message_id)` | さとこ → みさき | spec 001 の `notifications` に種類 `staff_message_reply` と列 `staff_message_id` を足し（通知設定に関係なく送る）、`email_outbox` に「施設からメッセージの返事が届きました」を作る（R-09） |
| OpenRouter のキー・モデル名の環境変数 | みさき → ようこ | `env.example` にはもうある（`OPENROUTER_API_KEY`・`OPENROUTER_MODEL`） |

## ミニマム版と作り込み

| ミニマム版（Day 2〜4） | 作り込み（Day 5〜） |
|---|---|
| 会話（家族が送る・AI が答える・見返す）、ツール 3 つ（記録を調べる・返事を調べる・答える）＋渡す、根拠の確かめ、言葉による決まり、職員の一覧と詳細（直前 3 往復）、「自分が対応する」、定型文で返事、苦情の見え方（最初から）、件数の関数、1 日の回数の制限 | 電話で対応した、種類の付け替え、担当を外す・変える、家族の続きの書き込みで対応待ちに戻す、同じ内容の重複、24 時間・3 日の表示、AI が止まったときの案内、攻撃の例の評価、モデルの比較 |

## 未決定のこと

| 項目 | 仮に置いた内容 | 決める場 |
|---|---|---|
| 使うモデル | 評価のスクリプトで 5 つのモデルを比べて決める。それまでは `openai/gpt-oss-120b` を仮に使う（R-10） | みさき（Day 3 までに） |
| 施設全体の 1 日の上限 | 300 回（家族 30 × 10 回）。共有のキーの上限が分かったら見直す（R-07） | みさき |
| AI に渡す直近のやりとり | 直近の 6 往復（R-06） | 評価の結果で見直す |
| 技術選定・CLAUDE.md の「相談員に回す」 | このPRで「質問の種類を付けて職員に渡す」に直す。PRD（#28）は、マージ後に合わせる | みさき |
