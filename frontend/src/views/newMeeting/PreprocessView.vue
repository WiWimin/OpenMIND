<template>
  <StageShell stage="preprocess" title="资料预处理">

    <div class="preprocess">
      <aside class="preprocess__aside">
        <section class="aside-section">
          <h2 class="aside-section__title">上传资料</h2>
          <template v-if="meetingId">
            <MaterialUploader :uploading="uploading" @upload="upload" />
            <ErrorMessage v-if="uploadError" :error="uploadError" />
          </template>
        </section>

        <section class="aside-section">
          <h2 class="aside-section__title">会议资料</h2>
          <MaterialSection
            v-if="meetingId"
            :key="materialsKey"
            :meeting-id="meetingId"
            hide-uploader
          />
        </section>

        <section v-if="lastPreparation" class="aside-section aside-section--accent">
          <div class="aside-section__head">
            <div>
              <p class="aside-section__eyebrow">本轮产出</p>
              <h2 class="aside-section__title">会前准备稿</h2>
            </div>
            <StatusBadge
              :label="lastPreparation.status === 'confirmed' ? '已确认' : '草稿'"
              :tone="lastPreparation.status === 'confirmed' ? 'success' : 'info'"
            />
          </div>

          <div class="prep-summary">
            <p class="prep-summary__text">{{ excerpt(lastPreparation.summary) }}</p>
            <p class="prep-summary__meta">
              准备清单 {{ lastPreparation.checklist.length }} 项 · v{{ lastPreparation.version }}
            </p>
            <ul v-if="lastPreparation.checklist.length" class="prep-list">
              <li v-for="item in lastPreparation.checklist.slice(0, 4)" :key="item">
                {{ item }}
              </li>
            </ul>
          </div>

          <ErrorMessage v-if="actionError" :error="actionError" />

          <div class="aside-section__actions">
            <AppButton
              v-if="lastPreparation.status !== 'confirmed'"
              :loading="confirming"
              @click="savePreparation"
            >
              确认准备稿
            </AppButton>
          </div>
        </section>
      </aside>

      <div class="preprocess__chatwrap">
        <AgentChat
          ref="chatRef"
          class="preprocess__chat"
          agent-name="AI会议助手"
          :show-welcome="false"
          :on-send="handleSend"
          :disabled="!meetingId"
          placeholder="输入补充要求或调整议程…"
        >
          <template #composer-extra>
            <TemplatePickerPopover
              :disabled="!meetingId"
              :selected="selectedTemplateId"
              @select="onSelectTemplate"
            />
            <ModelPickerPopover
              :disabled="!meetingId"
              :selected="selectedModel"
              @select="onSelectModel"
            />
          </template>

          <template #composer-below>
            <button
              v-for="bubble in quickBubbles"
              :key="bubble.label"
              type="button"
              class="preprocess-bubble"
              :disabled="!meetingId"
              @click="applyPrompt(bubble.prompt)"
            >
              <span class="preprocess-bubble__icon" aria-hidden="true" v-html="bubble.icon" />
              {{ bubble.label }}
            </button>
          </template>
        </AgentChat>
      </div>
    </div>
  </StageShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import * as chatApi from '@/api/chat'
import * as materialsApi from '@/api/materials'
import * as preparationsApi from '@/api/preparations'
import AgentChat from '@/components/AgentChat.vue'
import AppButton from '@/components/AppButton.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import MaterialSection from '@/components/MaterialSection.vue'
import MaterialUploader from '@/components/MaterialUploader.vue'
import ModelPickerPopover from '@/components/ModelPickerPopover.vue'
import StageShell from '@/components/StageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TemplatePickerPopover from '@/components/TemplatePickerPopover.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import type { AgentReply } from '@/types/agent'
import type { ChatSource } from '@/types/chat'
import type { MaterialUploadPayload } from '@/types/material'
import type { Preparation } from '@/types/preparation'
import { resolveErrorMessage } from '@/utils/errors'

const route = useRoute()
const toast = useToast()
const { mirrorMeetingFile } = useLocalWorkspace()

const meetingId = computed(() => String(route.query.meetingId ?? ''))
const lastPreparation = ref<Preparation | null>(null)
const confirming = ref(false)
const actionError = ref<unknown>(null)

