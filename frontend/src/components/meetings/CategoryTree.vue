<template>
  <nav class="category-tree" aria-label="会议文件夹树">
    <!-- 全部会议 -->
    <div
      class="tree-row"
      :class="{ 'tree-row--active': selectedKey === 'all' }"
    >
      <button type="button" class="tree-row__main" @click="$emit('select-all')">
        <span class="tree-row__icon" aria-hidden="true"><NavIcon name="grid" :size="15" /></span>
        <span class="tree-row__name">全部会议</span>
        <span class="tree-row__count">{{ totalCount }}</span>
      </button>
    </div>

    <!-- 分类（可展开 → 缩进显示其下会议） -->
    <div v-for="category in categories" :key="category.id" class="tree-branch">
      <div
        class="tree-row"
        :class="{ 'tree-row--active': selectedKey === `cat:${category.id}` }"
      >
        <button
          type="button"
          class="tree-row__chevron"
          :class="{ 'tree-row__chevron--open': isExpanded(category.id) }"
          :aria-expanded="isExpanded(category.id)"
          :aria-label="isExpanded(category.id) ? `收起「${category.name}」` : `展开「${category.name}」`"
          @click="$emit('toggle', category.id)"
        >
          <NavIcon name="chevron" :size="13" />
        </button>
        <button type="button" class="tree-row__main" @click="$emit('select-category', category.id)">
          <span class="tree-row__icon" aria-hidden="true"><NavIcon name="folder" :size="15" /></span>
          <span class="tree-row__name">{{ category.name }}</span>
          <span class="tree-row__count">{{ category.meetings.length }}</span>
        </button>
        <button
          type="button"
          class="tree-row__more"
          aria-label="分类更多操作"
          :aria-expanded="menuId === category.id"
          @click.stop="toggleMenu(category.id)"
        >
          <NavIcon name="more" :size="15" />
        </button>

        <!-- hover/点击出现的更多菜单：次要操作收纳 -->
        <div
          v-if="menuId === category.id"
          class="tree-row__menu"
          role="menu"
          @click.stop
        >
          <button type="button" class="tree-row__menu-item" role="menuitem" @click="startRename(category)">
            重命名
          </button>
          <button
            type="button"
            class="tree-row__menu-item tree-row__menu-item--danger"
            role="menuitem"
            @click="askRemove(category)"
          >
            删除分类
          </button>
        </div>
      </div>

      <!-- 重命名（原地输入） -->
      <div v-if="renamingId === category.id" class="tree-rename">
        <input
          :ref="setRenameInput"
          v-model="renameValue"
          class="tree-rename__input"
          type="text"
          maxlength="40"
          aria-label="分类名称"
          @keyup.enter="commitRename"
          @keyup.escape="cancelRename"
        />
        <button type="button" class="tree-rename__save" :disabled="!renameValue.trim()" @click="commitRename">
          保存
        </button>
      </div>

      <!-- 展开后的会议子节点（缩进） -->
      <ul v-if="isExpanded(category.id)" class="tree-children">
        <li v-for="meeting in category.meetings" :key="meeting.meeting_id">
          <button
            type="button"
            class="tree-meeting"
            :class="{ 'tree-meeting--active': activeMeetingId === meeting.meeting_id }"
            @click="$emit('select-meeting', meeting)"
          >
            <span class="tree-meeting__dot" aria-hidden="true" />
            <span class="tree-meeting__name">{{ meeting.title }}</span>
          </button>
        </li>
        <li v-if="category.meetings.length === 0" class="tree-children__empty">
          {{ searchActive ? '没有匹配的会议' : '该分类下还没有会议' }}
        </li>
      </ul>
    </div>

    <!-- 未分类 -->
    <div class="tree-branch">
      <div class="tree-row" :class="{ 'tree-row--active': selectedKey === 'cat:uncategorized' }">
        <button
          type="button"
          class="tree-row__chevron"
          :class="{ 'tree-row__chevron--open': isExpanded('uncategorized') }"
          :aria-expanded="isExpanded('uncategorized')"
          aria-label="展开「未分类」"
          @click="$emit('toggle', 'uncategorized')"
        >
          <NavIcon name="chevron" :size="13" />
        </button>
        <button
          type="button"
          class="tree-row__main"
          @click="$emit('select-category', null)"
        >
          <span class="tree-row__icon" aria-hidden="true"><NavIcon name="folder" :size="15" /></span>
          <span class="tree-row__name">未分类</span>
          <span class="tree-row__count">{{ uncategorized.length }}</span>
        </button>
      </div>
      <ul v-if="isExpanded('uncategorized')" class="tree-children">
        <li v-for="meeting in uncategorized" :key="meeting.meeting_id">
          <button
            type="button"
            class="tree-meeting"
            :class="{ 'tree-meeting--active': activeMeetingId === meeting.meeting_id }"
            @click="$emit('select-meeting', meeting)"
          >
            <span class="tree-meeting__dot" aria-hidden="true" />
            <span class="tree-meeting__name">{{ meeting.title }}</span>
          </button>
        </li>
        <li v-if="uncategorized.length === 0" class="tree-children__empty">
          {{ searchActive ? '没有匹配的会议' : '该分类下还没有会议' }}
        </li>
      </ul>
    </div>

    <!-- 新建分类 -->
    <div class="tree-create">
      <template v-if="creating">
        <input
          ref="createInput"
          v-model="createValue"
          class="tree-create__input"
          type="text"
          placeholder="输入分类名称，如：周会"
          maxlength="40"
          aria-label="新分类名称"
          @keyup.enter="submitCreate"
          @keyup.escape="cancelCreate"
        />
        <div class="tree-create__actions">
          <button
            type="button"
            class="tree-create__save"
            :disabled="!createValue.trim()"
            @click="submitCreate"
          >
            创建
          </button>
          <button type="button" class="tree-create__cancel" @click="cancelCreate">取消</button>
        </div>
      </template>
      <button v-else type="button" class="tree-create__toggle" @click="startCreate">
        ＋ 新建分类
      </button>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue'

