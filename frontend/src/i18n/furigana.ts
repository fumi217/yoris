// ふりがなを出すかどうか（constitution 3.2.0 の UI 方針。#260）。
// 職員の画面・管理画面では出す（初期値）。家族の画面（/family の下）は、FamilyRoutes で false にして出さない。
// 辞書は分けないので、職員と家族が同じ文言（エラーの文言など）を使っても、画面ごとに出し分けられる。

import { createContext } from 'react'

export const FuriganaContext = createContext(true)
