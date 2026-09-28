import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { computed, h, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import SidebarNavSettings from '~/components/SidebarNavSettings.vue'
import SidebarRail from '~/components/SidebarRail.vue'
import { SIDEBAR_NAV_HIDDEN_KEY } from '~/lib/sidebar-nav'

// SidebarRail 依赖 Nuxt 的自动导入（Vue API 与 useRoute/navigateTo 等），测试里手动补上。
const Stub = { name: 'Stub', render: () => h('div') }

const installNuxtGlobals = () => {
  Object.assign(globalThis, {
    ref,
    computed,
    watch,
    onMounted,
    onBeforeUnmount,
    nextTick,
    h,
    $fetch: async () => ({ accounts: [], default_account: '' }),
    navigateTo: async () => {},
    useApi: () => ({
      deleteChatAccount: async () => ({ status: 'success' }),
      getChatAccountInfo: async () => ({ status: 'error' }),
    }),
    useApiBase: () => '',
    usePlanWindow: () => ({ open: ref(false), openPlanWindow: () => {} }),
    useRoute: () => ({ path: '/chat' }),
    useSettingsDialog: () => ({
      closeDialog: () => {},
      focusTarget: ref(''),
      open: ref(false),
      openDialog: () => {},
    }),
  })
}

const switchOf = (settings, label) => settings.find(`button[aria-label="${label} 显示在左侧栏"]`)

describe('设置里的侧边栏开关', () => {
  let rail
  let settings

  const mountPair = async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    rail = mount(SidebarRail, {
      global: {
        components: {
          AdvancedFeaturesDialog: Stub,
          ErrorNotice: Stub,
          GlobalExportDialog: Stub,
        },
        plugins: [pinia],
      },
    })
    settings = mount(SidebarNavSettings, { global: { plugins: [pinia] } })
    await flushPromises()
    return { rail, settings }
  }

  beforeEach(() => {
    installNuxtGlobals()
    // lib/sidebar-nav 的读写都挂在 process.client 上
    process.client = true
    localStorage.clear()
  })

  afterEach(() => {
    rail?.unmount()
    settings?.unmount()
    rail = undefined
    settings = undefined
    delete process.client
  })

  it('关掉「高级功能演示」后侧边栏按钮消失，其它按钮不受影响', async () => {
    await mountPair()

    expect(rail.find('[title="高级功能演示"]').exists()).toBe(true)
    expect(rail.find('[title="套餐与额度"]').exists()).toBe(true)

    await switchOf(settings, '高级功能演示').trigger('click')
    await nextTick()

    expect(rail.find('[title="高级功能演示"]').exists()).toBe(false)
    expect(rail.find('[title="套餐与额度"]').exists()).toBe(true)
    expect(rail.find('[title="聊天"]').exists()).toBe(true)
    expect(switchOf(settings, '高级功能演示').attributes('aria-checked')).toBe('false')
    expect(settings.text()).toContain('已隐藏，左侧栏不再显示该按钮')

    await switchOf(settings, '高级功能演示').trigger('click')
    await nextTick()
    expect(rail.find('[title="高级功能演示"]').exists()).toBe(true)
  })

  it('逐个开关互不干扰，「全部显示」一键恢复', async () => {
    await mountPair()

    await switchOf(settings, '朋友圈').trigger('click')
    await switchOf(settings, '套餐与额度').trigger('click')
    await nextTick()

    expect(rail.find('[title="朋友圈"]').exists()).toBe(false)
    expect(rail.find('[title="套餐与额度"]').exists()).toBe(false)
    expect(rail.find('[title="联系人"]').exists()).toBe(true)
    expect(JSON.parse(localStorage.getItem(SIDEBAR_NAV_HIDDEN_KEY))).toEqual(['sns', 'plan'])

    const showAllButton = settings.findAll('button').find((button) => button.text() === '全部显示')
    expect(showAllButton).toBeTruthy()
    await showAllButton.trigger('click')
    await nextTick()

    expect(rail.find('[title="朋友圈"]').exists()).toBe(true)
    expect(rail.find('[title="套餐与额度"]').exists()).toBe(true)
    expect(JSON.parse(localStorage.getItem(SIDEBAR_NAV_HIDDEN_KEY))).toEqual([])
  })

  it('隐藏状态写进 localStorage，重新挂载侧边栏后依然隐藏', async () => {
    await mountPair()
    await switchOf(settings, '套餐与额度').trigger('click')
    await nextTick()
    rail.unmount()
    settings.unmount()

    const pinia = createPinia()
    setActivePinia(pinia)
    rail = mount(SidebarRail, {
      global: {
        components: {
          AdvancedFeaturesDialog: Stub,
          ErrorNotice: Stub,
          GlobalExportDialog: Stub,
        },
        plugins: [pinia],
      },
    })
    await flushPromises()

    expect(rail.find('[title="套餐与额度"]').exists()).toBe(false)
    expect(rail.find('[title="高级功能演示"]').exists()).toBe(true)
  })
})
