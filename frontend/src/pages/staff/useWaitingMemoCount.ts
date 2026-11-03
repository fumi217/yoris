import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { APPROVALS_KEY } from './memoApprovalsView'

/**
 * 様子のメモの承認待ちの件数（施設全体。リーダー・施設長だけ。ほかの役割は null で、読まない）。
 * 職員の画面のタブに添える（#437）。画面を開いたときに読むだけで、通知・音は出さない（FR-015）。
 */
export function useWaitingMemoCount(enabled: boolean): number {
  const count = useQuery({
    queryKey: [...APPROVALS_KEY, 'count'],
    queryFn: () => api.get<{ count: number | null }>('/api/staff/memo-approvals/count'),
    enabled,
  })
  return count.data?.count ?? 0
}
