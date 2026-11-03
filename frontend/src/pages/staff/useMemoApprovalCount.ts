import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { APPROVALS_KEY } from './memoApprovalsView'

/** `GET /api/staff/memo-approvals/count` の返り値。承認できない人（リーダー・施設長以外）は null。 */
type MemoApprovalCount = { count: number | null }

/**
 * 様子のメモの承認待ちの件数（施設全体。入居者ごとではない。FR-015）。承認できるリーダー・施設長に、
 * 職員のホームの入り口として添える（007-T028）。画面を開いたときに読むだけで、通知・音は出さない。
 * 承認できない人・読めなかったときは null（項目を出さない。一覧は使えるように）。
 */
export function useMemoApprovalCount(): number | null {
  const count = useQuery({
    queryKey: [...APPROVALS_KEY, 'count'],
    queryFn: () => api.get<MemoApprovalCount>('/api/staff/memo-approvals/count'),
  })
  return count.data?.count ?? null
}
