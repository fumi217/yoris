# Implementation Plan: 施設がアプリの月額利用料を支払う（J：システム利用料）

**Branch**: `docs/spec-002-billing` | **Date**: 2026-10-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-billing/spec.md`

## Summary

施設長が、ログインなしで開ける申し込みページで施設名・名前・連絡用のメールアドレス・パスワードを入れ、
Stripe の支払い画面（Checkout）でカードで払うと、Stripe からの知らせ（Webhook）を確かめたうえで、施設・施設長のアカウント・契約ができて「契約中」になる。
作り込みで、契約の状態の表示、ID を書いたメール、申し込み直し、カードの変更・解約・請求の履歴（Stripe の Customer Portal）を足す。

設計の柱は次の 3 つ（詳しくは [research.md](./research.md)）。

1. **カード情報に触れない**：支払いも、カードの変更も、領収書も Stripe の画面で行う（Checkout・Customer Portal。R-01・R-10）
2. **アカウントは Stripe の知らせを確かめてから作る**：署名を確かめ、同じ知らせは 1 回だけ処理し、順番が入れ替わっても Stripe から今の状態を読み直して合わせる（R-03・R-04）
3. **施設は 1 つだけ**：施設を作る処理を DB のロックで 1 つずつにし、2 つ目は作らない（R-04）。初期データとは「施設があればそれを使う」で両立する

## Technical Context

**Language/Version**: Python 3.13（バックエンド）、TypeScript 6・Node 24（フロントエンド）。spec 001 と同じ（技術選定 7 章）

**Primary Dependencies**:
- spec 001 の依存（FastAPI・SQLAlchemy・Alembic・redis-py・structlog・bcrypt など）
- **`stripe`**（Stripe の公式 Python ライブラリ。この spec で足す。R-01）
- 開発だけ：Stripe CLI（`stripe/stripe-cli` のコンテナ。Webhook を手元に転送する。R-11）

**Storage**:
- PostgreSQL：契約・申し込み・受け取った知らせ・状態の履歴（[data-model.md](./data-model.md)）
- Redis：作り込みで、申し込みの回数の制限（`ratelimit:signup:<接続元>`。spec 001 の research.md R-12 の決まりどおり期限を付ける）
- カード情報・領収書は Stripe に置き、アプリには持たない

**Testing**: pytest（Stripe のライブラリはモック。Webhook はテスト用の秘密で署名を作って送る。R-11）、Vitest（申し込みページの入力の確かめ）

**Target Platform**: spec 001 と同じ（Docker Compose、本番は Render）。Stripe CLI は `stripe` の profile で、決済を試すときだけ起動する

**Project Type**: Web アプリケーション（`frontend/`・`backend/`）

**Performance Goals**:
- 支払いを終えてから 1 分以内に「契約中」になる（SC-002。Webhook は数秒で届き、完了の画面は数秒ごとに読み直す）
- 申し込みページを開いてからログインまで 5 分以内（SC-001）

**Constraints**:
- カード番号・パスワードを、アプリの画面・DB・ログのどこにも残さない（SC-005・SC-007）
- Stripe には施設名と連絡用のメールアドレスだけを渡す（FR-025・SC-010）
- 開発・デモは Stripe のテスト環境だけ（FR-024）。自動テストは Stripe を呼ばない

**Scale/Scope**: 施設 1 つ、プラン 1 つ。画面は、申し込みページ・申し込み完了・利用料のお支払い（管理画面）の 3 つ

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Phase 0 の前

| 原則・制約 | 確認 | 結果 |
|---|---|---|
| I. 家族が聞かずに・遠慮せずに知れる | 家族が直接使う機能ではない。支払いに失敗・解約しても、家族は今までどおり使え、利用料の案内も出さない（FR-017） | ✅（家族の体験を変えない） |
| II. 職員の入力負担を増やさない | 職員の入力はない。利用料の画面は施設長・事務員だけ | ✅ |
| III. AI は医療判断をしない | AI を使わない | ✅（対象外） |
| IV. 開示は施設が選ぶ | 入居者・家族・記録の情報を Stripe に渡さない（FR-025）。利用料の画面は家族に存在も知らせない（FR-007） | ✅ |
| V. 10 日間で動くものを優先 | ミニマム版（Day 3）は US1 の「申し込んで払えて、契約中になる」まで。決済は Stripe のテストモードで実際に組み込む（原則 V の決済の例外）。増えるライブラリは `stripe` だけ（公式・情報が多い） | ✅ |
| UI 方針 | 利用料のお支払いは辞書とふりがなに従う。申し込みページ・完了は、constitution 3.1.0 の例外でふりがなを付けない（辞書は `{漢字|かな}` を使わない）。Stripe の画面は対象外（spec の Assumptions） | ✅ |
| 利用者と権限 | 申し込みはログインなし。利用料の画面と操作は施設長・事務員だけ（FR-007、[contracts/api.md](./contracts/api.md)） | ✅ |
| 個人情報 | 架空の施設とテスト用のカードだけを使う。パスワードはハッシュだけを持ち、アカウントを作ったら申し込みの行から消す | ✅ |
| 課題要件：決済 | Stripe Billing のテストモードで、Checkout・Webhook（署名の確認）・Customer Portal を使う | ✅ |
| 課題要件：セキュリティ | 入力は React の通常の表示だけで出す。SQL は ORM。Webhook は署名を確かめる。申し込みページの書き込みにも `X-Requested-With` を当てる（FR-027） | ✅ |
| 課題要件：キャッシュ | この spec ではキャッシュを足さない。作り込みの回数の制限で Redis を使う | ✅ |
| 課題要件：テスト・ログ | pytest で SC-003〜SC-009 を確かめる。ログには id と種類だけを出す（R-13） | ✅ |

**違反なし**。Complexity Tracking は空。

### Phase 1 のあと（設計後の確認）

| 確認したこと | 結果 |
|---|---|
| アカウントを作る道は Webhook の処理 1 か所だけで、署名の確認と、同じ知らせの確認を通る（[research.md R-03・R-04](./research.md)） | ✅ |
| `billing_events` に知らせの本文を保存しない。パスワードのハッシュは、アカウントを作ったら申し込みの行から消す（[data-model.md](./data-model.md)） | ✅ |
| 管理画面の API は施設長・事務員だけ。家族向けの画面の行き先に利用料の画面がない（[contracts/api.md](./contracts/api.md)） | ✅ |
| Stripe の顧客には施設名とメールアドレスだけを渡す。メタデータに入居者・家族の情報を入れない | ✅ |
| 増えたライブラリは `stripe` だけで、10 日間で使える根拠を research.md R-01 に書いた | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/002-billing/
├── spec.md              # 仕様（/speckit-specify・clarify）
├── plan.md              # この文書
├── research.md          # 調べて決めたこと（Phase 0）
├── data-model.md        # テーブルの形・状態の動き（Phase 1）
├── quickstart.md        # 動かし方と、通しの確認手順（Phase 1）
├── contracts/
│   └── api.md           # API の一覧と決まりごと（Phase 1）
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks で作る（この plan では作らない）
```

