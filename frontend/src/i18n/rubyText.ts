// ふりがなの書き方 `{漢字|かんじ}` を読む（spec 001 の research.md R-11）。
// 日本語の辞書だけがこの書き方を使う。インドネシア語・英語の辞書には書かないので、そのまま文になる。

export type RubySegment =
  { kind: 'text'; text: string } | { kind: 'ruby'; base: string; reading: string }

// { と } の間に「漢字|読み」が 1 組。どちらも空でなく、{ } | を含まない
const RUBY_PATTERN = /\{([^{}|]+)\|([^{}|]+)\}/g

/** 文を、ふつうの文とふりがなの付いた部分に分ける。書き方に合わない { } はそのまま文として残す。 */
export function parseRuby(text: string): RubySegment[] {
  const segments: RubySegment[] = []
  let last = 0
  for (const match of text.matchAll(RUBY_PATTERN)) {
    const start = match.index ?? 0
    if (start > last) segments.push({ kind: 'text', text: text.slice(last, start) })
    segments.push({ kind: 'ruby', base: match[1], reading: match[2] })
    last = start + match[0].length
  }
  if (last < text.length) segments.push({ kind: 'text', text: text.slice(last) })
  return segments
}

/** ふりがなを外して漢字だけにする（画面の title・aria-label など、ルビを出せないところで使う）。 */
export function stripRuby(text: string): string {
  return text.replace(RUBY_PATTERN, '$1')
}
