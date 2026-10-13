<template>
  <div class="form-field">
    <label class="form-field__label" :for="id">
      {{ label }}
      <span v-if="required" class="form-field__required" aria-hidden="true">*</span>
    </label>
    <textarea
      :id="id"
      v-model="model"
      class="form-field__control"
      :name="id"
      :rows="rows"
      :placeholder="placeholder"
      :required="required"
      :maxlength="maxlength"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error ? errorId : undefined"
      @blur="emit('blur')"
    />
    <p v-if="error" :id="errorId" class="form-field__error" role="alert">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    id: string
    label: string
    rows?: number
    placeholder?: string
    required?: boolean
    maxlength?: number
    error?: string
  }>(),
  {
    rows: 4,
    placeholder: '',
    required: false,
    maxlength: undefined,
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
  gap: var(--space-1);
}

.form-field__label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-foreground);
}

.form-field__required {
  color: var(--color-down);
}

.form-field__control {
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  color: var(--color-foreground);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font: inherit;
  resize: vertical;
}

.form-field__control:focus {
  border-color: var(--color-primary);
}

.form-field__control[aria-invalid='true'] {
  border-color: var(--color-down);
}

.form-field__error {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--color-down);
}
</style>
