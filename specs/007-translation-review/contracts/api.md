# API Contract: spec 007（D：翻訳・整文・訳し戻し・承認）

共通の決まり（`/api`、Cookie のセッション、`X-Requested-With: fetch`、エラーの形）は [spec 001 contracts/api.md](../../001-family-priority-report/contracts/api.md) と同じ。担当はすべてみさき。
家族向けの新しい API はない（家族の連絡帳は spec 001 の `GET /api/family/contact-book` が `get_disclosed_memos()` を通して返す。さとこ）。

### 役割の略号

`CW` 介護職員、`L` リーダー、`D` 施設長。「本人」は書いた職員

### 時期の略号

`ミ` ミニマム版（Day 3）、`作` 作り込み（Day 4〜）

### エラー（spec 001 の表に足すもの）

| HTTP | code | いつ | spec |
|---|---|---|---|
| 409 | `memo_limit` | その入居者について、今日 3 件書いた | FR-001 |
| 409 | `invalid_state` | その状態ではできない操作（承認済みを直す、ほかの人が先に承認した など） | FR-009〜013a |
| 409 | `rewrite_limit` | 1 つのメモでやり直しが 5 回を超えた | research.md R-08 |
| 403 | `self_approval` | 本人が自分のメモを承認・戻そうとした（リーダーでも。ほかのリーダー・施設長が承認する） | FR-011a |
| 503 | `ai_unavailable` | AI のサービスに接続できない・30 秒を超えた（原文は残る） | FR-020 |
| 404 | `not_found` | 本人でない職員が、ほかの人の下書きを id で開いた | — |

## 書く・整える・確かめる（本人）

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `POST /api/staff/residents/{id}/memos` | CW・L | ミ | 下書きを作る（`original_text`：1〜500 文字、`source_lang`）。409：`memo_limit`（作。1 日 3 件は 007-T013 で足す） | FR-001 |
| `GET /api/staff/memos?resident_id=&date=` | CW・L | ミ | 自分のメモの一覧（状態・戻した理由つき） | FR-013 |
| `GET /api/staff/memos/{id}` | 本人 | ミ | 原文・整えた日本語・訳し戻し・印・状態。本人でなければ、リーダーでも 404（リーダー・施設長が承認待ちを見るのは、下の `GET /api/staff/memo-approvals`） | FR-004・FR-007 |
| `PATCH /api/staff/memos/{id}` | 本人 | 作 | 原文か整えた日本語を直す（`original_text`・`rewritten_text` のどちらか、または両方。`draft`・`returned` のときだけ）。原文を直すと、整えた日本語と訳し戻しは消える（その原文から作ったものではなくなるため。直した整えた日本語を同時に送れば、それを使う）。整えた日本語を直すと、訳し戻しは消える（直した文で作り直す）。印は直した内容で付け直す。まだ整えていないメモの整えた日本語は直せない。整えた日本語は 1,000 文字まで。409：`invalid_state` | FR-008 |
| `POST /api/staff/memos/{id}/rewrite` | 本人 | ミ（整えるだけ）／作（訳し戻しも） | 「日本語にする」：整える → 訳し戻す（職員の表示言語が日本語のときは、訳し戻さない）。本文は任意で `{"back_translate_only": true}`：整えた日本語を自分で直したあと、直した文を表示言語に訳し戻すだけにする（整え直さない。表示言語が日本語・整えた日本語がないときは 409：`invalid_state`）。どちらも履歴を 1 件足し、やり直しの 5 回に数える。503：`ai_unavailable`（途中で止まったら何も保存しない）、409：`rewrite_limit`（作。やり直し 5 回の上限は 007-T014 で足す）。直せない状態では 409：`invalid_state` | FR-003・FR-007・FR-020 |
| `POST /api/staff/memos/{id}/confirm` | 本人 | 作 | 「確かめました」→ `pending`（`draft`・`returned` のときだけ。確かめた日時を残す）。整えた日本語がないとき、表示言語が日本語でないのに訳し戻しがないときは、確かめられない（409：`invalid_state`）。更新したメモを返す | FR-009 |
| `POST /api/staff/memos/{id}/withdraw` | 本人 | 作 | 取り下げる（`draft`・`pending`・`returned` のときだけ → `withdrawn`）。更新したメモを返す | FR-010 |

- 本人でない職員（リーダーを含む）が `{id}` を指定したときは、どの操作も 404（`not_found`）。直す・整える・確かめる・取り下げるは、どれも条件つきの 1 回の更新で進める（research.md R-05）。

## 承認（リーダー・施設長）

| メソッド・パス | 役割 | 時期 | 中身 | spec |
|---|---|---|---|---|
| `GET /api/staff/memo-approvals?status=` | L・D | 作 | 承認待ちの一覧（`status=pending`。初期値）：入居者の名前（`resident_name`。職員の表示言語に合わせる。ふりがな付きは `resident_name_ruby`（`ja` のときだけ））・書いた職員・`is_own`（ログイン中の職員が書いたか。画面は本人のメモに「承認する」「戻す」を出さない。FR-011a）・原文・整えた日本語・訳し戻し・印・確かめた日時・経過時間（`waiting_minutes`）・「1 日以上待っています」（`overdue`）。確かめてから長く待っているものを上にする。`status=approved` は、公開を取り下げる対象を探すための承認済みの一覧（承認した日時の新しい順に、多くても 50 件。経過時間は付けない）。同じ施設のものだけ。一度も「確かめました」を押していない下書きは返さない | FR-011・FR-013a・FR-015 |
| `GET /api/staff/memo-approvals/count` | 職員なら誰でも呼べる。件数を返すのは L・D だけ | 作 | 承認待ちの件数（施設全体。本人が書いたものも数える）。L・D 以外は `{"count": null}`（件数を出さない）。ゆうの画面から呼ぶ | FR-015 |
| `POST /api/staff/memo-approvals/{id}/approve` | L・D（本人以外） | 作 | 承認する。403：`self_approval`、409：`invalid_state` | FR-011・FR-011a・FR-012 |
| `POST /api/staff/memo-approvals/{id}/return` | L・D（本人以外） | 作 | 戻す（`reason`：1〜200 文字）。403：`self_approval`、409：`invalid_state` | FR-013 |
| `POST /api/staff/memo-approvals/{id}/unpublish` | L・D | 作 | 公開を取り下げる（承認済み → 戻し。`reason`：1〜200 文字）。409：`invalid_state` | FR-013a |

- 承認の API は、どれも同じ施設のメモだけを扱う。ほかの施設のメモ・一度も「確かめました」を押していない下書きは、あることも分からないよう 404（`not_found`）にする。
- approve・return・unpublish は、更新したメモ 1 件（一覧の 1 件と同じ形）を返す。
- 戻した理由と公開を取り下げた理由は、書いた職員の画面には、新しい方を「戻された理由」として出す（`GET /api/staff/memos/{id}` の `return_reason`）。

- 原文・整えた日本語・訳し戻し・理由は、文字としてのみ表示する（FR-017）。
- 書く画面と承認の画面には、「急変・事故は、すぐに電話で連絡してください」を出す。承認の画面には「ほかの入居者の名前が入っていないか」「医療・服薬・体調の判断が入っていないか」を出し、印（research.md R-03）があれば目立たせる（FR-016）。
