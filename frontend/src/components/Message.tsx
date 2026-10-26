import { Text } from './Text'

/** 画面の真ん中に出す短い文（読み込み中・エラー・準備中など）。 */
export function Message({ k }: { k: string }) {
  return (
    <p className="p-6">
      <Text k={k} />
    </p>
  )
}
