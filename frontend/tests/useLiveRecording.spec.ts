import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

import * as audioApi from '@/api/audio'
import { useLiveRecording } from '@/composables/useLiveRecording'
import type { AudioSegment, MeetingAudio } from '@/types/audio'

vi.mock('@/api/audio', () => ({
  startLiveAudio: vi.fn(),
  uploadLiveChunk: vi.fn(),
  finishLiveAudio: vi.fn(),
  retrySegment: vi.fn(),
}))

const startLiveAudio = vi.mocked(audioApi.startLiveAudio)
const uploadLiveChunk = vi.mocked(audioApi.uploadLiveChunk)
const finishLiveAudio = vi.mocked(audioApi.finishLiveAudio)
const retrySegmentApi = vi.mocked(audioApi.retrySegment)

class FakeMediaRecorder {
  static instances: FakeMediaRecorder[] = []

  static isTypeSupported(): boolean {
    return true
  }

  state = 'inactive'
  mimeType = 'audio/webm;codecs=opus'
  private listeners = new Map<string, Array<(event: unknown) => void>>()

  constructor() {
    FakeMediaRecorder.instances.push(this)
  }

  addEventListener(type: string, handler: (event: unknown) => void): void {
    const list = this.listeners.get(type) ?? []
    list.push(handler)
    this.listeners.set(type, list)
  }

  start(): void {
    this.state = 'recording'
  }

  stop(): void {
    if (this.state !== 'recording') {
      return
    }
    this.state = 'inactive'
    this.emit('dataavailable', { data: new Blob(['tail'], { type: 'audio/webm' }) })
    this.emit('stop', {})
  }

  emit(type: string, event: unknown): void {
    for (const handler of this.listeners.get(type) ?? []) {
      handler(event)
    }
  }
}

function liveAudio(
  status: MeetingAudio['status'],
  segments: MeetingAudio['segments'],
): MeetingAudio {
  return {
    audio_id: 'aud_1',
    meeting_id: 'mtg_1',
    file_name: '实时录音-20261101-090000.webm',
    type: 'webm',
    status,
    transcript: null,
    segments,
    error: null,
    record_id: null,
    created_at: '2026-11-01T09:00:00+08:00',
    updated_at: '2026-11-01T09:00:00+08:00',
  }
}

function segmentOf(seq: number, text: string): AudioSegment[] {
  return [{ seq, offset_seconds: (seq - 1) * 30, text, marker_type: null, error: null }]
}

function withSetup<T>(composable: () => T): { result: T; unmount: () => void } {
  let result!: T
  const wrapper = mount(
    defineComponent({
      setup() {
        result = composable()
        return () => h('div')
      },
    }),
  )
  return { result, unmount: () => wrapper.unmount() }
}

function currentRecorder(): FakeMediaRecorder {
  const recorder = FakeMediaRecorder.instances.at(-1)
  if (!recorder) {
    throw new Error('no recorder created')
  }
  return recorder
}

describe('useLiveRecording', () => {
  beforeEach(() => {
    FakeMediaRecorder.instances = []
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder)
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn(async () => ({ getTracks: () => [] })) },
    })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('uploads chunks in order and finishes the session', async () => {
    startLiveAudio.mockResolvedValue(liveAudio('processing', null))
    uploadLiveChunk.mockImplementation(async (_audioId, seq) =>
      liveAudio('processing', segmentOf(seq, `第${seq}段`)),
    )
    finishLiveAudio.mockResolvedValue(
      liveAudio(
        'transcribed',
        [1, 2, 3].flatMap((seq) => segmentOf(seq, `第${seq}段`)),
      ),
    )
    const finished: MeetingAudio[] = []
    const { result, unmount } = withSetup(() =>
      useLiveRecording({
        meetingId: () => 'mtg_1',
        onSessionFinished: (audio) => {
          finished.push(audio)
        },
      }),
    )

    await result.startRecording()
    expect(startLiveAudio).toHaveBeenCalledWith('mtg_1', 'webm')
    expect(result.recording.value).toBe(true)
    expect(result.liveAudioId.value).toBe('aud_1')

    currentRecorder().emit('dataavailable', {
      data: new Blob(['a'], { type: 'audio/webm' }),
    })
    currentRecorder().emit('dataavailable', {
      data: new Blob(['b'], { type: 'audio/webm' }),
    })

    const done = await result.stopRecording()

    // 两段手动分片 + 停止时的尾段，按 seq 串行上传
    expect(uploadLiveChunk).toHaveBeenCalledTimes(3)
    expect(uploadLiveChunk.mock.calls.map((call) => call[1])).toEqual([1, 2, 3])
    expect(result.liveSegments.value.map((segment) => segment.text)).toEqual([
      '第1段',
      '第2段',
      '第3段',
    ])
    expect(done?.status).toBe('transcribed')
    expect(finished).toHaveLength(1)
    expect(result.recording.value).toBe(false)
    unmount()
  })

  it('keeps a placeholder for failed chunks and continues the session', async () => {
    startLiveAudio.mockResolvedValue(liveAudio('processing', null))
    uploadLiveChunk.mockResolvedValue(liveAudio('processing', segmentOf(2, '第2段')))
    uploadLiveChunk.mockRejectedValueOnce(new Error('network'))
    finishLiveAudio.mockResolvedValue(
      liveAudio('transcribed', segmentOf(1, '')),
    )
    const errors: string[] = []
    const { result, unmount } = withSetup(() =>
      useLiveRecording({
        meetingId: () => 'mtg_1',
        onError: (message) => {
          errors.push(message)
        },
      }),
    )

    await result.startRecording()
    currentRecorder().emit('dataavailable', { data: new Blob(['x']) })
    await result.stopRecording()

    expect(result.liveSegments.value[0]?.error).toBeTruthy()
    expect(result.liveSegments.value[0]?.text).toBe('')
    expect(errors).toHaveLength(1)
    unmount()
  })

  it('retries a failed segment and updates it in place', async () => {
    startLiveAudio.mockResolvedValue(liveAudio('processing', null))
    uploadLiveChunk.mockResolvedValue(liveAudio('processing', segmentOf(2, '第2段')))
    uploadLiveChunk.mockRejectedValueOnce(new Error('network'))
    finishLiveAudio.mockResolvedValue(liveAudio('transcribed', segmentOf(1, '')))
    retrySegmentApi.mockResolvedValue(liveAudio('processing', segmentOf(1, '重试成功')))
    const { result, unmount } = withSetup(() =>
      useLiveRecording({ meetingId: () => 'mtg_1' }),
    )

    await result.startRecording()
    currentRecorder().emit('dataavailable', { data: new Blob(['x']) })
    await result.stopRecording()

    await result.retrySegment(1)

    expect(retrySegmentApi).toHaveBeenCalledWith('aud_1', 1)
    expect(result.liveSegments.value[0]?.text).toBe('重试成功')
    expect(result.liveSegments.value[0]?.error).toBeNull()
    unmount()
  })

  it('reports an error when the browser cannot record', async () => {
    vi.stubGlobal('MediaRecorder', undefined)
    const errors: string[] = []
    const { result, unmount } = withSetup(() =>
      useLiveRecording({
        meetingId: () => 'mtg_1',
        onError: (message) => {
          errors.push(message)
        },
      }),
    )

    await result.startRecording()

    expect(result.recording.value).toBe(false)
    expect(startLiveAudio).not.toHaveBeenCalled()
    expect(errors).toEqual(['当前浏览器不支持录音，请上传音频文件'])
    unmount()
  })
})
