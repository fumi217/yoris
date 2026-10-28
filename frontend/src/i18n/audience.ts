// 家族の画面（/family の下）かどうか。FamilyRoutes で true にする（初期値は職員・管理画面・ログイン・申し込みの false）。
// 同じエラーのキーでも、家族の画面だけ別の言い方にしたいとき、辞書に `<キー>_family` を足す（Text が引き分ける。#79）。

import { createContext } from 'react'

export const FamilyContext = createContext(false)
