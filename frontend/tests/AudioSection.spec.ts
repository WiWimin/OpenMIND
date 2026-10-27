import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as audioApi from '@/api/audio'
import AudioSection from '@/components/AudioSection.vue'
import type { ListData } from '@/types/api'
import type { MeetingAudio } from '@/types/audio'

vi.mock('@/api/audio', () => ({
  listAudio: vi.fn(),
  uploadAudio: vi.fn(),
  updateTranscript: vi.fn(),
  retryAudio: vi.fn(),
  confirmAudio: vi.fn(),
  deleteAudio: vi.fn(),
  getAudio: vi.fn(),
}))

const audio: MeetingAudio = {
  audio_id: 'aud_1',
  meeting_id: 'mtg_1',
  file_name: 'meeting.mp3',
  type: 'mp3',
  status: 'transcribed',
  transcript: '原始转写文本',
  error: null,
  record_id: null,
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
}

function listOf(items: MeetingAudio[]): ListData<MeetingAudio> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountSection(readonly = false): VueWrapper {
  return mount(AudioSection, {
    props: { meetingId: 'mtg_1', readonly },
  })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text().includes(text))
}

async function selectAudioFile(wrapper: VueWrapper, file: File): Promise<void> {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
}

describe('AudioSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders the list and selects the first audio', async () => {
    vi.mocked(audioApi.listAudio).mockResolvedValue(listOf([audio]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('meeting.mp3')
    expect((wrapper.get('#audio-transcript').element as HTMLTextAreaElement).value).toBe(
      '原始转写文本',
    )
  })

  it('uploads an audio file and refreshes', async () => {
    vi.mocked(audioApi.listAudio)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([audio]))
    vi.mocked(audioApi.uploadAudio).mockResolvedValue(audio)
    const wrapper = mountSection()
    await flushPromises()
    const file = new File(['audio'], 'meeting.mp3', { type: 'audio/mpeg' })

    await selectAudioFile(wrapper, file)
    await button(wrapper, '上传并转写')?.trigger('click')
    await flushPromises()

    expect(audioApi.uploadAudio).toHaveBeenCalledWith('mtg_1', file)
    expect(audioApi.listAudio).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('meeting.mp3')
  })

  it('saves edited transcript', async () => {
    vi.mocked(audioApi.listAudio).mockResolvedValue(listOf([audio]))
    vi.mocked(audioApi.updateTranscript).mockResolvedValue({
      ...audio,
      transcript: '修订后的文本',
    })
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('#audio-transcript').setValue('修订后的文本')
    await button(wrapper, '保存修订')?.trigger('click')
    await flushPromises()

    expect(audioApi.updateTranscript).toHaveBeenCalledWith('aud_1', '修订后的文本')
  })

  it('confirms audio and emits saved', async () => {
    vi.mocked(audioApi.listAudio).mockResolvedValue(listOf([audio]))
    vi.mocked(audioApi.confirmAudio).mockResolvedValue({
      ...audio,
      status: 'confirmed',
      record_id: 'rec_1',
    })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '确认并保存为记录')?.trigger('click')
    await flushPromises()

    expect(audioApi.confirmAudio).toHaveBeenCalledWith('aud_1')
    expect(wrapper.emitted('saved')).toHaveLength(1)
    expect(wrapper.text()).toContain('rec_1')
  })

  it('hides mutation controls when readonly', async () => {
    vi.mocked(audioApi.listAudio).mockResolvedValue(listOf([audio]))
    const wrapper = mountSection(true)
    await flushPromises()

    expect(wrapper.find('input[type="file"]').exists()).toBe(false)
    expect(button(wrapper, '保存修订')).toBeUndefined()
    expect(button(wrapper, '确认并保存为记录')).toBeUndefined()
  })
})
