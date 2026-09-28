export const SIDEBAR_NAV_HIDDEN_KEY = 'ui.sidebar_nav_hidden'

// 侧边栏中允许单独隐藏的“功能页入口 / 弹窗入口”。
// 头像、聊天、导出、隐私、主题、引导、设置固定显示 ——
// 尤其是设置，必须始终能打开，否则用户藏掉按钮后无法再恢复。
export const SIDEBAR_NAV_ITEMS = [
  { key: 'sns', label: '朋友圈' },
  { key: 'advanced', label: '高级功能演示' },
  { key: 'plan', label: '套餐与额度' },
  { key: 'favorites', label: '收藏' },
  { key: 'contacts', label: '联系人' },
  { key: 'biz', label: '服务号' },
  { key: 'mini-programs', label: '小程序' },
  { key: 'finder', label: '视频号 / 直播' },
  { key: 'payments', label: '转账 / 红包' },
  { key: 'wrapped', label: '年度总结' },
]

export const sidebarNavKeys = () => SIDEBAR_NAV_ITEMS.map((item) => item.key)

// 只做去重和字符串化，不校验 key 是否还存在于 SIDEBAR_NAV_ITEMS。
// 写入如果按列表过滤，一旦 store 持有的是热更新前的旧列表（Vite HMR 下很常见），
// 新增的 key 会被静默丢掉 —— 表现就是「点开关没反应」。
const dedupeKeys = (value) => {
  const list = Array.isArray(value) ? value : []
  const seen = new Set()
  const result = []
  for (const raw of list) {
    const key = String(raw)
    if (seen.has(key)) continue
    seen.add(key)
    result.push(key)
  }
  return result
}

// 按 SIDEBAR_NAV_ITEMS 的顺序去重，顺带丢掉已失效的 key（比如旧版本遗留的项）。
// 只在读取时做清理：读取发生在页面加载后，此时模块列表是最新的。
export const normalizeHiddenSidebarNavKeys = (value) => {
  const selected = new Set(dedupeKeys(value))
  return sidebarNavKeys().filter((key) => selected.has(key))
}

export const readHiddenSidebarNavKeys = (fallback = []) => {
  const normalizedFallback = normalizeHiddenSidebarNavKeys(fallback)
  if (!process.client) return normalizedFallback
  try {
    const raw = localStorage.getItem(SIDEBAR_NAV_HIDDEN_KEY)
    if (raw == null) return normalizedFallback
    const parsed = JSON.parse(raw)
    return normalizeHiddenSidebarNavKeys(parsed)
  } catch {
    return normalizedFallback
  }
}

// 原样落盘（只去重），不依赖当前列表，避免上面提到的丢 key 问题。
export const writeHiddenSidebarNavKeys = (keys) => {
  if (!process.client) return
  try {
    localStorage.setItem(SIDEBAR_NAV_HIDDEN_KEY, JSON.stringify(dedupeKeys(keys)))
  } catch {}
}
