<template>
  <div class="form-field">
    <label class="form-field__label" :for="id">
      {{ label }}
      <span v-if="required" class="form-field__required" aria-hidden="true">*</span>
    </label>
    <input
      :id="id"
      v-model="model"
      class="form-field__input"
      :type="type"
      :name="id"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :required="required"
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
    type?: string
    autocomplete?: string
    placeholder?: string
    required?: boolean
    error?: string
  }>(),
  {
    type: 'text',
    autocomplete: 'off',
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

.form-field__input {
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

.form-field__input::placeholder {
  color: var(--color-muted-foreground);
}

.form-field__input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.form-field__input[aria-invalid='true'] {
  border-color: var(--color-down);
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.13);
}

.form-field__error {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--color-down);
}

@media (max-width: 640px) {
  .form-field__input {
    min-height: 2.75rem;
  }
}
</style>
