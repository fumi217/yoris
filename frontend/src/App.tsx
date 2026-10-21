import { useQuery } from '@tanstack/react-query'
import { Route, Routes } from 'react-router'

// 骨組みの確認用の画面。家族・職員・管理画面の枠と、役割で画面を分けるルーティングは T019 で作る
function Home() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await fetch('/api/health')
      if (!response.ok) throw new Error(`status ${response.status}`)
      return (await response.json()) as { status: string }
    },
  })

  return (
    <main className="mx-auto max-w-xl p-6">
      <h1 className="text-2xl font-bold">家族連絡アプリ</h1>
      <p className="mt-4">
        バックエンドとの接続：
        {health.isPending && '確認中'}
        {health.isError && 'つながりません'}
        {health.isSuccess && health.data.status}
      </p>
    </main>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
    </Routes>
  )
}
