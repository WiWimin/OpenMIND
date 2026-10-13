<template>
  <AppModal :open="open" :title="title" @close="emit('cancel')">
    <p class="confirm-dialog__message">{{ message }}</p>

    <template #footer>
      <AppButton variant="ghost" :disabled="loading" @click="emit('cancel')">
        {{ cancelText }}
      </AppButton>
      <AppButton
        :variant="danger ? 'danger' : 'primary'"
        :loading="loading"
        @click="emit('confirm')"
      >
        {{ confirmText }}
      </AppButton>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'

withDefaults(
  defineProps<{
    open: boolean
    message: string
    title?: string
    confirmText?: string
    cancelText?: string
    danger?: boolean
    loading?: boolean
  }>(),
  {
    title: '请确认',
    confirmText: '确定',
    cancelText: '取消',
    danger: false,
    loading: false,
  },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<style scoped>
.confirm-dialog__message {
  margin: 0;
  color: var(--color-foreground);
}
</style>
