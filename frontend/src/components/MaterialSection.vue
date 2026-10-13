<template>
  <div class="material-section">
    <MaterialUploader :uploading="uploading" @upload="upload" />

    <ErrorMessage v-if="uploadError" :error="uploadError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="material-section__state" />

    <ErrorMessage
      v-else-if="error"
      :error="error"
      retryable
      @retry="refresh()"
    />

    <EmptyState
      v-else-if="items.length === 0"
      title="还没有材料"
      description="上传会议材料（PDF / Word / TXT），供会前准备与问答检索使用。"
    />

    <template v-else>
      <MaterialList :items="items" @delete="askDelete" />
      <AppPagination
        v-if="pagination.total_pages > 1"
        class="material-section__pagination"
        :page="pagination.page"
        :page-size="pagination.page_size"
        :total="pagination.total"
        @update:page="load"
      />
    </template>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <ConfirmDialog
      :open="showDelete"
      title="删除材料"
      message="删除后材料及其解析索引将不可恢复，确定删除吗？"
      confirm-text="删除"
      danger
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import * as materialsApi from '@/api/materials'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MaterialList from '@/components/MaterialList.vue'
import MaterialUploader from '@/components/MaterialUploader.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import type { Material, MaterialUploadPayload } from '@/types/material'

const POLL_INTERVAL_MS = 3000

const props = defineProps<{ meetingId: string }>()

const { items, pagination, loading, error, load } = useAsyncList<Material>({
  fetcher: ({ page, page_size }) => materialsApi.listMaterials(props.meetingId, { page, page_size }),
})

const uploading = ref(false)
const uploadError = ref<unknown>(null)
const actionError = ref<unknown>(null)
const showDelete = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref<string | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null
let isActive = true

const hasProcessing = computed(() =>
  items.value.some((material) => material.processing_status === 'processing'),
)

function stopPolling(): void {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling(): void {
  if (pollTimer !== null) {
    return
  }
  pollTimer = setInterval(() => {
    if (isActive) {
      void load()
    }
  }, POLL_INTERVAL_MS)
}

function refresh(): Promise<void> {
  return load()
}

watch(hasProcessing, (processing) => {
  if (processing) {
    startPolling()
  } else {
    stopPolling()
  }
})

onMounted(() => {
  void refresh()
})

onUnmounted(() => {
  isActive = false
  stopPolling()
})

async function upload(payload: MaterialUploadPayload): Promise<void> {
  uploading.value = true
  uploadError.value = null
  try {
    await materialsApi.uploadMaterial(props.meetingId, payload)
    await load(1)
  } catch (caught) {
    uploadError.value = caught
  } finally {
    uploading.value = false
  }
}

function askDelete(materialId: string): void {
  pendingDeleteId.value = materialId
  showDelete.value = true
}

function cancelDelete(): void {
  showDelete.value = false
  pendingDeleteId.value = null
}

async function confirmDelete(): Promise<void> {
  if (!pendingDeleteId.value) {
    return
  }
  deleting.value = true
  actionError.value = null
  try {
    await materialsApi.deleteMaterial(pendingDeleteId.value)
    showDelete.value = false
    await load()
  } catch (caught) {
    actionError.value = caught
  } finally {
    deleting.value = false
    pendingDeleteId.value = null
  }
}
</script>

<style scoped>
.material-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.material-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.material-section__pagination {
  margin-top: var(--space-2);
}
</style>
