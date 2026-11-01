<template>
  <router-view />
</template>

<script setup lang="ts">
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'

// 应用启动即恢复本地工作区句柄与授权状态，
// 使任意页面（含刷新后直达的详情页）都能使用本地文件夹能力（幂等）。
void useLocalWorkspace().init()
</script>
