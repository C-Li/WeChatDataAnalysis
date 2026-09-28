<template>
  <div>
    <div class="mb-2.5 text-[12px] font-bold text-[#999] tracking-widest">侧边栏</div>
    <div class="overflow-hidden rounded-[10px] border border-[#e7e7e7] bg-white divide-y divide-[#ececec]">
      <div class="px-3.5 py-3">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="text-[13px] font-medium text-[#222]">功能页入口</div>
            <div class="mt-0.5 text-[11px] leading-relaxed text-[#909090]">逐个控制左侧栏按钮的显示与隐藏，设置立即生效并保存在本机。头像、聊天、导出、隐私、主题、引导、设置始终显示。</div>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-[6px] border border-[#e2e2e2] bg-[#fafafa] px-2.5 py-1 text-[12px] text-[#222] transition hover:bg-[#f0f0f0] disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!hiddenNavKeys.length"
            @click="sidebarNavStore.showAll()"
          >
            全部显示
          </button>
        </div>
      </div>

      <div v-for="item in sidebarNavItems" :key="item.key" class="px-3.5 py-3">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="text-[13px] font-medium text-[#222]">{{ item.label }}</div>
            <div class="mt-0.5 text-[11px] text-[#909090]">{{ hiddenNavKeys.includes(item.key) ? '已隐藏，左侧栏不再显示该按钮' : '显示中' }}</div>
          </div>
          <button
            type="button"
            role="switch"
            :aria-checked="!hiddenNavKeys.includes(item.key)"
            :aria-label="`${item.label} 显示在左侧栏`"
            class="settings-switch shrink-0"
            :class="switchTrackClass(!hiddenNavKeys.includes(item.key))"
            @click="sidebarNavStore.toggle(item.key)"
          >
            <span class="settings-switch-thumb" :class="!hiddenNavKeys.includes(item.key) ? 'translate-x-[20px]' : 'translate-x-0'" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { onMounted } from 'vue'

import { SIDEBAR_NAV_ITEMS } from '~/lib/sidebar-nav'
import { useSidebarNavStore } from '~/stores/sidebarNav'

const sidebarNavStore = useSidebarNavStore()
const { hiddenKeys: hiddenNavKeys } = storeToRefs(sidebarNavStore)
const sidebarNavItems = SIDEBAR_NAV_ITEMS

const switchTrackClass = (enabled) => (enabled ? 'bg-[#07b75b] hover:brightness-95' : 'bg-[#d0d0d0] hover:brightness-95')

onMounted(() => {
  sidebarNavStore.init()
})
</script>

<style scoped>
.settings-switch {
  width: 44px;
  height: 24px;
  border-radius: 999px;
  padding: 2px;
  transition: background-color 0.16s ease, opacity 0.16s ease, filter 0.16s ease;
}

.settings-switch-thumb {
  display: block;
  height: 20px;
  width: 20px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.24);
  transition: transform 0.16s ease;
}
</style>
