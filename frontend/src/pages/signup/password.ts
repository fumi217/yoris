// パスワードの決まりの、送る前の確認（サーバーの決まりと同じ。spec 001 の research.md R-03）。
// 最後に確かめるのはサーバー（よく使われるパスワードは、サーバーが 422 で断る）。
// ここで先に確かめるのは、ブラウザ標準のエラーの吹き出し（辞書を通らない文言）を出さないため。

const MIN_LENGTH = 8
const MAX_LENGTH = 64

/** 半角の英数字と記号（空白を含む）で、8〜64 文字か。 */
export function isValidPassword(password: string): boolean {
  return password.length >= MIN_LENGTH && password.length <= MAX_LENGTH && /^[ -~]+$/.test(password)
}
