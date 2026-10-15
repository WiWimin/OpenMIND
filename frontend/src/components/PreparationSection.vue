<template>
  <div class="preparation-section">
    <div class="preparation-section__toolbar">
      <FormTextarea
        id="preparation-goal"
        v-model="userGoal"
        label="准备目标（可选）"
        :rows="2"
        placeholder="例如：确认本周里程碑与待解决风险"
      />
      <AppButton :loading="generating" @click="generate">生成准备稿</AppButton>
    </div>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="preparation-section__state" />

    <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />

    <EmptyState
      v-else-if="items.length === 0"
      title="还没有准备稿"
      description="基于会议材料生成会前摘要与准备清单草稿。"
    />

    <div v-else class="preparation-section__body">
      <ul class="preparation-section__list">
        <li v-for="item in items" :key="item.preparation_id">
          <button
            type="button"
            class="preparation-section__item"
            :class="{
              'preparation-section__item--active': selected?.preparation_id === item.preparation_id,
            }"
            @click="select(item)"
          >
            <StatusBadge :label="statusOf(item).label" :tone="statusOf(item).tone" />
            <span class="preparation-section__time">{{ timeOf(item) }}</span>
          </button>
        </li>
      </ul>

      <div v-if="selected" class="preparation-section__editor">
        <div class="preparation-section__editor-head">
          <StatusBadge :label="statusOf(selected).label" :tone="statusOf(selected).tone" />
          <span class="preparation-section__version">v{{ selected.version }}</span>
        </div>

        <FormTextarea id="preparation-summary" v-model="draftSummary" label="会前摘要" :rows="6" />
        <FormTextarea
          id="preparation-checklist"
          v-model="draftChecklist"
          label="准备清单（每行一项）"
          :rows="6"
        />

        <div class="preparation-section__actions">
          <AppButton :loading="saving" @click="save">保存</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as preparationsApi from '@/api/preparations'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import type { Preparation } from '@/types/preparation'
import { formatDateTime } from '@/utils/datetime'
import { preparationStatusMeta } from '@/utils/statusLabels'

const props = defineProps<{ meetingId: string }>()

const { items, loading, error, load } = useAsyncList<Preparation>({
  fetcher: ({ page, page_size }) =>
    preparationsApi.listPreparations(props.meetingId, { page, page_size }),
})

const userGoal = ref('')
const selected = ref<Preparation | null>(null)
const draftSummary = ref('')
const draftChecklist = ref('')
const generating = ref(false)
const saving = ref(false)
const actionError = ref<unknown>(null)

function statusOf(preparation: Preparation) {
  return preparationStatusMeta[preparation.status]
}

function timeOf(preparation: Preparation): string {
  return formatDateTime(preparation.created_at)
}

function select(preparation: Preparation): void {
  selected.value = preparation
  draftSummary.value = preparation.summary
  draftChecklist.value = preparation.checklist.join('\n')
}

function syncSelected(updated: Preparation): void {
  if (selected.value?.preparation_id === updated.preparation_id) {
    selected.value = updated
    draftSummary.value = updated.summary
    draftChecklist.value = updated.checklist.join('\n')
  }
}

function refresh(): Promise<void> {
  return load()
}

onMounted(() => {
  void refresh()
})

async function generate(): Promise<void> {
  generating.value = true
  actionError.value = null
  try {
    const preparation = await preparationsApi.generatePreparation(props.meetingId, {
      include_history: true,
      user_goal: userGoal.value.trim() || undefined,
    })
    await load(1)
    select(preparation)
  } catch (caught) {
    actionError.value = caught
  } finally {
    generating.value = false
  }
}

async function save(): Promise<void> {
  if (!selected.value) {
    return
  }
  saving.value = true
  actionError.value = null
  try {
    const checklist = draftChecklist.value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
    const updated = await preparationsApi.updatePreparation(selected.value.preparation_id, {
      summary: draftSummary.value,
      checklist,
    })
    syncSelected(updated)
    await load()
  } catch (caught) {
    actionError.value = caught
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.preparation-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.preparation-section__toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-start;
}

.preparation-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.preparation-section__body {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: minmax(10rem, 16rem) 1fr;
}

.preparation-section__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.preparation-section__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font: inherit;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.preparation-section__item:hover {
  background: var(--color-surface-strong);
  border-color: var(--color-border-strong);
}

.preparation-section__item--active {
  border-color: var(--color-primary);
  background: rgba(99, 102, 241, 0.07);
}

.preparation-section__time {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.preparation-section__editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.preparation-section__editor-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.preparation-section__version {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.preparation-section__actions {
  display: flex;
  gap: var(--space-2);
}
</style>