import NavIcon from '@/components/NavIcon.vue'
import type { Meeting } from '@/types/meeting'

export interface TreeCategory {
  id: string
  name: string
  meetings: Meeting[]
}

const props = defineProps<{
  categories: TreeCategory[]
  uncategorized: Meeting[]
  totalCount: number
  /** 'all' | `cat:<分类id>` | 'cat:uncategorized' */
  selectedKey: string
  activeMeetingId: string | null
  expandedIds: string[]
  searchActive?: boolean
}>()

const emit = defineEmits<{
  'select-all': []
  'select-category': [id: string | null]
  'select-meeting': [meeting: Meeting]
  toggle: [id: string]
  rename: [id: string, name: string]
  remove: [category: { id: string; name: string }]
  create: [name: string]
}>()

const menuId = ref<string | null>(null)
const renamingId = ref<string | null>(null)
const renameValue = ref('')
const renameInput = ref<HTMLInputElement | null>(null)
const creating = ref(false)
const createValue = ref('')
const createInput = ref<HTMLInputElement | null>(null)

function isExpanded(id: string): boolean {
  return props.expandedIds.includes(id)
}

function toggleMenu(id: string): void {
  menuId.value = menuId.value === id ? null : id
}

function startRename(category: TreeCategory): void {
  renamingId.value = category.id
  renameValue.value = category.name
  menuId.value = null
  void nextTick(() => renameInput.value?.focus())
}

/** 函数 ref：静态 ref 位于 v-for 子树内会被收集为数组，这里归一为单元素 */
function setRenameInput(el: unknown): void {
  renameInput.value = (el as HTMLInputElement | null) ?? null
}

function commitRename(): void {
  const name = renameValue.value.trim()
  if (renamingId.value && name) {
    emit('rename', renamingId.value, name)
  }
  cancelRename()
}

function cancelRename(): void {
  renamingId.value = null
  renameValue.value = ''
}

function askRemove(category: TreeCategory): void {
  menuId.value = null
  emit('remove', { id: category.id, name: category.name })
}

function startCreate(): void {
  creating.value = true
  createValue.value = ''
  void nextTick(() => createInput.value?.focus())
}

function cancelCreate(): void {
  creating.value = false
  createValue.value = ''
}

function submitCreate(): void {
  const name = createValue.value.trim()
  if (!name) {
    return
  }
  emit('create', name)
  cancelCreate()
}

