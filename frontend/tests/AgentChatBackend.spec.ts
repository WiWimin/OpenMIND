import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AgentChat from '@/components/AgentChat.vue'
import * as agentApi from '@/api/agent'
import type {
  AgentBackendMessage,
  AgentBackendSession,
  AgentPendingAction,
} from '@/types/agent'

vi.mock('@/api/agent', () => ({
  ensureSession: vi.fn(),
  listMessages: vi.fn(),
  listPendingActions: vi.fn(),
  deleteSession: vi.fn(),
  approvePendingAction: vi.fn(),
  rejectPendingAction: vi.fn(),
  streamAgentTurn: vi.fn(),
}))

const session: AgentBackendSession = {
  session_id: 'ags_1',
  user_id: 'usr_1',
  meeting_id: 'mtg_1',
  scene: 'minutes',
  title: null,
  status: 'active',
  created_at: '2026-11-11T10:00:00+08:00',
  updated_at: '2026-11-11T10:00:00+08:00',
}

const history: AgentBackendMessage[] = [
  {
    message_id: 'agm_1',
    session_id: 'ags_1',
    role: 'user',
    content: '帮我看看资料里有没有排期',
    status: 'completed',
    created_at: '2026-11-11T10:01:00+08:00',
  },
  {
    message_id: 'agm_2',
    session_id: 'ags_1',
    role: 'assistant',
    content: '会议资料中没有找到相关证据。',
    status: 'completed',
    created_at: '2026-11-11T10:02:00+08:00',
    meta: { pending_action_id: 'aga_1' },
  },
]

const pendingAction: AgentPendingAction = {
  action_id: 'aga_1',
  session_id: 'ags_1',
  run_id: 'agr_1',
  action_type: 'web_search',
  question: '会议资料中没有找到相关证据，是否联网检索后再回答？',
  payload: { question: '排期是什么' },
  status: 'pending',
  created_at: '2026-11-11T10:02:00+08:00',
}

function mountBackendChat() {
  return mount(AgentChat, {
    props: {
      agentName: '会后处理',
      backendSession: true,
      agentScene: 'minutes',
      meetingId: 'mtg_1',
      storageKey: 'minutes:mtg_1',
      onSend: vi.fn(),
    },
  })
}

describe('AgentChat 后端会话模式', () => {
  beforeEach(() => {
    // 各用例共用 storageKey，清掉上一个用例防抖落盘的会话缓存，避免回退读到残留
    window.localStorage.clear()
    vi.mocked(agentApi.ensureSession).mockReset()
    vi.mocked(agentApi.listMessages).mockReset()
    vi.mocked(agentApi.listPendingActions).mockReset()
    vi.mocked(agentApi.approvePendingAction).mockReset()
    vi.mocked(agentApi.rejectPendingAction).mockReset()
    vi.mocked(agentApi.deleteSession).mockReset()
    vi.mocked(agentApi.streamAgentTurn).mockReset()
  })

  it('恢复服务端历史并把确认门挂到对应消息', async () => {
    vi.mocked(agentApi.ensureSession).mockResolvedValue(session)
    vi.mocked(agentApi.listMessages).mockResolvedValue(history)
    vi.mocked(agentApi.listPendingActions).mockResolvedValue([pendingAction])

    const wrapper = mountBackendChat()
    await flushPromises()

    expect(agentApi.ensureSession).toHaveBeenCalledWith({
      scene: 'minutes',
      meeting_id: 'mtg_1',
    })
    expect(agentApi.listMessages).toHaveBeenCalledWith('ags_1')
    expect(wrapper.text()).toContain('帮我看看资料里有没有排期')
    expect(wrapper.text()).toContain('会议资料中没有找到相关证据。')
    // 确认门卡片与批准按钮
    expect(wrapper.find('.agent-pending').exists()).toBe(true)
    expect(wrapper.text()).toContain('需要你的确认')
    expect(wrapper.text()).toContain('联网检索')
  })

  it('批准确认门后追加工作流的新助手消息', async () => {
    vi.mocked(agentApi.ensureSession).mockResolvedValue(session)
    vi.mocked(agentApi.listMessages).mockResolvedValue(history)
    vi.mocked(agentApi.listPendingActions).mockResolvedValue([pendingAction])
    vi.mocked(agentApi.approvePendingAction).mockResolvedValue({
      session_id: 'ags_1',
      intent: {
        intent: 'web_search',
        confidence: 1,
        slots: {},
        needs_clarification: false,
        clarification_question: null,
        source: 'explicit',
      },
      assistant_message: {
        message_id: 'agm_3',
        session_id: 'ags_1',
        role: 'assistant',
        content: '联网检索后的回答。',
        status: 'completed',
        created_at: '2026-11-11T10:03:00+08:00',
      },
      accepted: false,
    })

    const wrapper = mountBackendChat()
    await flushPromises()

    const approve = wrapper
      .findAll('button')
      .find((button) => button.text().includes('联网检索'))
    await approve?.trigger('click')
    await flushPromises()

    expect(agentApi.approvePendingAction).toHaveBeenCalledWith('aga_1')
    expect(wrapper.text()).toContain('联网检索后的回答。')
    expect(wrapper.text()).toContain('已批准，正在继续执行。')
    expect(wrapper.emitted('agent-result')).toBeTruthy()
  })

  it('拒绝确认门后以取消文案收尾，不继续工作流', async () => {
    vi.mocked(agentApi.ensureSession).mockResolvedValue(session)
    vi.mocked(agentApi.listMessages).mockResolvedValue(history)
    vi.mocked(agentApi.listPendingActions).mockResolvedValue([pendingAction])
    vi.mocked(agentApi.rejectPendingAction).mockResolvedValue({
      session_id: 'ags_1',
      intent: {
        intent: 'web_search',
        confidence: 1,
        slots: {},
        needs_clarification: false,
        clarification_question: null,
        source: 'explicit',
      },
      assistant_message: {
        message_id: 'agm_4',
        session_id: 'ags_1',
        role: 'assistant',
        content: '已取消联网检索。',
        status: 'completed',
        created_at: '2026-11-11T10:04:00+08:00',
      },
      accepted: false,
    })

    const wrapper = mountBackendChat()
    await flushPromises()

    const reject = wrapper
      .findAll('button')
      .find((button) => button.text().includes('暂不处理'))
    await reject?.trigger('click')
    await flushPromises()

    expect(agentApi.rejectPendingAction).toHaveBeenCalledWith('aga_1')
    expect(agentApi.approvePendingAction).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('已取消联网检索。')
    expect(wrapper.text()).toContain('已取消该操作。')
  })

  it('后端不可用（404）时回退本地缓存且不报错', async () => {
    vi.mocked(agentApi.ensureSession).mockRejectedValue({
      status: 'error',
      error_code: 'RESOURCE_NOT_FOUND',
      message: '资源不存在',
      retryable: false,
    })

    const wrapper = mountBackendChat()
    await flushPromises()

    expect(wrapper.find('.agent-pending').exists()).toBe(false)
    // 回退后仍可正常输入
    expect(wrapper.find('#agent-chat-input').exists()).toBe(true)
  })
})
