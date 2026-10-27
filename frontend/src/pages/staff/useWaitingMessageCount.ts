import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { MESSAGES_KEY, type MessageCount } from './messagesView'

/**
 * 家族からのメッセージの対応待ちの件数（施設全体）。管理画面のトップの入り口に添える（#88）。
 * 画面を開いたときに読むだけで、通知・音は出さない（FR-013）。読めなくても入り口は出す（件数だけ出さない）。
 */
export function useWaitingMessageCount(): number {
  const count = useQuery({
    queryKey: [...MESSAGES_KEY, 'count'],
    queryFn: () => api.get<MessageCount>('/api/staff/messages/count'),
  })
  return count.data?.count ?? 0
}
