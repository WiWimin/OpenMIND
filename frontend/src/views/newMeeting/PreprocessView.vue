<template>
  <StageShell stage="preprocess" title="资料预处理">

    <div class="preprocess">
      <aside class="preprocess__aside">
        <section class="aside-section">
          <h2 class="aside-section__title">上传资料</h2>
          <template v-if="meetingId">
            <MaterialUploader :uploading="uploading" :error="uploadError" @upload="upload" />
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
              :label="preparationStatusMeta[lastPreparation.status]?.label ?? lastPreparation.status"
              :tone="preparationStatusMeta[lastPreparation.status]?.tone ?? 'neutral'"
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
          v-model:thinking="thinking"
          class="preprocess__chat"
          agent-name="杂乱文档，先规整再入库"
          mascot-size="8rem"
          :meeting-id="meetingId"
          :storage-key="meetingId ? `preprocess:${meetingId}` : ''"
          :show-welcome="false"
          :on-send="handleSend"
          :on-send-stream="handleSend"
          :backend-session="agentEnabled && !!meetingId"
          agent-scene="preprocess"
          :agent-options="agentOptions"
          :disabled="!meetingId"
          placeholder="输入补充要求或调整议程…"
          @agent-result="onAgentResult"
        >
          <!-- 输入框内：模式 / 模型 / 模板选择 -->
          <template #composer-extra>
            <ModePicker v-model="chatMode" :disabled="!meetingId" />
            <ModelPickerPopover
              :disabled="!meetingId"
              :selected="selectedModel"
              @select="onSelectModel"
              @manage="openPanel('model')"
            />
            <TemplatePickerPopover
              :disabled="!meetingId"
              :selected="selectedTemplateId"
              :meeting-id="meetingId"
              return-to="preprocess"
            />
          </template>

          <template #composer-below>
            <button
              v-for="bubble in quickBubbles"
              :key="bubble.key"
              type="button"
              class="preprocess-bubble"
              :title="bubble.rationale"
              :disabled="!meetingId"
              @click="applyBubble(bubble)"
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
import ModePicker from '@/components/ModePicker.vue'
import ModelPickerPopover from '@/components/ModelPickerPopover.vue'
import StageShell from '@/components/StageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TemplatePickerPopover from '@/components/TemplatePickerPopover.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useSettingsPanels } from '@/composables/useSettingsPanels'
import { useToast } from '@/composables/useToast'
import { agentEnabled } from '@/config/flags'
import { PREPROCESS_QUICK_ACTIONS, type QuickActionSpec } from '@/config/quickActions'
import type { AgentReply, AgentResultEvent, AgentSource, AgentStreamHandlers, AgentTurnOptions } from '@/types/agent'
import type { ChatMode, ChatPayload, ChatResult, ChatSource } from '@/types/chat'
import type { MaterialUploadError, MaterialUploadPayload } from '@/types/material'
import type { Preparation } from '@/types/preparation'
import { preparationStatusMeta } from '@/utils/statusLabels'
import { resolveErrorMessage, resolveUploadError } from '@/utils/errors'

const route = useRoute()
const toast = useToast()
const { openPanel } = useSettingsPanels()
const { mirrorMeetingFile } = useLocalWorkspace()

const meetingId = computed(() => String(route.query.meetingId ?? ''))
const lastPreparation = ref<Preparation | null>(null)
const confirming = ref(false)
const actionError = ref<unknown>(null)

const chatRef = ref<InstanceType<typeof AgentChat> | null>(null)
const selectedModel = ref('')
const selectedTemplateId = ref('')

// 支持「模板管理页 → 使用」跳转时通过路由参数预选模板
const routeTemplateId = String(route.query.templateId ?? '')
if (routeTemplateId) {
  selectedTemplateId.value = routeTemplateId
}
const chatMode = ref<ChatMode>('plan')
/** 思考过程（推理链）开关：默认开启，可按次关闭（关闭后不请求思考模式） */
const thinking = ref(true)

