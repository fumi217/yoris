// 変化の目印の設定の画面（ChangeRules.tsx）の、保存の文を出すかどうかの決まり。
// 画面のファイルは、部品だけを書き出す決まり（react-refresh）なので、関数はここに置く。

type Rule = { code: string; enabled: boolean }

/**
 * 「オフにしました」などの保存の文を出してよいか。ほかの人が変えて、いまの値と食い違ったら、出さない
 * （画面の値と、文が食い違ったまま残らないように）。
 */
export function visibleSaved(rules: Rule[], result: Rule | null): Rule | null {
  if (!result) return null
  const current = rules.find((rule) => rule.code === result.code)
  return current && current.enabled === result.enabled
    ? { code: result.code, enabled: result.enabled }
    : null
}
