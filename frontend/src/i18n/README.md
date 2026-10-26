# 多言語の辞書とふりがな

spec 001 の research.md R-11 の決まりを、使う人向けにまとめたもの。

## 使い方

```tsx
import { useTranslation } from 'react-i18next'
import { Ruby } from '../i18n/Ruby'

const { t } = useTranslation()
return <Ruby text={t('error.forbidden')} />
```

- 画面の固定の文言は、必ず辞書（`ja.json`）から引く。コードに日本語を直接書かない
- ふりがなは `{漢字|かんじ}` の書き方で、`ja.json` の中に書く。表示は `Ruby` の部品が `<ruby>` にする
  - ミニマム版はふりがななしでよい。Day 5 に 001-T083 などでまとめて付ける（spec 001 の tasks.md）
  - `id.json`・`en.json` には、この書き方を使わない
- 職員が自由に書いた文・お知らせの本文・ファイルの中身は、辞書を通さずそのまま出す
- ルビを出せないところ（`title`・`aria-label` など）は、`rubyText.ts` の `stripRuby` で漢字だけにする。メールは backend の `app/i18n.py` の `strip_ruby`

## キーの付け方

全員が同じ `ja.json` に書き足すので、キーの先頭を spec ごとに分ける（同じところを書き換えてぶつかるのを減らすため）。

| 先頭                    | 中身                                                                                                                                                                                  | 決まっているところ           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `error.*`               | API のエラー（`message_key` は `error.<code>`）                                                                                                                                       | spec 001 の contracts/api.md |
| `theme.*`・`template.*` | 知りたいことのテーマと、職員の返事の定型文                                                                                                                                            | spec 001 の research.md R-11 |
| `staff_template.*`      | 問い合わせ AI で、職員が家族に返す定型文                                                                                                                                              | spec 004 の research.md R-14 |
| `role.*`                | 職員の役割の名前（介護職員・施設長など。どの機能でも共通で使う）                                                                                                                      | spec 001 の data-model.md    |
| `change.*`              | 変化の検知の目印まわり                                                                                                                                                                | spec 006 の tasks.md         |
| そのほか                | 機能ごとに 1 つの先頭にまとめる（例：記録 `record.*`、連絡帳 `contact_book.*`、面会 `visit.*`、決済 `billing.*`、問い合わせ AI `inquiry.*`、アルバム `album.*`、様子のメモ `memo.*`） | 提案（使う人が決めてよい）   |
