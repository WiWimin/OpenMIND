<template>
  <div class="ai-entry" role="note">
    <span class="ai-entry__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
        <path
          d="M12 3.5 13.6 8.4 18.5 10 13.6 11.6 12 16.5 10.4 11.6 5.5 10 10.4 8.4 12 3.5Z"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
        <path d="M18.5 15.5 19.3 17.7 21.5 18.5 19.3 19.3 18.5 21.5 17.7 19.3 15.5 18.5 17.7 17.7 18.5 15.5Z" fill="currentColor" />
      </svg>
    </span>
    <div class="ai-entry__body">
      <p class="ai-entry__title">AI 助手</p>
      <p class="ai-entry__desc">{{ description }}</p>
    </div>
    <AppButton variant="ghost" @click="emit('go-to-chat')">去提问</AppButton>
  </div>
</template>

<script setup lang="ts">
import AppButton from '@/components/AppButton.vue'

withDefaults(
  defineProps<{ description?: string }>(),
  { description: '此功能由 AI 生成，遇到问题可直接向会议 AI 助手提问。' },
)

const emit = defineEmits<{ 'go-to-chat': [] }>()
</script>

<style scoped>
.ai-entry {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-3);
  background: linear-gradient(135deg, rgba(59, 111, 212, 0.07), rgba(20, 184, 166, 0.07));
  border: 1px solid rgba(59, 111, 212, 0.18);
  border-radius: var(--radius-md);
}

.ai-entry__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.85rem;
  height: 1.85rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-sm);
}

.ai-entry__body {
  flex: 1;
  min-width: 0;
}

.ai-entry__title {
  margin: 0;
  font-size: 0.8125rem;
  font-weight: 700;
  color: var(--color-primary-strong);
}

.ai-entry__desc {
  margin: 2px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}
</style>
