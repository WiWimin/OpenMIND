<template>
  <router-view />
</template>

<script setup lang="ts">
import { watch } from 'vue'

import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useAuthStore } from '@/stores/auth'

// 本地工作区必须按登录用户初始化：句柄在 IndexedDB 里按 userId 隔离，
// 未登录/切换账号时不能沿用上一个账号的目录。
const auth = useAuthStore()
const workspace = useLocalWorkspace()

watch(
  () => auth.user?.user_id,
  (next) => {
    if (next) {
      void workspace.init(next)
    } else {
      void workspace.disconnect()
    }
  },
  { immediate: true },
)
</script>
