import { useTranslation } from 'react-i18next'
import wordmark from '../assets/brand/logo-wordmark.png'
import { stripRuby } from '../i18n/rubyText'

// 余白を切り取った画像の大きさ（半透明のふちの外側に 2px の余白つき）。
// width・height を書くのは、読み込み中に表示がずれないようにするため
const WIDTH = 475
const HEIGHT = 122

type Props = {
  // 高さを決める（幅は、縦横比 475 : 122 のまま）。家族は h-7（28px）、職員・管理画面は h-8（32px）
  className?: string
}

/**
 * YORIS のロゴ（文字つき）。全画面の左上に置く（デザインの決めごと 12.3。#330）。
 * 読み上げの名前は、アプリの名前（辞書の layout.app_name）。画像の文字は、名前の代わりなので、
 * `alt` を付ける（1.1.1）。色・縦横比を変えない。濃い色や写真の上には置かない（O の輪が薄いため）。
 */
export function Logo({ className = 'h-7' }: Props) {
  const { t } = useTranslation()
  return (
    <img
      src={wordmark}
      alt={stripRuby(t('layout.app_name'))}
      width={WIDTH}
      height={HEIGHT}
      // max-w-none：Tailwind は img に max-width:100% を付けるため、外の枠が狭いと幅だけ縮んで縦横比が崩れる
      className={`${className} w-auto max-w-none shrink-0`}
    />
  )
}
