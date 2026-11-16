import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as memoryApi from '@/api/memory'
import * as templatesApi from '@/api/templates'
import TemplateManageView from '@/views/meetings/TemplateManageView.vue'
import { useToast } from '@/composables/useToast'
import type { MeetingTemplate } from '@/types/template'

const push = vi.fn()
const route = { query: {} as Record<string, string> }

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => route,
}))

vi.mock('@/api/templates', () => ({
  listTemplates: vi.fn(),
  getTemplate: vi.fn(),
  uploadTemplate: vi.fn(),
  createTemplateText: vi.fn(),
  deleteTemplate: vi.fn(),
}))

vi.mock('@/api/memory', () => ({
  getMemory: vi.fn(),
  saveMemory: vi.fn(),
}))

function builtinTemplate(overrides: Partial<MeetingTemplate> = {}): MeetingTemplate {
  return {
    template_id: 'tpl-builtin-minutes',
    name: '会议纪要',
    description: '标准纪要',
    category: '会后',
    source: 'builtin',
    file_name: null,
    created_at: null,
    content_preview: '1. 会议信息；2. 议题与讨论；3. 结论与决议',
    ...overrides,
  }
}

function customTemplate(overrides: Partial<MeetingTemplate> = {}): MeetingTemplate {
  return builtinTemplate({
    template_id: 'tpl_custom_1',
    name: '我的模板',
    category: '通用',
    source: 'custom',
    content_preview: '1. 自定义要点',
    ...overrides,
  })
}

async function mountView() {
  const wrapper = mount(TemplateManageView)
  await flushPromises()
  return wrapper
}

function cardNames(wrapper: Awaited<ReturnType<typeof mountView>>): string[] {
  return wrapper.findAll('.template-card__name').map((node) => node.text())
}

beforeEach(() => {
  vi.resetAllMocks()
  route.query = {}
  vi.mocked(templatesApi.listTemplates).mockResolvedValue([
    builtinTemplate(),
    builtinTemplate({
      template_id: 'tpl-builtin-pre-summary',
      name: '会前摘要',
      category: '会前',
      content_preview: '1. 会议目标；2. 材料要点',
    }),
    customTemplate(),
  ])
  vi.mocked(memoryApi.getMemory).mockResolvedValue({
    role: '',
    work_scenarios: '',
    communication_style: '',
    preferred_minutes_template: null,
    updated_at: null,
  })
})

