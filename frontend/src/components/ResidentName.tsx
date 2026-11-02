import { useTranslation } from 'react-i18next'
import { Ruby } from '../i18n/Ruby'
import { escapeRubyMarks } from '../i18n/rubyText'

const RELATIONSHIPS = new Set(['daughter', 'son', 'spouse', 'grandchild', 'sibling', 'other'])

// 辞書の文に、名前を差し込む場所の目印（名前の部分だけ、別の部品で出すため）
const NAME_MARK = '\u0001'

type NameProps = {
  // API が返す名前（表示言語に合わせたもの。日本語はフルネーム、インドネシア語・英語はローマ字）
  name: string
  // ふりがな付きの名前（`{佐藤|さとう} {文江|ふみえ}`。職員の画面で日本語のときだけ API が返す）。
  // 家族の画面は、Ruby 部品がふりがなを外す
  ruby?: string
}

// API が読みを付けたとき（ruby が name と違うとき）だけ、ふりがなの書き方として解釈する。
// 名前そのものは、書き方の記号（{ } |）を全角にして、文字のまま出す（FR-017）
function shownName({ name, ruby }: NameProps): string {
  return ruby !== undefined && ruby !== name ? ruby : escapeRubyMarks(name)
}

// 「さん」（日本語のときだけ。辞書の resident_name.honorific_suffix の 1 か所で決める）。
// 敬称なので、名前より少し小さく出す
function Honorific() {
  const { t } = useTranslation()
  const suffix = t('resident_name.honorific_suffix')
  return suffix ? <span className="text-[0.85em]">{suffix}</span> : null
}

/**
 * 入居者の名前（ふりがなと、日本語のときの「さん」つき。docs/デザインの決めごと.md の 15 章）。
 * 入居者一覧のように文字が多い所は、honorific={false} で「さん」を付けない。
 */
export function ResidentName({ honorific = true, ...props }: NameProps & { honorific?: boolean }) {
  return (
    <>
      <Ruby text={shownName(props)} />
      {honorific && <Honorific />}
    </>
  )
}

/**
 * 「佐藤 文江さんのご家族（娘）」の形（職員の画面の、家族からのメッセージ・面会の予約）。
 * relationship は、家族アカウントの代表者の続柄のコード。ないとき・知らないコードは「（娘）」を省く。
 */
export function ResidentFamily({
  relationship,
  ...props
}: NameProps & { relationship: string | null }) {
  const { t } = useTranslation()
  const template =
    relationship && RELATIONSHIPS.has(relationship)
      ? t('resident_name.family_of', {
          name: NAME_MARK,
          relationship: t(`resident_name.relationship.${relationship}`),
        })
      : t('resident_name.family_of_plain', { name: NAME_MARK })
  // 名前の前後の言葉と、名前（「さん」つき）を、別々に出す
  const [before, after] = template.split(NAME_MARK)
  return (
    <>
      {before && <Ruby text={before} />}
      <ResidentName {...props} />
      {after && <Ruby text={after} />}
    </>
  )
}
