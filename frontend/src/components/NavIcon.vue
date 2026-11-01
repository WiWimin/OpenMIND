<template>
  <svg
    class="nav-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <path
      v-for="(path, index) in paths"
      :key="index"
      :d="path"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 18 })

const ICONS: Record<string, string[]> = {
  home: ['M4 10.2 12 3.8l8 6.4V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1v-9.8Z'],
  plus: ['M12 5.5v13M5.5 12h13'],
  calendar: [
    'M5 5.5h14A1.5 1.5 0 0 1 20.5 7v12A1.5 1.5 0 0 1 19 20.5H5A1.5 1.5 0 0 1 3.5 19V7A1.5 1.5 0 0 1 5 5.5Z',
    'M3.5 10h17M8 3v4M16 3v4',
  ],
  video: [
    'M4 6.5h10A1.5 1.5 0 0 1 15.5 8v8a1.5 1.5 0 0 1-1.5 1.5H4A1.5 1.5 0 0 1 2.5 16V8A1.5 1.5 0 0 1 4 6.5Z',
    'm15.5 10 5-2.5v9l-5-2.5',
  ],
  tasks: ['M4.5 4.5h15v15h-15z', 'm8 12 2.2 2.2L16 8.5'],
  book: [
    'M5 4.5h9.5A3.5 3.5 0 0 1 18 8v11.5H8.5A3.5 3.5 0 0 1 5 16V4.5Z',
    'M5 16a3 3 0 0 1 3-3h10',
  ],
  settings: [
    'M12 8.8a3.2 3.2 0 1 0 0 6.4 3.2 3.2 0 0 0 0-6.4Z',
    'M19.4 13.5a7.8 7.8 0 0 0 0-3l2-1.5-2-3.4-2.4 1a7.5 7.5 0 0 0-2.6-1.5L14 2.5h-4l-.4 2.6A7.5 7.5 0 0 0 7 6.6l-2.4-1-2 3.4 2 1.5a7.8 7.8 0 0 0 0 3l-2 1.5 2 3.4 2.4-1a7.5 7.5 0 0 0 2.6 1.5l.4 2.6h4l.4-2.6a7.5 7.5 0 0 0 2.6-1.5l2.4 1 2-3.4-2-1.5Z',
  ],
  grid: ['M4 4.5h6v6H4zM14 4.5h6v3.5h-6zM4 14h6v5.5H4zM14 11.5h6v8h-6z'],
  file: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M8.5 12h6M8.5 15.5h4',
  ],
  mic: [
    'M12 3.5a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0v-5a3 3 0 0 0-3-3Z',
    'M6.5 11.5v.5a5.5 5.5 0 0 0 11 0v-.5M12 17.5V21M9 21h6',
  ],
  clipboard: [
    'M8 4.5h8M8 4.5A1.5 1.5 0 0 0 6.5 6v13A1.5 1.5 0 0 0 8 20.5h8a1.5 1.5 0 0 0 1.5-1.5V6A1.5 1.5 0 0 0 16 4.5',
    'M8.5 10h7M8.5 13.5h7M8.5 17h4',
  ],
  list: ['M8 6h12M8 12h12M8 18h12', 'M4 6h.01M4 12h.01M4 18h.01'],
  folder: [
    'M3.5 8.5A2.5 2.5 0 0 1 6 6h3.2c.5 0 1 .2 1.4.6l1.6 1.4H18a2.5 2.5 0 0 1 2.5 2.5v6A2.5 2.5 0 0 1 18 19H6a2.5 2.5 0 0 1-2.5-2.5v-8Z',
  ],
  archive: ['M4 4.5h16v4H4zM5.5 8.5v11h13v-11', 'M9.5 12h5'],
  search: ['M10.8 17.6a6.8 6.8 0 1 0 0-13.6 6.8 6.8 0 0 0 0 13.6Z', 'm16 16 4 4'],
  user: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z', 'M4.5 20c0-3.6 3.4-6.5 7.5-6.5s7.5 2.9 7.5 6.5'],
  cpu: [
    'M7 7h10v10H7z',
    'M9.5 3v4M14.5 3v4M9.5 17v4M14.5 17v4M3 9.5h4M3 14.5h4M17 9.5h4M17 14.5h4',
  ],
  sparkle: [
    'M12 3.5 13.7 8.8 19 10.5 13.7 12.2 12 17.5 10.3 12.2 5 10.5 10.3 8.8 12 3.5Z',
    'M18.5 15.5 19.2 17.3 21 18 19.2 18.7 18.5 20.5 17.8 18.7 16 18 17.8 17.3 18.5 15.5Z',
  ],
  chevron: ['M9 5.5 15.5 12 9 18.5'],
  clock: ['M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17Z', 'M12 7.5v4.8l3.2 2'],
  check: ['M4.5 12.5 9.5 17.5 19.5 6.5'],
  bell: [
    'M12 3.5a5.3 5.3 0 0 0-5.3 5.3v3.1l-1.8 3.2a.9.9 0 0 0 .8 1.4h12.6a.9.9 0 0 0 .8-1.4l-1.8-3.2V8.8A5.3 5.3 0 0 0 12 3.5Z',
    'M9.9 19.6a2.2 2.2 0 0 0 4.2 0',
  ],
}

const paths = computed(() => ICONS[props.name] ?? ICONS.grid)
</script>

<style scoped>
.nav-icon {
  flex: 0 0 auto;
  display: block;
}
</style>
