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
      <MaterialList :items="items" @delete="askDelete" @view="askView" />
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

    <AppModal :open="viewTarget !== null" title="资料详情" @close="pendingViewId = null">
      <dl v-if="viewTarget" class="material-detail">
        <div class="material-detail__row">
          <dt>文件名</dt>
          <dd>{{ viewTarget.file_name }}</dd>
        </div>
        <div class="material-detail__row">
          <dt>类型</dt>
          <dd>{{ viewTarget.type.toUpperCase() }}</dd>
        </div>
        <div class="material-detail__row">
          <dt>来源</dt>
          <dd>{{ viewTarget.source ?? '未填写' }}</dd>
        </div>
        <div class="material-detail__row">
          <dt>上传时间</dt>
          <dd>{{ createdAtOf(viewTarget) }}</dd>
        </div>
        <div class="material-detail__row">
          <dt>处理状态</dt>
          <dd>{{ statusOf(viewTarget) }}</dd>
        </div>
        <div v-if="viewTarget.parse_error" class="material-detail__row">
          <dt>解析错误</dt>
          <dd class="material-detail__error">{{ viewTarget.parse_error }}</dd>
        </div>
      </dl>
      <template #footer>
        <AppButton variant="ghost" @click="pendingViewId = null">关闭</AppButton>
      </template>
    </AppModal>

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
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MaterialList from '@/components/MaterialList.vue'
import MaterialUploader from '@/components/MaterialUploader.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import type { Material, MaterialUploadPayload } from '@/types/material'
import { formatDateTime } from '@/utils/datetime'
import { materialStatusMeta } from '@/utils/statusLabels'

const POLL_INTERVAL_MS = 3000

const props = defineProps<{ meetingId: string }>()

const toast = useToast()

const { items, pagination, loading, error, load } = useAsyncList<Material>({
  fetcher: ({ page, page_size }) => materialsApi.listMaterials(props.meetingId, { page, page_size }),
})

const uploading = ref(false)
const uploadError = ref<unknown>(null)
const actionError = ref<unknown>(null)
const showDelete = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref<string | null>(null)
const pendingViewId = ref<string | null>(null)

const viewTarget = computed(
  () => items.value.find((item) => item.material_id === pendingViewId.value) ?? null,
)

function askView(materialId: string): void {
  pendingViewId.value = materialId
}

function createdAtOf(material: Material): string {
  return formatDateTime(material.created_at)
}

function statusOf(material: Material): string {
  return materialStatusMeta[material.processing_status].label
}

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
    toast.success('资料已上传')
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
    toast.success('资料已删除')
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

.material-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
}

.material-detail__row {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr);
  gap: var(--space-3);
  align-items: baseline;
}

.material-detail__row dt {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
}

.material-detail__row dd {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
  overflow-wrap: anywhere;
}

.material-detail__error {
  color: var(--color-down);
}
</style>
