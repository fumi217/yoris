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

## コントリビュート

- ブランチ戦略・コミット規約・PR レビュー方針は各アプリの README とリポジトリの CI 設定に従う。
