import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { TODAY_VISITS_KEY, type StaffReservation } from './visitReservationRows'

/** 今日の面会予定（今日の予約済み・時刻の順）。今日の面会予定の画面と、入居者一覧の「今日の面会：◯組」で使う。 */
export function useTodayVisits() {
  return useQuery({
    queryKey: TODAY_VISITS_KEY,
    queryFn: () => api.get<StaffReservation[]>('/api/staff/visits/today'),
  })
}