const chatRef = ref<InstanceType<typeof AgentChat> | null>(null)
const selectedModel = ref('')
const selectedTemplateId = ref('')

const uploading = ref(false)
const uploadError = ref<unknown>(null)
const materialsKey = ref(0)

interface QuickBubble {
  label: string
  prompt: string
  icon: string
}

const ICON_SUMMARY =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M5 5.5h14M5 10h14M5 14.5h9M5 19h6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
const ICON_AGENDA =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M5 5.5h14v15H5zM5 10h14M9 3v4M15 3v4M8.5 14h4M8.5 17h7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
const ICON_SPEECH =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M12 3.5a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0v-5a3 3 0 0 0-3-3ZM6.5 11.5v.5a5.5 5.5 0 0 0 11 0v-.5M12 17.5V21" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
const ICON_SEARCH =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M10.8 17.6a6.8 6.8 0 1 0 0-13.6 6.8 6.8 0 0 0 0 13.6ZM16 16l4 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
const ICON_RISK =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M12 3.8 21 19.5H3L12 3.8Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 9.5v4.2M12 16.6v.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
const ICON_CHECKLIST =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M4.5 4.5h15v15h-15zM8 12l2.2 2.2L16 8.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'

const quickBubbles: QuickBubble[] = [
  {
    label: '会议摘要',
    prompt: '请生成会前准备摘要与准备清单。',
    icon: ICON_SUMMARY,
  },
  {
    label: '会议议程',
    prompt: '请基于已上传资料，生成一份结构清晰的会议议程，包含时间分配与讨论重点。',
    icon: ICON_AGENDA,
  },
  {
    label: '发言稿',
    prompt: '请基于已上传资料，为本次会议写一段开场发言稿，语气自然、重点清晰。',
    icon: ICON_SPEECH,
  },
  {
    label: '检索资料',
    prompt: '请检索会议资料，总结其中的关键信息，并给出对应来源。',
    icon: ICON_SEARCH,
  },
  {
    label: '议题与风险',
    prompt: '请阅读已上传的会议资料，提炼本次会议的核心议题、风险点和待确认事项。',
    icon: ICON_RISK,
  },
  {
    label: '准备清单',
    prompt: '请梳理会前需要准备的材料、需要确认的信息和参会人需要提前了解的内容。',
    icon: ICON_CHECKLIST,
  },
]

const preparationIntent = /准备稿|准备清单|会前摘要|生成会前准备/

watch(meetingId, () => {
  lastPreparation.value = null
  actionError.value = null
  uploadError.value = null
})

function sourceLabel(source: ChatSource): string {
  if (source.document_name) {
    return source.document_name
  }
  if (source.material_id) {
    return '会议资料'
  }
  if (source.record_id) {
    return '会议记录'
  }
  if (source.meeting_id) {
    return '会议上下文'
  }
  return '来源'
}

function excerpt(text: string, limit = 220): string {
  const normalized = text.replace(/\s+/g, ' ').trim()
  return normalized.length > limit ? `${normalized.slice(0, limit)}…` : normalized
}

function applyPrompt(prompt: string): void {
  chatRef.value?.setDraft(prompt)
}

function onSelectModel(model: string): void {
  selectedModel.value = model
  toast.success(model ? `已选择模型：${model}` : '已恢复默认模型路由')
}

function onSelectTemplate(templateId: string): void {
  selectedTemplateId.value = templateId
  toast.success(templateId ? '已选择输出模板，生成准备稿时将套用' : '已恢复默认模板结构')
}

async function upload(payload: MaterialUploadPayload): Promise<void> {
  if (!meetingId.value) {
    return
  }
  uploading.value = true
  uploadError.value = null
  try {
    const material = await materialsApi.uploadMaterial(meetingId.value, payload)
    if (material.processing_status === 'failed') {
      uploadError.value = {
        status: 'error',
        error_code: 'FILE_PARSE_FAILED',
        message: material.parse_error ?? '文件解析失败',
        retryable: false,
      }
      return
    }
    toast.success('资料已上传')
    materialsKey.value += 1
    void mirrorMeetingFile({
      meetingId: meetingId.value,
      kind: 'materials',
      fileName: payload.file.name,
      content: payload.file,
    })
  } catch (caught) {
    uploadError.value = caught
  } finally {
    uploading.value = false
  }
}