/** 点击树以外区域关闭更多菜单 */
function onDocClick(): void {
  menuId.value = null
}
document.addEventListener('click', onDocClick)
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<style scoped>
.category-tree {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tree-branch {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tree-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 2px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.tree-row:hover {
  background: var(--color-surface-muted);
}

.tree-row--active {
  background: var(--color-primary-soft);
}

.tree-row--active .tree-row__name {
  color: var(--color-primary-strong);
}

.tree-row__chevron {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.4rem;
  height: 1.4rem;
  padding: 0;
  color: var(--color-muted-foreground);
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.tree-row__chevron svg {
  transition: transform var(--transition-fast);
}

/* 收起指向右，展开指向下 */
.tree-row__chevron--open svg {
  transform: rotate(90deg);
}

.tree-row__chevron:hover {
  color: var(--color-foreground);
}

.tree-row__main {
  display: flex;
  flex: 1;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: 0.35rem 0.4rem;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.tree-row__icon {
  display: inline-flex;
  flex: 0 0 auto;
  color: var(--color-muted-foreground);
}

.tree-row--active .tree-row__icon {
  color: var(--color-primary-strong);
}

.tree-row__name {
  flex: 0 1 auto;
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-row__count {
  flex: 0 0 auto;
  min-width: 1.35rem;
  padding: 0 6px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-variant-numeric: tabular-nums;
  text-align: center;
  background: var(--color-surface-muted);
  border-radius: var(--radius-pill);
}

.tree-row--active .tree-row__count {
  color: var(--color-primary-strong);
  background: var(--color-surface);
}

.tree-row__more {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.5rem;
  height: 1.5rem;
  padding: 0;
  color: var(--color-muted-foreground);
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  /* 默认收起，hover 才显现 */
  opacity: 0;
  transition:
    opacity var(--transition-fast),
    color var(--transition-fast);
}

.tree-row:hover .tree-row__more,
.tree-row__more[aria-expanded='true'],
.tree-row__more:focus-visible {
  opacity: 1;
}

.tree-row__more:hover {
  color: var(--color-foreground);
}

.tree-row__menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 6px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  min-width: 7.5rem;
  padding: 4px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(15, 23, 42, 0.12));
}

.tree-row__menu-item {
  padding: 6px 10px;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.75rem;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.tree-row__menu-item:hover {
  background: var(--color-surface-muted);
}

.tree-row__menu-item--danger {
  color: var(--color-down);
}

/* 子节点：缩进 */
.tree-children {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin: 0;
  padding: 0 0 2px 1.75rem;
  list-style: none;
}

.tree-meeting {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  min-width: 0;
  padding: 0.3rem 0.4rem;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.75rem;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.tree-meeting:hover {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
}

.tree-meeting--active {
  color: var(--color-primary-strong);
  font-weight: 600;
  background: var(--color-primary-soft);
}

.tree-meeting__dot {
  flex: 0 0 auto;
  width: 5px;
  height: 5px;
  background: currentColor;
  border-radius: 50%;
  opacity: 0.5;
}

.tree-meeting__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-children__empty {
  padding: 0.25rem 0.4rem;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  opacity: 0.8;
}

/* 重命名 */
.tree-rename {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0.25rem 0.4rem 0.25rem 1.75rem;
}

.tree-rename__input {
  flex: 1;
  min-width: 0;
  min-height: 1.75rem;
  padding: 0 8px;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.75rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.tree-rename__input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.tree-rename__save {
  padding: 3px 10px;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: var(--color-primary-soft);
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.tree-rename__save:disabled {
  opacity: 0.5;
  cursor: default;
}

/* 新建分类 */
.tree-create {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--color-border);
}

.tree-create__toggle {
  align-self: flex-start;
  padding: 0.3rem 0.8rem;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  background: transparent;
  border: 1px dashed rgba(21, 94, 239, 0.4);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.tree-create__toggle:hover {
  background: var(--color-primary-soft);
}

.tree-create__input {
  min-height: 1.9rem;
  padding: 0 8px;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.75rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.tree-create__input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.tree-create__actions {
  display: flex;
  gap: var(--space-1);
}

.tree-create__save {
  padding: 3px 12px;
  color: #fff;
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: var(--color-primary);
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.tree-create__save:disabled {
  opacity: 0.5;
  cursor: default;
}

.tree-create__cancel {
  padding: 3px 10px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}
</style>
