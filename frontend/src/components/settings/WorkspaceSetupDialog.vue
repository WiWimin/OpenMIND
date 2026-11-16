<template>
  <AppModal :open="open" title="绑定本地文件夹" @close="emit('close')">
    <div class="setup-workspace">
      <p class="setup-workspace__hint">
        选择一个本地文件夹，用于存放会议资料与纪要。仅在浏览器授权后访问，不会上传到服务器。
      </p>

      <p v-if="!supported" class="setup-workspace__unsupported">
        当前浏览器不支持本地文件夹访问，可稍后在会议中再配置。
      </p>

      <template v-else>
        <p v-if="wsDirectory" class="setup-workspace__directory">
          已选择：<strong>{{ wsDirectory }}</strong>
        </p>

        <div class="setup-workspace__actions">
          <AppButton variant="ghost" :loading="picking" @click="chooseDirectory">
            {{ connected ? '更换文件夹' : '选择本地文件夹' }}
          </AppButton>
          <AppButton
            v-if="wsStatus === 'needs-permission'"
            variant="ghost"
            :loading="picking"
            @click="restorePermission"
          >
            恢复权限
          </AppButton>
        </div>

        <p v-if="statusText" class="setup-workspace__status" role="status">{{ statusText }}</p>
        <p v-if="error" class="setup-workspace__error" role="alert">{{ error }}</p>
      </template>
    </div>

    <template #footer>
      <AppButton type="button" :disabled="picking" @click="emit('close')">完成</AppButton>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { isLocalWorkspaceSupported } from '@/utils/localFileSystem'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const ws = useLocalWorkspace()

const supported = computed(() => isLocalWorkspaceSupported())
const wsStatus = computed(() => ws.status.value)
const wsDirectory = computed(() => ws.directoryName.value)
const connected = computed(() => wsStatus.value === 'connected')

const picking = ref(false)
const statusText = ref('')
const error = ref('')

function messageOf(caught: unknown): string {
  if (typeof caught === 'object' && caught !== null && 'message' in caught) {
    return String((caught as { message: unknown }).message)
  }
  return '操作失败，请重试'
}

async function chooseDirectory(): Promise<void> {
  picking.value = true
  error.value = ''
  statusText.value = ''
  try {
    const granted = await ws.connect()
    if (!granted) {
      statusText.value =
        wsStatus.value === 'needs-permission'
          ? '本地文件夹权限未授予，点击「恢复权限」重试'
          : '未选择文件夹，可稍后再配置'
      return
    }
    statusText.value = '本地文件夹已绑定'
  } catch (caught) {
    error.value = messageOf(caught)
  } finally {
    picking.value = false
  }
}

async function restorePermission(): Promise<void> {
  picking.value = true
  error.value = ''
  statusText.value = ''
  try {
    const granted = await ws.restore()
    statusText.value = granted ? '本地文件夹权限已恢复' : '未能恢复权限，请重新选择文件夹'
  } catch (caught) {
    error.value = messageOf(caught)
  } finally {
    picking.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      statusText.value = ''
      error.value = ''
      void ws.init()
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.setup-workspace {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.setup-workspace__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
  line-height: 1.6;
}

.setup-workspace__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.setup-workspace__directory {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
}

.setup-workspace__status {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.setup-workspace__unsupported,
.setup-workspace__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}
</style>
