<template>
  <nav class="app-breadcrumb" aria-label="面包屑">
    <ol class="app-breadcrumb__list">
      <li
        v-for="(item, index) in items"
        :key="`${item.label}-${index}`"
        class="app-breadcrumb__item"
      >
        <RouterLink
          v-if="item.to && index < items.length - 1"
          class="app-breadcrumb__link"
          :to="item.to"
        >
          {{ item.label }}
        </RouterLink>
        <button
          v-else-if="item.onClick && index < items.length - 1"
          type="button"
          class="app-breadcrumb__link app-breadcrumb__link--button"
          @click="item.onClick()"
        >
          {{ item.label }}
        </button>
        <span
          v-else
          class="app-breadcrumb__current"
          :aria-current="index === items.length - 1 ? 'page' : undefined"
        >
          {{ item.label }}
        </span>
        <span v-if="index < items.length - 1" class="app-breadcrumb__separator" aria-hidden="true">
          /
        </span>
      </li>
    </ol>
  </nav>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

defineProps<{
  items: { label: string; to?: RouteLocationRaw; onClick?: () => void }[]
}>()
</script>

<style scoped>
.app-breadcrumb {
  margin-bottom: var(--space-3);
}

.app-breadcrumb__list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.app-breadcrumb__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.app-breadcrumb__link {
  color: var(--color-muted-foreground);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.app-breadcrumb__link--button {
  padding: 0;
  font: inherit;
  font-size: 0.75rem;
  background: none;
  border: 0;
  cursor: pointer;
}

.app-breadcrumb__link:hover {
  color: var(--color-primary-strong);
}

.app-breadcrumb__current {
  color: var(--color-foreground);
  font-weight: 550;
}

.app-breadcrumb__separator {
  color: var(--color-border-strong);
}
</style>
