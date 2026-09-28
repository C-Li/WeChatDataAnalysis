import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import vm from 'node:vm'

const createStorage = (initial = {}) => {
  const map = new Map(Object.entries(initial))
  return {
    getItem: (key) => (map.has(String(key)) ? map.get(String(key)) : null),
    setItem: (key, value) => { map.set(String(key), String(value)) },
    removeItem: (key) => { map.delete(String(key)) },
  }
}

const process_ = { client: true }

const loadLib = async (storage) => {
  const source = await readFile(new URL('../lib/sidebar-nav.js', import.meta.url), 'utf8')
  const context = vm.createContext({ localStorage: storage, process: process_ })
  const executable = source
    .replace(/export const /g, 'const ')
    .concat('\nthis.lib = { SIDEBAR_NAV_HIDDEN_KEY, SIDEBAR_NAV_ITEMS, normalizeHiddenSidebarNavKeys, readHiddenSidebarNavKeys, writeHiddenSidebarNavKeys }')
  vm.runInContext(executable, context)
  return context.lib
}

const createStore = async (storage, lib) => {
  const source = await readFile(new URL('../stores/sidebarNav.js', import.meta.url), 'utf8')
  const context = vm.createContext({
    defineStore: (_name, setup) => setup,
    localStorage: storage,
    normalizeHiddenSidebarNavKeys: lib.normalizeHiddenSidebarNavKeys,
    process: process_,
    readHiddenSidebarNavKeys: lib.readHiddenSidebarNavKeys,
    ref: (value) => ({ value }),
    writeHiddenSidebarNavKeys: lib.writeHiddenSidebarNavKeys,
  })
  const executable = source
    .replace(/import[\s\S]*?from\s*'[^']+'\s*/g, '')
    .replace('export const useSidebarNavStore', 'const useSidebarNavStore')
    .concat('\nthis.store = useSidebarNavStore()')
  vm.runInContext(executable, context)
  return context.store
}

test('侧边栏可隐藏项按固定顺序去重并丢弃失效 key', async () => {
  const lib = await loadLib(createStorage())

  assert.deepEqual(
    Array.from(lib.SIDEBAR_NAV_ITEMS, (item) => item.key),
    ['sns', 'advanced', 'plan', 'favorites', 'contacts', 'biz', 'mini-programs', 'finder', 'payments', 'wrapped'],
  )
  assert.deepEqual(
    Array.from(lib.normalizeHiddenSidebarNavKeys(['wrapped', 'sns', 'wrapped', 'ghost', 42])),
    ['sns', 'wrapped'],
  )
})

test('隐藏列表写入 localStorage 不丢 key，读取时才按当前列表清理', async () => {
  const storage = createStorage()
  const lib = await loadLib(storage)

  assert.deepEqual(Array.from(lib.readHiddenSidebarNavKeys()), [])

  // 写入只去重：列表过期（热更新）时也不能把开关状态吞掉。
  lib.writeHiddenSidebarNavKeys(['payments', 'sns', 'unknown-item', 'sns'])
  const raw = storage.getItem(lib.SIDEBAR_NAV_HIDDEN_KEY)
  assert.deepEqual(JSON.parse(raw), ['payments', 'sns', 'unknown-item'])
  assert.deepEqual(Array.from(lib.readHiddenSidebarNavKeys()), ['sns', 'payments'])
})

test('存储内容损坏时回退到默认（全部显示）', async () => {
  const storage = createStorage({ 'ui.sidebar_nav_hidden': '{ 这不是合法 JSON' })
  const lib = await loadLib(storage)

  assert.deepEqual(Array.from(lib.readHiddenSidebarNavKeys()), [])

  storage.setItem('ui.sidebar_nav_hidden', '"sns"')
  assert.deepEqual(Array.from(lib.readHiddenSidebarNavKeys()), [])
})

test('init 前保持全部显示，init 后按存储隐藏，且 init 幂等', async () => {
  const storage = createStorage({ 'ui.sidebar_nav_hidden': JSON.stringify(['sns', 'contacts']) })
  const lib = await loadLib(storage)
  const store = await createStore(storage, lib)

  // 服务端渲染 / hydration 阶段就是这个状态：全部按钮可见。
  assert.deepEqual(Array.from(store.hiddenKeys.value), [])

  store.init()
  assert.equal(store.initialized.value, true)
  assert.deepEqual(Array.from(store.hiddenKeys.value), ['sns', 'contacts'])
  assert.equal(store.isHidden('sns'), true)
  assert.equal(store.isHidden('favorites'), false)

  store.toggle('favorites')
  store.toggle('sns')
  store.init()
  // 写入阶段不做列表过滤（保留插入顺序），读取时才按 SIDEBAR_NAV_ITEMS 归一。
  assert.deepEqual(Array.from(store.hiddenKeys.value), ['contacts', 'favorites'])
  assert.deepEqual(JSON.parse(storage.getItem(lib.SIDEBAR_NAV_HIDDEN_KEY)), ['contacts', 'favorites'])
  assert.deepEqual(Array.from(lib.readHiddenSidebarNavKeys()), ['favorites', 'contacts'])
})

test('store 不会吞掉当前列表里还没有的 key（热更新后新增按钮的开关必须有效）', async () => {
  const storage = createStorage()
  const lib = await loadLib(storage)
  const store = await createStore(storage, lib)
  store.init()

  store.setHidden('future-button', true)
  assert.equal(store.isHidden('future-button'), true)
  assert.deepEqual(JSON.parse(storage.getItem(lib.SIDEBAR_NAV_HIDDEN_KEY)), ['future-button'])

  store.setHidden('sns', true)
  assert.deepEqual(JSON.parse(storage.getItem(lib.SIDEBAR_NAV_HIDDEN_KEY)), ['future-button', 'sns'])

  store.setHidden('future-button', false)
  assert.equal(store.isHidden('future-button'), false)
  assert.deepEqual(JSON.parse(storage.getItem(lib.SIDEBAR_NAV_HIDDEN_KEY)), ['sns'])
})

test('showAll 恢复全部按钮并清空存储', async () => {
  const storage = createStorage({ 'ui.sidebar_nav_hidden': JSON.stringify(['payments', 'wrapped']) })
  const lib = await loadLib(storage)
  const store = await createStore(storage, lib)

  store.init()
  assert.equal(store.isHidden('payments'), true)

  store.showAll()
  assert.deepEqual(Array.from(store.hiddenKeys.value), [])
  assert.deepEqual(JSON.parse(storage.getItem(lib.SIDEBAR_NAV_HIDDEN_KEY)), [])

  store.setHidden('finder', true)
  assert.equal(store.isHidden('finder'), true)
  store.setHidden('finder', false)
  assert.equal(store.isHidden('finder'), false)
})
