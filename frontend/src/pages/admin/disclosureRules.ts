// 開示設定の、関係しそうな組み合わせの注意書き（spec 001 の T042・FR-009）。
// 組の一覧（related）は API が返す（backend の RELATED_PAIRS。data-model.md）。
// まだ保存していない選び方でも出すので、画面で今の選び方から計算する。止めはしない。

export type RelatedPair = { item: string; theme: string }

/** 記録の項目は「見せない」なのに、組のテーマは「見せる」になっている組。 */
export function warningsFor(
  related: RelatedPair[],
  isVisible: (kind: 'items' | 'themes', code: string) => boolean,
): RelatedPair[] {
  return related.filter((pair) => !isVisible('items', pair.item) && isVisible('themes', pair.theme))
}
