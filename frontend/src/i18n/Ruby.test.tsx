import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import i18n from './index'
import ja from './ja.json'
import { Ruby } from './Ruby'
import { parseRuby, stripRuby } from './rubyText'

describe('parseRuby', () => {
  it('ふりがなの書き方を、文とふりがなの部分に分ける', () => {
    expect(parseRuby('{全部|ぜんぶ}（8{割|わり}）')).toEqual([
      { kind: 'ruby', base: '全部', reading: 'ぜんぶ' },
      { kind: 'text', text: '（8' },
      { kind: 'ruby', base: '割', reading: 'わり' },
      { kind: 'text', text: '）' },
    ])
  })

  it('書き方を使わない文（インドネシア語・英語）は、そのまま 1 つの文になる', () => {
    expect(parseRuby('Makan siang habis')).toEqual([{ kind: 'text', text: 'Makan siang habis' }])
  })

  it('書き方に合わない { } は、そのまま文として残す', () => {
    expect(parseRuby('{だけ} と {|よみ}')).toEqual([{ kind: 'text', text: '{だけ} と {|よみ}' }])
  })
})

describe('stripRuby', () => {
  it('ふりがなを外して漢字だけにする', () => {
    expect(stripRuby('{全部|ぜんぶ}（8{割|わり}）')).toBe('全部（8割）')
  })
})

describe('Ruby', () => {
  it('ふりがなを <ruby> にして出す', () => {
    expect(renderToStaticMarkup(<Ruby text="{全部|ぜんぶ}たべた" />)).toBe(
      '<ruby>全部<rp>(</rp><rt>ぜんぶ</rt><rp>)</rp></ruby>たべた',
    )
  })

  it('文は HTML として解釈せず、文字として出す', () => {
    expect(renderToStaticMarkup(<Ruby text="<script>x</script>" />)).toBe(
      '&lt;script&gt;x&lt;/script&gt;',
    )
  })
})

describe('辞書', () => {
  // backend/app/errors.py の ErrorCode のすべて。API は message_key に error.<code> を返す
  const errorCodes = [
    'not_logged_in',
    'forbidden',
    'not_found',
    'too_many_attempts',
    'request_limit',
    'theme_waiting',
    'already_replied',
    'request_cancelled',
    'not_today',
    'invalid_file',
    'validation_error',
    'server_error',
  ]

  it('API のエラーのコードすべてに、日本語の文言がある', () => {
    for (const code of errorCodes) {
      expect(ja.error[code as keyof typeof ja.error], code).toBeTruthy()
    }
  })

  it('初めは日本語で、辞書から文言を引ける', () => {
    expect(i18n.language).toBe('ja')
    expect(i18n.t('error.already_replied')).toBe('ほかの職員が返事をしました')
  })
})
