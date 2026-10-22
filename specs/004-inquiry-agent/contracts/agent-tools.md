# Agent Tools Contract: spec 004（F：問い合わせ AI エージェント）

AI（OpenRouter のモデル）に渡すツールの形と、ループの決まりごと。ツールの定義は OpenAI 形式の `tools`（`type: function`）で渡す。
どのツールも、**入居者の id を引数に持たない**（サーバーがログイン中の家族から決める。FR-020）。

## ループ

1. 指示（固定）・直近の 6 往復・その家族の対応待ちのメッセージ（id・種類・要約）・今回の発言を付けて、`chat.completions.create` を呼ぶ。`tools` は毎回付ける（技術選定 5 章）。
2. 応答に `tool_calls` があれば、応答をそのまま履歴に足してから、ツールを 1 つずつサーバーで実行し、結果を `role: "tool"` で足して 1 に戻る。
3. `answer_family` か `hand_off_to_staff` が呼ばれたら終わる。応答に `tool_calls` がない（普通の文で答えてきた）ときは、その文を家族に出さず、「`answer_family` を使って答えてください」と返して 1 回だけやり直させる。2 回目もツールを使わなければ、決まった文「お答えできる記録がありません」にする（research.md R-03）。
4. ツールを呼んだ回数が 5 回に達したら終わり、`hand_off_to_staff(category="other")` と同じ扱いで職員に渡す（FR-025）。
5. 1 回の呼び出しが 30 秒を超えた・つながらないときは、503（`ai_unavailable`）。回数は戻す（FR-026）。
6. 言葉による決まり（`guard.py`）に引っかかった発言では、`answer_family` を受け付けず、決まった種類で職員に渡す（research.md R-05）。

## `get_care_records`

```json
{
  "name": "get_care_records",
  "description": "この入居者の、家族に見せてよい連絡帳の記録（食事量・機嫌・様子・眠り）を調べる。今日から過去 7 日まで。",
  "parameters": {
    "type": "object",
    "properties": {
      "date_from": {"type": "string", "description": "YYYY-MM-DD（日本時間）"},
      "date_to":   {"type": "string", "description": "YYYY-MM-DD（日本時間）"},
      "items":     {"type": "array", "items": {"enum": ["meal", "mood", "sleep"]}}
    },
    "required": ["date_from", "date_to"]
  }
}
```

- 中で `get_disclosed_records(resident_id, date_from, date_to, items)` を呼ぶ（spec 001）。範囲は今日から過去 7 日に切り詰める。
- 結果の例：`{"records": [{"source_id": "record:812", "date": "2026-10-21", "item": "meal", "slot": "lunch", "value": "8", "label": "ほぼ全部（8割）", "note": "…"}], "missing": [{"date": "2026-10-21", "item": "meal", "slot": "dinner"}], "clamped": false}`
  - `missing` は、その期間で未記録の欄（「まだ記録されていません」と答えるため）。非開示の項目は、`records` にも `missing` にも出さない。

## `get_staff_replies`

```json
{
  "name": "get_staff_replies",
  "description": "家族の「知りたいこと」への、施設の職員の返事を調べる。今日から過去 7 日まで。",
  "parameters": {
    "type": "object",
    "properties": {
      "date_from": {"type": "string"},
      "date_to":   {"type": "string"}
    },
    "required": ["date_from", "date_to"]
  }
}
```

- 中で `get_active_replies(resident_id, date_from, date_to)` を呼ぶ（spec 001）。
- 結果の例：`{"replies": [{"source_id": "reply:55", "date": "2026-10-20", "theme": "楽しく過ごせているか", "text": "他の入居者さんと楽しそうに話していました", "note": "…"}]}`

## `answer_family`

```json
{
  "name": "answer_family",
  "description": "家族に答える。記録・返事にもとづく内容だけを書き、もとにした source_id を必ず入れる。記録がなければ、ないと伝える。",
  "parameters": {
    "type": "object",
    "properties": {
      "text":       {"type": "string", "description": "家族の表示言語で。やさしい日本語。500 文字まで"},
      "source_ids": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["text", "source_ids"]
  }
}
```

- サーバーは `source_ids` を、この答えの中でツールが返したものだけに絞る（research.md R-03）。

## `hand_off_to_staff`

```json
{
  "name": "hand_off_to_staff",
  "description": "答えずに施設の職員に渡す。医療・服薬・体調の解釈・苦情・お金・緊急・記録にないことで人の確認が要るもの。",
  "parameters": {
    "type": "object",
    "properties": {
      "category":            {"enum": ["medical", "complaint", "money", "care_request", "urgent", "other"]},
      "summary":             {"type": "string", "description": "職員向けの要約。日本語。500 文字まで。開示されていない記録の内容は書かない"},
      "existing_message_id": {"type": ["integer", "null"], "description": "同じ内容の対応待ちのメッセージがあれば、その id"}
    },
    "required": ["category", "summary"]
  }
}
```

- `existing_message_id` は、AI に渡した「その家族の対応待ちのメッセージ」の id のときだけ使う（ほかの id は無視して新しく作る）。
- 家族には「この内容は施設の職員からお答えします。施設の職員にお伝えしました」（つないだときは「すでに施設の職員にお伝えしています」）を返す。
- `category = "urgent"` のときは、あわせて「お急ぎのときは、施設にお電話ください」を返す。
