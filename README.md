# 最終プロジェクト名

最終課題用プロジェクトのドキュメントのテンプレートです。
あくまでテンプレートなので、参考に使ってください

## 企画

### Issue

- 誰の課題？：xxxx
- なにに困っている？：xxxx
- 本来はどうあるべき？：xxxx
- 既存のソリューションは？：xxxx
- その課題が解決されたらいくら払う？：xxxx 円 / 月

### Solution

- どうやって解決する？：xxxx
- 実現できたら実際に解決できる？：xxxx
- 優位性は？：xxxx
- デメリットや副作用はある？：xxxx
- デメリットと天秤にかけてもこのソリューションを使うべき？：(Yes / No)

## アーキテクチャ概要

> システム構成図（C4 / 簡易構成図）をここに貼る。draw.io / Mermaid いずれでも可。

## ディレクトリ構成

```
.
├── frontend/   # フロントエンドアプリケーション
├── backend/    # バックエンドアプリケーション
└── docs/       # 企画・要件・各種設計ドキュメント
```

## 開発の始め方

- フロントエンド：[frontend/README.md](./frontend/README.md)
- バックエンド：[backend/README.md](./backend/README.md)

**保存しても自動で読み直されないとき（Windows 側のフォルダで動かしているときなど）**：
リポジトリの一番上の `.env` に `WATCH_POLLING=true` を書いて、`docker compose up -d` で起動し直す。
フロント（Vite）とバックエンド（uvicorn）が、変更を定期的に見に行くようになる（少し重くなるので、困ったときだけ使う）。

## ドキュメント

### 企画・要件

- [PRD](./docs/PRD.md)
- [要件定義](./docs/要件定義.md)

参考：[要件と仕様の違い](https://korogaruomochi.com/the-difference-and-importance-of-requirements-and-specifications/)

### 設計

- [技術選定](./docs/技術選定.md)
- [画面設計](./docs/画面設計.md)
- [DB 設計](./docs/DB設計.md)
- [API 設計](./docs/API設計.md)

### テスト

- [テスト設計書](./docs/テスト設計書.md)

### 非機能設計

- [運用設計](./docs/運用設計.md)
- [性能設計](./docs/性能設計.md)
- [ログ設計](./docs/ログ設計.md)
- [可用性設計](./docs/可用性設計.md)
- [セキュリティ設計](./docs/セキュリティ設計.md)

## 体制

リーダーはさとこ。全員がフロントエンドとバックエンドの両方を担当し、機能ごとに画面から API・DB まで通しで作る（決定：[作業分担MTG](./docs/context/meeting/作業分担MTG.md)）。

| メンバー | 責任を持つ領域 | 主な担当機能 |
|---|---|---|
| ようこ | インフラ・デプロイ、認証、決済、テスト（E2E） | 環境構築、ログイン・役割・招待、J：Stripe、本番デプロイ |
| みさき | AI、多言語・ふりがな | F：問い合わせ AI、D：翻訳・整文、E：変化の検知 |
| ゆう | 職員の画面 | C：記録、B：開示設定、A：職員の返事、G：面会予約 |
| さとこ | 家族の画面、通知、ドキュメント | 家族の連絡帳・頼みごと、通知、施設からのお知らせ（献立表の投稿も含む）、H：アルバム |

## コントリビュート

ブランチ・コミット・Issue・PR・マージのルールは [.claude/skills/github-workflow/SKILL.md](.claude/skills/github-workflow/SKILL.md) を見てください。Claude Code 向けの前提は [CLAUDE.md](CLAUDE.md) にあります。

- `main` への直接 push は禁止。実装は Issue を立て、`feature/<Issue番号>-<短い英語名>` のブランチで作業する
- コミット・PR のタイトル: `<type>(<scope>): #<Issue番号> <要約>`（docs・chore は scope と Issue 番号を省いてよい）
- レビュー: 関わる人を PR ごとに決めて Reviewers に入れる。目安は半日以内
- マージ: Reviewers のうち誰か 1 名の Approve・AI チューターの指摘に対応済み・CI が緑で、Squash and merge。Approve のあとの指摘対応・誤字修正は、コメントに一言書けば再 Approve は不要

### はじめに（1 回だけ）

Claude Code でコミットする場合、`.env` やトークンのコミットを止める仕組みは clone するだけで有効になります。人が直接コミットする場合は、最初に一度だけ次を実行してください。

```bash
git config core.hooksPath .githooks
```