### Source Code (repository root)

spec 001 の構成（[plan.md](../001-family-priority-report/plan.md#project-structure)）に足すものだけを書く。

```text
backend/
├── app/
│   ├── api/
│   │   ├── billing.py          # 申し込みページの API と Webhook の受け口（ログインなし）
│   │   └── admin/billing.py    # 利用料のお支払い（施設長・事務員）
│   ├── services/
│   │   └── billing.py          # Checkout・Customer Portal の作成、知らせの処理、施設とアカウントを作る処理、状態の対応表
│   ├── models/
│   │   └── billing.py          # facility_subscriptions・subscription_status_histories・billing_applications・billing_events
│   └── auth/
│       └── login_ids.py        # ログイン用の ID を作る（基盤。職員のアカウント・初期データと共通。R-06）
└── tests/api/
    ├── test_billing_signup.py
    └── test_billing_webhook.py

frontend/src/pages/
├── signup/
│   ├── Signup.tsx              # 申し込みページ
│   └── SignupComplete.tsx      # 申し込み完了（ID を出す）
└── admin/Billing.tsx           # 利用料のお支払い

docker-compose.yml              # stripe（Stripe CLI。profile: stripe）を足す
env.example                     # STRIPE_SECRET_KEY・STRIPE_WEBHOOK_SECRET を足す
```

**Structure Decision**: spec 001 と同じ Web アプリの構成に、決済のファイルを足す。決済はすべてようこの担当なので、ほかの人のファイルを触らない。
例外は、`email_outbox` のテンプレートの追加（さとこ、作り込み）と、spec 001 の T009・T015・T014 の基盤のタスクへの追加（ようこ自身）。

## ほかの人・spec 001 とのつながり

| つながり | 内容 | 相手 | 時期 |
|---|---|---|---|
| 共通のテーブル（T009） | `facilities` に 2 列を足し、ログイン用の ID のシーケンスを作る | ようこ（自分） | ミニマム |
| 書き込みの確認（T014） | `/api/billing/webhook` を `X-Requested-With` の確認から外す | ようこ（自分） | ミニマム |
| 初期データ（T015） | 施設がなければ「契約中」の契約も作る。あればそれを使う | ようこ（自分） | ミニマム |
| ログイン（T022） | 施設長は職員と同じく ID でログインする。パスワードの決まり（8〜64 文字・組み合わせなし・よく使われるパスワードを弾く）は spec 001 の research.md R-03 に書き、ログイン全体で共通にする（PR #25 でチームが決定） | ようこ（自分） | ミニマム（Day 2） |
| メール（T048・T057） | テンプレート `owner_account` を足し、params に `login_id` を入れる例外を認めてもらう（R-08） | さとこ | 作り込み |
| 画面の枠（T019） | `/signup`・`/signup/complete` はログインなしの枠、`/admin/billing` は管理画面の枠に置く | ようこ（自分） | ミニマム |

## ミニマム版と作り込み

| ミニマム版（Day 1〜3） | 作り込み（Day 4〜） |
|---|---|
| 申し込みページ（入力・メールアドレスの 2 回入力・二度押し対策・施設があれば 404）、Checkout、Webhook（署名・同じ知らせ・`checkout.session.completed`・`checkout.session.expired`）、施設とアカウントを作る処理、完了の画面（ID を出す）、利用料のお支払いの画面（契約の状態だけ）、自動テスト（SC-003〜SC-009） | ID を書いたメール（FR-005）、申し込みを同時に 1 つだけ（FR-014）、回数の制限（FR-027）、契約の状態の知らせ（`customer.subscription.*`・`invoice.*`）と次の請求日の表示（US2）、申し込み直し、Customer Portal（US3）、制限付きの鍵（FR-026） |

Day 3 までの順番（ようこ）：spec 001 の基盤（T009〜T015、T022）を先に終え、決済は Day 2 の午後から。Webhook を手元で受けられること（Stripe CLI）を最初に確かめる。

## 未決定のこと（plan では仮に置いた）

| 項目 | 仮に置いた内容 | 決める場 |
|---|---|---|
| ログイン用の ID の形 | `s` ＋ 5 桁の数字（R-06） | ようこ（基盤）。T009 の PR で共有する |
| ID を書いたメールの params | `login_id` を params に入れる例外（R-08） | さとこと相談（作り込みの前） |
| 本番の Webhook の受け口 | 本番の URL を Stripe の管理画面に登録し、本番用の `STRIPE_WEBHOOK_SECRET` を Render に置く | ようこ（本番デプロイ T092 のとき） |

## Complexity Tracking

> Constitution Check に違反はないため、記入なし。