/** 后端 Agent 单轮执行选项：页面选择随消息透传，后端按意图消费 */
const agentOptions = computed<AgentTurnOptions>(() => ({
  model: selectedModel.value || undefined,
  template_id: selectedTemplateId.value || undefined,
  mode: chatMode.value,
  context_scope: 'current_meeting',
  include_sources: true,
  // 会前速览/清单只读本场资料，不读取用户历史会议资料
  include_history: false,
  include_materials: true,
}))

const uploading = ref(false)
const uploadError = ref<MaterialUploadError | null>(null)
const materialsKey = ref(0)

const quickBubbles: QuickActionSpec[] = PREPROCESS_QUICK_ACTIONS

watch(meetingId, () => {
  lastPreparation.value = null
  actionError.value = null
  uploadError.value = null
})

function sourceLabel(source: ChatSource): string {
  if (source.origin === 'web') {
    return source.title ? `联网 · ${source.title}` : '联网检索'
  }
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

function applyBubble(bubble: QuickActionSpec): void {
  // 挂载注册表动作：发送时透传 intent/mode/task，由后端按通道执行
  chatRef.value?.setPendingQuickAction({
    label: bubble.label,
    prompt: bubble.prompt,
    intent: bubble.intent,
    mode: bubble.mode,
    task: bubble.task,
    quickTask: bubble.quickTask,
  })
}

function onSelectModel(model: string): void {
  selectedModel.value = model
  toast.success(model ? `已选择模型：${model}` : '已恢复默认模型路由')
}

async function upload(payload: MaterialUploadPayload): Promise<void> {
  if (!meetingId.value) {
    return
  }
  uploading.value = true
  uploadError.value = null
  try {
    await materialsApi.uploadMaterial(meetingId.value, payload)
    toast.success('资料已上传并解析')
    materialsKey.value += 1
    void mirrorMeetingFile({
      meetingId: meetingId.value,
      fileName: payload.file.name,
      content: payload.file,
    })
  } catch (caught) {
    // 解析失败（422 FILE_PARSE_FAILED）与其他失败都显示在上传框内，可直接重试
    uploadError.value = resolveUploadError(caught, '上传失败，请检查文件后重试。')
  } finally {
    uploading.value = false
  }
}

function mapSources(sources: ChatSource[]): AgentSource[] {
  return sources.slice(0, 3).map((source) => ({
    label: sourceLabel(source),
    detail: excerpt(source.excerpt, 64),
  }))
}

function buildAskReply(result: ChatResult): AgentReply {
  return {
    content: result.answer,
    file: result.file ?? undefined,
    sources: mapSources(result.sources),
    reasoning: result.reasoning,
    note:
      result.insufficient_evidence && !result.sources.some((s) => s.origin === 'web')
        ? '证据不足，回答仅供参考。'
        : undefined,
  }
}

async function handleSend(
  text: string,
  signal: AbortSignal,
  stream?: AgentStreamHandlers,
): Promise<AgentReply> {
  if (!meetingId.value) {
    throw new Error('请先选择一场会议。')
  }

  const model = selectedModel.value || undefined

  try {
    const payload: ChatPayload = {
      question: text,
      context_scope: 'current_meeting',
      include_sources: true,
      model,
      mode: chatMode.value,
      thinking: thinking.value,
    }
    // Build 模式走同步（流式端点仅支持 plan，api.md 5.7a）；否则走 SSE 增量
    if (!stream || chatMode.value === 'build') {
      return buildAskReply(await chatApi.askMeeting(meetingId.value, payload, signal))
    }
    const result = await chatApi.askMeetingStream(
      meetingId.value,
      payload,
      {
        onMeta: (meta) => stream.onMeta?.(mapSources(meta.sources), meta.trace),
        onDelta: stream.onDelta,
        onReasoning: stream.onReasoning,
      },
      signal,
    )
    return buildAskReply(result)
  } catch (caught) {
    throw new Error(resolveErrorMessage(caught, 'Agent 处理失败，请稍后重试。'))
  }
}

/** 后端 Agent 业务结果：会前准备草稿就地刷新左侧确认卡 */
function onAgentResult(event: AgentResultEvent): void {
  if (event.intent.intent !== 'prepare' || !event.result) {
    return
  }
  lastPreparation.value = event.result as Preparation
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
