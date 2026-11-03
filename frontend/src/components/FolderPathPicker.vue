<template>
  <div v-if="visible" class="folder-picker">
    <label class="folder-picker__label" for="folder-picker-0">本地存储位置</label>
    <div
      v-for="(level, index) in levels"
      :key="index"
      class="folder-picker__row"
      :style="{ paddingLeft: `${index * 14}px` }"
    >
      <select
        :id="`folder-picker-${index}`"
        class="folder-picker__select"
        :value="level.value"
        :disabled="level.loading"
        :aria-label="index === 0 ? '存储位置（第一层）' : `存储位置（第 ${index + 1} 层）`"
        @change="onLevelChange(index, $event)"
      >
        <option value="__stop__">{{ level.stopLabel }}</option>
        <option v-for="dir in level.options" :key="dir" :value="dir">{{ dir }}</option>
      </select>
      <span v-if="level.loading" class="folder-picker__loading">读取中…</span>
    </div>
    <p v-if="hint" class="folder-picker__hint" role="alert">{{ hint }}</p>
    <p v-else class="folder-picker__hint">
      {{ selectedText }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { listSubdirs } from '@/utils/localFileSystem'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    /** 第一层「不选择」选项的文案（默认会议名文件夹说明） */
    defaultLabel: string
    /** 未连接本地文件夹时隐藏整个选择器 */
    visible?: boolean
  }>(),
  { visible: true },
)

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const ws = useLocalWorkspace()

const STOP = '__stop__'

interface Level {
  value: string
  options: string[]
  loading: boolean
  stopLabel: string
}

const levels = ref<Level[]>([])
const hint = ref('')

const selectedText = computed(() =>
  props.modelValue.length > 0
    ? `会议文件夹：${props.modelValue.join('/')}`
    : props.defaultLabel,
)

async function loadChildren(prefix: string[]): Promise<string[]> {
  const root = ws.rootHandle.value
  if (!root) {
    return []
  }
  return listSubdirs(root, prefix)
}

/** 重置层级（打开表单/切换目录后调用）：按既有 modelValue 逐层重建，再补一层可继续下钻 */
async function resetLevels(): Promise<void> {
  hint.value = ''
  if (!ws.rootHandle.value) {
    levels.value = []
    return
  }
  const path = [...props.modelValue]
  // 先出一层 loading 占位，避免异步期间无选择框
  levels.value = [
    {
      value: path[0] ?? STOP,
      options: [],
      loading: true,
      stopLabel: path.length === 0 ? props.defaultLabel : '（用当前文件夹作为会议文件夹）',
    },
  ]
  const built: Level[] = []
  try {
    for (let depth = 0; depth <= path.length; depth += 1) {
      const options = await loadChildren(path.slice(0, depth))
      built.push({
        value: depth < path.length ? path[depth] : STOP,
        options,
        loading: false,
        stopLabel:
          depth === 0 ? props.defaultLabel : '（用当前文件夹作为会议文件夹）',
      })
    }
  } catch (caught) {
    hint.value = `无法读取本地文件夹：${messageOf(caught)}（可先「恢复权限」再重试）`
  }
  levels.value = built.length > 0 ? built : levels.value.map((item) => ({ ...item, loading: false }))
}

function messageOf(caught: unknown): string {
  if (typeof caught === 'object' && caught !== null && 'message' in caught) {
    return String((caught as { message: unknown }).message)
  }
  return '读取失败'
}

async function onLevelChange(index: number, event: Event): Promise<void> {
  const picked = (event.target as HTMLSelectElement).value
  const level = levels.value[index]
  if (!level) {
    return
  }
  const base = props.modelValue.slice(0, index)
  if (picked === STOP) {
    // 停在当前层：会议根 = 已选前缀；本层值回到 STOP 并截断更深层级
    emit('update:modelValue', base)
    levels.value = levels.value.slice(0, index + 1).map((item, depth) =>
      depth === index ? { ...item, value: STOP } : item,
    )
    hint.value = ''
    return
  }
  const next = [...base, picked]
  level.value = picked
  emit('update:modelValue', next)
  // 加载更深一层（懒加载子目录）
  const child: Level = {
    value: STOP,
    options: [],
    loading: true,
    stopLabel: '（用当前文件夹作为会议文件夹）',
  }
  const keep = index + 1
  levels.value = [...levels.value.slice(0, keep), child]
  try {
    const options = await loadChildren(next)
    if (options.length === 0) {
      // 没有更深目录：收敛为当前选择
      levels.value = levels.value.slice(0, keep)
    } else {
      levels.value = [...levels.value.slice(0, keep), { ...child, options, loading: false }]
    }
  } catch (caught) {
    hint.value = `无法读取子文件夹：${messageOf(caught)}`
    levels.value = levels.value.slice(0, keep)
  }
}

watch(
  () => [props.visible, ws.rootHandle.value, ws.status.value] as const,
  async ([visible]) => {
    if (visible) {
      await resetLevels()
    }
  },
  { immediate: true },
)

watch(
  () => props.defaultLabel,
  () => {
    if (levels.value[0]) {
      levels.value[0].stopLabel = props.defaultLabel
    }
  },
)
</script>

<style scoped>
.folder-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.folder-picker__label {
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

.folder-picker__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.folder-picker__select {
  flex: 1;
  min-height: 2.4rem;
  padding: 0 var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.folder-picker__select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.folder-picker__loading {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.folder-picker__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}
</style>
