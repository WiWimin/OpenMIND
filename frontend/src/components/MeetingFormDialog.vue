<template>
  <AppModal :open="open" :label="title" overflow-visible @close="emit('cancel')">
    <template #top>
      <div class="meeting-form__deco" aria-hidden="true">
        <span class="meeting-form__ribbon" />
        <img class="meeting-form__mascot" :src="dialogIpUrl" alt="" />
        <span class="meeting-form__bubble">{{ bubble }}</span>
      </div>
    </template>

    <MeetingForm
      :open="open"
      :meeting="meeting"
      :loading="loading"
      :error="error"
      :categories="categories"
      closable
      @submit="emit('submit', $event)"
      @cancel="emit('cancel')"
    />
  </AppModal>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import dialogIpUrl from '@/assets/new-meeting-ip.png'
import AppModal from '@/components/AppModal.vue'
import MeetingForm, { type MeetingFormPayload } from '@/components/MeetingForm.vue'
import type { Meeting } from '@/types/meeting'
import type { MeetingCategory } from '@/utils/meetingCategories'

export type { MeetingFormPayload }

const props = withDefaults(
  defineProps<{
    open: boolean
    meeting?: Meeting | null
    loading?: boolean
    error?: unknown
    categories?: MeetingCategory[]
  }>(),
  {
    meeting: null,
    loading: false,
    categories: () => [],
  },
)

const emit = defineEmits<{ submit: [payload: MeetingFormPayload]; cancel: [] }>()

const title = computed(() => (props.meeting !== null ? '编辑会议' : '新建会议'))
const bubble = computed(() =>
  props.meeting !== null ? '需要调整会议信息吗' : '我来帮你记录会议',
)
</script>

<style scoped>
/* 顶部装饰：渐变条 + 鹦鹉 IP + 气泡（锚定在面板上，可探出顶边） */
.meeting-form__deco {
  pointer-events: none;
}

.meeting-form__ribbon {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 0.875rem;
  background: linear-gradient(92deg, #155eef 0%, #4f7df6 55%, #a855f7 100%);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.meeting-form__mascot {
  position: absolute;
  bottom: 100%;
  right: 4.4rem;
  z-index: 2;
  width: 6.2rem;
  height: auto;
  filter: drop-shadow(0 10px 18px rgba(21, 94, 239, 0.22));
  user-select: none;
}

.meeting-form__bubble {
  position: absolute;
  top: -5.1rem;
  right: 11.4rem;
  z-index: 2;
  padding: 0.5rem 0.95rem;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
  white-space: nowrap;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
}

.meeting-form__bubble::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -5px;
  width: 9px;
  height: 9px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  border-right: 1px solid var(--color-border);
  transform: translateY(-50%) rotate(45deg);
  border-radius: 1px;
}

@media (max-width: 480px) {
  .meeting-form__mascot {
    bottom: 100%;
    right: 1.1rem;
    width: 4.8rem;
  }

  .meeting-form__bubble {
    display: none;
  }
}
</style>
