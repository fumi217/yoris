import {
  startTransition,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router'
import happyFace from '../../assets/brand/mascot-happy.png'
import normalFace from '../../assets/brand/mascot-normal.png'
import { stripRuby } from '../../i18n/rubyText'
import { GO_DELAY_MS, INQUIRY_PATH, isPlainClick, prefersReducedMotion } from './mascotLogic'

// 余白を切り取った画像の大きさ（2 枚とも同じ枠で切り取ってある。12.1）。
// width・height を書くのは、読み込み中に表示がずれないようにするため
const WIDTH = 308
const HEIGHT = 263

const faceClass = 'col-start-1 row-start-1 h-auto w-full drop-shadow-md'

/**
 * YORIS のキャラクター。家族のホーム（連絡帳）の右下に置き、押すとお問い合わせへ進む
 * （デザインの決めごと 12.4。#339）。
 * - 押すと、嬉しい顔に切り替えて、0.4 秒後に移る。動きを減らす設定のときは、待たずに移る
 * - 外側の枠（リンク）は動かさず、中の絵だけをふわふわ動かす（押す場所がずれないように。index.css）
 * - 2 枚の絵は、同じ場所に重ねて、ずっと読み込んでおく（押したときに空白が出ない・跳ねない）
 * - 絵は飾り（`alt=""`）。リンクの名前は、辞書の layout.mascot_link
 * - 幅 320px 以下・高さが低いときは、固定をやめて、ページの末尾に置く（index.css・本文に重ならないように）
 * - 移る処理を呼んだら、ふつうの顔・押せる状態に戻す（移った直後に「戻る」で戻っても、押せるように。下の go）
 */
export function Mascot() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [happy, setHappy] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current)
    },
    [],
  )

  // お問い合わせへ移る。画面の移動は裏で描き替える（startTransition）ので、移った直後に「戻る」を
  // 押すと、移動と戻るがまとめて描かれ、この部品が作り直されないことがある。そのままだと、嬉しい顔と
  // 「移動中」の印が残り、押しても動かなくなる（PR #340 ようこさん）。移る処理を呼んだら、印を消し、
  // 顔も戻す。顔を戻すのも移動と同じ扱いにして、ふつうに移るときに、顔が一瞬戻って見えないようにする
  const go = () => {
    timer.current = null
    startTransition(() => setHappy(false))
    void navigate(INQUIRY_PATH)
  }

  const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
    // 新しいタブなどは、待たずにふつうに動かす。動きを減らす設定のときも、Link にそのまま移らせる
    if (!isPlainClick(event) || prefersReducedMotion()) return
    event.preventDefault()
    // 続けて押しても、移るのは 1 回だけ
    if (timer.current !== null) return
    setHappy(true)
    timer.current = window.setTimeout(go, GO_DELAY_MS)
  }
  // リンクは Enter では押せるが、Space では押せない。ボタンと同じく、Space でも押せるようにする（12.4）
  const onKeyDown = (event: KeyboardEvent<HTMLAnchorElement>) => {
    if (event.key !== ' ') return
    event.preventDefault()
    event.currentTarget.click()
  }

  return (
    <div
      data-mascot
      className="pointer-events-none fixed inset-x-0 bottom-[calc(var(--family-menu-height)+1rem)] mx-auto flex max-w-xl justify-end px-4 [@media(max-width:320px)]:static [@media(max-width:320px)]:mt-4 [@media(max-height:400px)]:static [@media(max-height:400px)]:mt-4"
    >
      <Link
        to={INQUIRY_PATH}
        aria-label={stripRuby(t('layout.mascot_link'))}
        onClick={onClick}
        onKeyDown={onKeyDown}
        className="pointer-events-auto block w-[72px] rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-700"
      >
        <span className="mascot-float grid">
          <img
            src={normalFace}
            alt=""
            width={WIDTH}
            height={HEIGHT}
            className={`${faceClass} ${happy ? 'opacity-0' : ''}`}
          />
          <img
            src={happyFace}
            alt=""
            width={WIDTH}
            height={HEIGHT}
            className={`${faceClass} ${happy ? '' : 'opacity-0'}`}
          />
        </span>
      </Link>
    </div>
  )
}