describe('TemplateManageView', () => {
  it('renders the card grid with the upload and AI generate header actions', async () => {
    const wrapper = await mountView()

    expect(cardNames(wrapper)).toEqual(['会议纪要', '会前摘要', '我的模板'])
    // 元信息行展示来源：内置模板 / 我的模板
    const builtinCard = wrapper.findAll('.template-card')[0]
    expect(builtinCard.text()).toContain('内置模板')
    // 用户上传的模板显示「我的」
    const customCard = wrapper.findAll('.template-card')[2]
    expect(customCard.text()).toContain('我的')
    // 页头：上传 + AI 生成 + 创建模板三个入口
    expect(wrapper.text()).toContain('上传模板文件')
    expect(wrapper.text()).toContain('AI 生成模板')
    expect(wrapper.text()).toContain('创建模板')
    expect(wrapper.text()).toContain('会议模板中心')
    expect(wrapper.text()).not.toContain('返回会议管理')
  })

  it('filters templates by the search keyword and chips', async () => {
    const wrapper = await mountView()

    await wrapper.get('.template-manage__search-input').setValue('会前')
    expect(cardNames(wrapper)).toEqual(['会前摘要'])

    await wrapper.get('.template-manage__search-input').setValue('')
    const customChip = wrapper
      .findAll('.template-manage__filter')
      .find((node) => node.text() === '我的')
    await customChip?.trigger('click')
    expect(cardNames(wrapper)).toEqual(['我的模板'])
  })

  it('shows the default tag for the memory preferred template', async () => {
    vi.mocked(memoryApi.getMemory).mockResolvedValue({
      role: '',
      work_scenarios: '',
      communication_style: '',
      preferred_minutes_template: 'tpl-builtin-minutes',
      updated_at: null,
    })
    const wrapper = await mountView()

    const minutesCard = wrapper.findAll('.template-card')[0]
    expect(minutesCard.text()).toContain('默认')
  })

  it('opens the template content as a document preview', async () => {
    vi.mocked(templatesApi.getTemplate).mockResolvedValue({
      ...builtinTemplate(),
      content_text: '1. 会议信息\n2. 议题与讨论',
    })
    const wrapper = await mountView()

    const card = wrapper
      .findAll('.template-card')
      .find((node) => node.text().includes('会议纪要'))
    await card
      ?.findAll('.template-card__action')
      .find((node) => node.text() === '预览')
      ?.trigger('click')
    await flushPromises()

    // 文档式预览：标题为模板名，正文按 Markdown 渲染进纸张区
    expect(wrapper.get('.modal__title').text()).toBe('会议纪要')
    expect(wrapper.get('.tpl-doc__paper').text()).toContain('会议信息')
    expect(wrapper.find('.markdown-view').exists()).toBe(true)
  })

  it('returns to the originating ai input page when 使用 is clicked', async () => {
    route.query = { returnTo: 'minutes', meetingId: 'mtg_9' }
    const wrapper = await mountView()

    const useButton = wrapper
      .findAll('.template-card')
      .find((card) => card.text().includes('会议纪要'))
      ?.findAll('.template-card__use')
      .find((node) => node.text() === '使用模板')
    await useButton?.trigger('click')

    expect(push).toHaveBeenCalledWith({
      name: 'new-meeting-minutes',
      query: { meetingId: 'mtg_9', templateId: 'tpl-builtin-minutes' },
    })
  })

  it('duplicates a template via 另存为', async () => {
    vi.mocked(templatesApi.getTemplate).mockResolvedValue({
      ...builtinTemplate(),
      content_text: '1. 会议信息；2. 议题与讨论',
    })
    vi.mocked(templatesApi.createTemplateText).mockResolvedValue(customTemplate())
    const wrapper = await mountView()

    // 另存为收纳在卡片「更多」菜单中
    const card = wrapper
      .findAll('.template-card')
      .find((node) => node.text().includes('会议纪要'))
    await card
      ?.findAll('.template-card__action')
      .find((node) => node.text() === '更多')
      ?.trigger('click')
    const saveAs = card
      ?.findAll('.template-card__action')
      .find((node) => node.text() === '另存为')
    await saveAs?.trigger('click')
    await flushPromises()

    expect(templatesApi.createTemplateText).toHaveBeenCalledWith(
      expect.objectContaining({ name: '会议纪要 副本' }),
    )
  })

  it('sets a template as the memory default', async () => {
    vi.mocked(memoryApi.saveMemory).mockResolvedValue({
      role: '',
      work_scenarios: '',
      communication_style: '',
      preferred_minutes_template: 'tpl-builtin-minutes',
      updated_at: null,
    })
    const wrapper = await mountView()

    // 设为默认收纳在卡片「更多」菜单中
    const card = wrapper
      .findAll('.template-card')
      .find((node) => node.text().includes('会议纪要'))
    await card
      ?.findAll('.template-card__action')
      .find((node) => node.text() === '更多')
      ?.trigger('click')
    const setDefault = card
      ?.findAll('.template-card__action')
      .find((node) => node.text() === '设为默认')
    await setDefault?.trigger('click')
    await flushPromises()

    expect(memoryApi.saveMemory).toHaveBeenCalledWith(
      expect.objectContaining({ preferred_minutes_template: 'tpl-builtin-minutes' }),
    )
    expect(useToast().toasts.value.some((t) => t.message.includes('已设为默认模板'))).toBe(true)
  })

  it('uploads a template file directly from the side card', async () => {
    vi.mocked(templatesApi.uploadTemplate).mockResolvedValue(customTemplate())
    const wrapper = await mountView()

    const file = new File(['结构'], '模板.md', { type: 'text/markdown' })
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    await wrapper.get('input[type="file"]').trigger('change')
    await flushPromises()

    expect(templatesApi.uploadTemplate).toHaveBeenCalledTimes(1)
  })
})
