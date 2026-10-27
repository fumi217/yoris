import { Fragment, useContext } from 'react'
import { FuriganaContext } from './furigana'
import { parseRuby, stripRuby } from './rubyText'

type Props = {
  // 辞書から引いた文（`{漢字|かんじ}` の書き方を含んでよい）
  text: string
}

/**
 * ふりがなの部品。`{漢字|かんじ}` を `<ruby>` にして出す（spec 001 の research.md R-11）。
 * 文は React の文字として出すので、HTML として解釈しない（dangerouslySetInnerHTML は使わない）。
 * 家族の画面（FuriganaContext が false）では、ふりがなを外して漢字だけにする（constitution 3.2.0。#260）。
 */
export function Ruby({ text }: Props) {
  const showFurigana = useContext(FuriganaContext)
  if (!showFurigana) return <>{stripRuby(text)}</>
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