async function handleSend(text: string, signal: AbortSignal): Promise<AgentReply> {
  if (!meetingId.value) {
    throw new Error('请先选择一场会议。')
  }

  const model = selectedModel.value || undefined
  const templateId = selectedTemplateId.value || undefined

  try {
    if (preparationIntent.test(text)) {
      const preparation = await preparationsApi.generatePreparation(
        meetingId.value,
        {
          include_history: true,
          user_goal: text,
          model,
          template_id: templateId,
        },
        signal,
      )
      lastPreparation.value = preparation
      const checklist = preparation.checklist.length
        ? preparation.checklist.map((item) => `- ${item}`).join('\n')
        : '- 暂无准备清单'
      return {
        content: `## 会前摘要\n\n${preparation.summary}\n\n## 准备清单\n\n${checklist}\n\n> 已生成会前准备草稿，可在左侧确认并保存。`,
        note:
          preparation.status === 'confirmed'
            ? '准备稿已确认。'
            : '草稿已生成，确认后会作为会中与纪要阶段的上下文。',
      }
    }

    const result = await chatApi.askMeeting(
      meetingId.value,
      {
        question: text,
        context_scope: 'current_meeting',
        include_sources: true,
        model,
      },
      signal,
    )

    return {
      content: result.answer,
      sources: result.sources.slice(0, 3).map((source) => ({
        label: sourceLabel(source),
        detail: excerpt(source.excerpt, 64),
      })),
      note: result.insufficient_evidence ? '证据不足，回答仅供参考。' : undefined,
    }
  } catch (caught) {
    throw new Error(resolveErrorMessage(caught, 'Agent 处理失败，请稍后重试。'))
  }
}

async function savePreparation(): Promise<void> {
  if (!lastPreparation.value) {
    return
  }
  confirming.value = true
  actionError.value = null
  try {
    lastPreparation.value = await preparationsApi.confirmPreparation(
      lastPreparation.value.preparation_id,
    )
    toast.success('会前准备稿已确认')
  } catch (caught) {
    actionError.value = caught
  } finally {
    confirming.value = false
  }
}
</script>

<style scoped>
.preprocess {
  display: grid;
  grid-template-columns: 22rem minmax(0, 1fr);
  gap: var(--space-4);
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

.preprocess__aside {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  order: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.preprocess__chatwrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  order: 2;
  min-width: 0;
  min-height: 0;
}

.preprocess__chat {
  flex: 1;
  min-height: 0;
}

/* 左栏内区块：去独立卡片外壳，用分隔线分隔 */
.aside-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.aside-section + .aside-section {
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.aside-section__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.aside-section__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
}

.aside-section__eyebrow {
  margin: 0;
  color: var(--color-accent-strong);
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.aside-section--accent {
  padding: var(--space-3);
  background: linear-gradient(180deg, rgba(230, 247, 244, 0.65), #ffffff 55%);
  border: 1px solid rgba(13, 148, 136, 0.22);
  border-radius: var(--radius-md);
}

.aside-section--accent + .aside-section {
  border-top: 0;
  padding-top: 0;
}

.aside-section__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.prep-summary {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.prep-summary__text {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  line-height: 1.7;
}

.prep-summary__meta {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.prep-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding-left: 1.1rem;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.prep-list li::marker {
  color: var(--color-accent);
}

/* 输入框下方的气泡快捷按钮 */
.preprocess-bubble {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.35rem 0.8rem;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 550;
  white-space: nowrap;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    border-color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.preprocess-bubble:hover:not(:disabled) {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.26);
}

.preprocess-bubble:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.preprocess-bubble__icon {
  display: inline-flex;
  color: var(--color-subtle-foreground);
}

.preprocess-bubble:hover:not(:disabled) .preprocess-bubble__icon {
  color: var(--color-primary);
}

@media (max-width: 1180px) {
  .preprocess {
    grid-template-columns: minmax(0, 1fr);
    height: auto;
  }

  .preprocess__chatwrap {
    order: 1;
  }

  .preprocess__aside {
    order: 2;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
    align-items: start;
    overflow: visible;
  }

  .preprocess__chat {
    min-height: 28rem;
  }
}
</style>
