import { defineStore } from 'pinia'

import {
  readHiddenSidebarNavKeys,
  writeHiddenSidebarNavKeys,
} from '~/lib/sidebar-nav'

export const useSidebarNavStore = defineStore('sidebarNav', () => {
  // 初始为空：服务端渲染与客户端 hydration 阶段都渲染全部按钮，
  // 读取 localStorage 放到 init()（由 onMounted 调用），避免 v-if 造成 hydration 不一致。
  const hiddenKeys = ref([])
  const initialized = ref(false)

  const isHidden = (key) => hiddenKeys.value.includes(String(key))

  const init = () => {
    if (!process.client || initialized.value) return
    initialized.value = true
    hiddenKeys.value = readHiddenSidebarNavKeys(hiddenKeys.value)
  }

  // 不按 SIDEBAR_NAV_ITEMS 过滤：key 是否“认识”只在读取时清理一次。
  // 这里过滤的话，store 里缓存的列表一旦过期（热更新后常见），
  // 新增按钮的开关就会点了没反应。
  const setHidden = (key, hidden) => {
    const current = Array.isArray(hiddenKeys.value) ? hiddenKeys.value : []
    const name = String(key)
    const next = hidden
      ? [...new Set([...current.map(String), name])]
      : current.map(String).filter((item) => item !== name)
    hiddenKeys.value = next
    writeHiddenSidebarNavKeys(next)
  }

  const toggle = (key) => {
    setHidden(key, !isHidden(key))
  }

  const showAll = () => {
    hiddenKeys.value = []
    writeHiddenSidebarNavKeys([])
  }

  return {
    hiddenKeys,
    initialized,
    isHidden,
    init,
    setHidden,
    toggle,
    showAll,
  }
})
