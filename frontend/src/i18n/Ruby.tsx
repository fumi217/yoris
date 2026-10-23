import { Fragment } from 'react'
import { parseRuby } from './rubyText'

type Props = {
  // 辞書から引いた文（`{漢字|かんじ}` の書き方を含んでよい）
  text: string
}

/**
 * ふりがなの部品。`{漢字|かんじ}` を `<ruby>` にして出す（spec 001 の research.md R-11）。
 * 文は React の文字として出すので、HTML として解釈しない（dangerouslySetInnerHTML は使わない）。
 */
export function Ruby({ text }: Props) {
  return (
    <>
      {parseRuby(text).map((segment, index) =>
        segment.kind === 'text' ? (
          <Fragment key={index}>{segment.text}</Fragment>
        ) : (
          <ruby key={index}>
            {segment.base}
            <rp>(</rp>
            <rt>{segment.reading}</rt>
            <rp>)</rp>
          </ruby>
        ),
      )}
    </>
  )
}
