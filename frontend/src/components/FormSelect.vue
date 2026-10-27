<template>
  <div class="form-field">
    <label class="form-field__label" :for="id">
      {{ label }}
      <span v-if="required" class="form-field__required" aria-hidden="true">*</span>
    </label>
    <select
      :id="id"
      v-model="model"
      class="form-field__control"
      :name="id"
      :required="required"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? errorId : undefined"
      @blur="emit('blur')"
    >
      <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <p v-if="error" :id="errorId" class="form-field__error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { SelectOption } from '@/types/ui'

const props = withDefaults(
  defineProps<{
    id: string
    label: string
    options: SelectOption[]
    placeholder?: string
    required?: boolean
    error?: string
  }>(),
  {
    placeholder: '',
    required: false,
    error: '',
  },
)

const emit = defineEmits<{ blur: [] }>()

const model = defineModel<string>({ required: true })
const errorId = computed(() => `${props.id}-error`)
</script>

<style scoped>
.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field__label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-foreground);
}

.form-field__required {
  color: var(--color-down);
}

.form-field__control {
  min-height: 2.6rem;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  color: var(--color-foreground);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font: inherit;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.form-field__control:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59, 111, 212, 0.16);
}

.form-field__control[aria-invalid='true'] {
  border-color: var(--color-down);
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.13);
}

.form-field__error {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--color-down);
}
</style>
