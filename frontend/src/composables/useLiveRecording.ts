import { computed, onBeforeUnmount, ref } from 'vue'

import * as audioApi from '@/api/audio'
import type { AudioSegment, MeetingAudio } from '@/types/audio'
import { resolveErrorMessage } from '@/utils/errors'

/** 分片时长：每 30 秒产生一段完整可解码的音频并上传转写 */
const CHUNK_MS = 30_000
const RECORDER_MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']

interface UseLiveRecordingOptions {
  /** 当前会议 ID（惰性求值） */
  meetingId: () => string
  /** 实时会话已创建（返回 processing 状态的音频记录） */
  onSessionStarted?: (audio: MeetingAudio) => void
  /** 某个分片转写完成（成功或失败均回调） */
  onSegment?: (segment: AudioSegment) => void
  /** 会话已结束并落定状态 */
  onSessionFinished?: (audio: MeetingAudio) => void
  /** 非致命错误提示（单片失败等） */
  onError?: (message: string) => void
}

function extensionOfRecorder(mime: string): string {
  if (mime.includes('webm')) {
    return 'webm'
  }
  if (mime.includes('mp4')) {
    return 'm4a'
  }
  if (mime.includes('mpeg') || mime.includes('mp3')) {
    return 'mp3'
  }
  if (mime.includes('wav')) {
    return 'wav'
  }
  return 'webm'
}

/**
 * 分片边录边转：
 * 周期性 stop/start MediaRecorder，每段都是完整可解码的 webm；
 * dataavailable 产生的分片按序串行上传，转写结果实时追加到 liveSegments。
 */
export function useLiveRecording(options: UseLiveRecordingOptions) {
  const recording = ref(false)
  const startingRecorder = ref(false)
  const stoppingRecorder = ref(false)
  const recordingSeconds = ref(0)
  const liveSegments = ref<AudioSegment[]>([])
  const liveAudioId = ref('')

  const recordingLabel = computed(() => {
    const minutes = Math.floor(recordingSeconds.value / 60)
    const seconds = recordingSeconds.value % 60
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  })

  let recorder: MediaRecorder | null = null
  let stream: MediaStream | null = null
  let elapsedTimer: ReturnType<typeof setInterval> | null = null
  let chunkTimer: ReturnType<typeof setTimeout> | null = null
  let mimeType = 'audio/webm'
  let chunkSeq = 0
  let chunkStartSeconds = 0
  let stopRequested = false
  // 串行上传链，保证分片按 seq 顺序到达后端
  let uploadChain: Promise<void> = Promise.resolve()

  function beforeUnloadGuard(event: BeforeUnloadEvent): void {
    if (recording.value) {
      event.preventDefault()
    }
  }

  function insertSegment(segment: AudioSegment): void {
    const rest = liveSegments.value.filter((item) => item.seq !== segment.seq)
    liveSegments.value = [...rest, segment].sort((a, b) => a.seq - b.seq)
    options.onSegment?.(segment)
  }

  async function uploadChunk(
    audioId: string,
    seq: number,
    offsetSeconds: number,
    blob: Blob,
  ): Promise<void> {
    try {
      const updated = await audioApi.uploadLiveChunk(
        audioId,
        seq,
        offsetSeconds,
        blob,
        extensionOfRecorder(mimeType),
      )
      const segment = (updated.segments ?? []).find((item) => item.seq === seq)
      if (segment) {
        insertSegment(segment)
      }
    } catch {
      insertSegment({
        seq,
        offset_seconds: offsetSeconds,
        text: '',
        marker_type: null,
        error: '分片上传或转写失败',
      })
      options.onError?.(`第 ${seq} 段转写失败，已标记占位，可稍后重试本段`)
    }
  }

  function scheduleNextChunk(): void {
    if (chunkTimer) {
      clearTimeout(chunkTimer)
    }
    chunkTimer = setTimeout(() => {
      chunkTimer = null
      if (!stopRequested && recorder && recorder.state === 'recording') {
        recorder.stop()
      }
    }, CHUNK_MS)
  }

  function handleDataAvailable(event: BlobEvent): void {
    if (!event.data || event.data.size === 0 || !liveAudioId.value) {
      return
    }
    const seq = chunkSeq + 1
    chunkSeq = seq
    const offset = chunkStartSeconds
    const audioId = liveAudioId.value
    const blob = event.data
    uploadChain = uploadChain.then(() => uploadChunk(audioId, seq, offset, blob))
  }

  function handleRecorderStop(): void {
    if (stopRequested || !recorder) {
      return
    }
    // 开启下一个分片周期
    chunkStartSeconds = recordingSeconds.value
    try {
      recorder.start()
      scheduleNextChunk()
    } catch {
      /* 录音器已失效时忽略，等待用户停止 */
    }
  }

  function teardown(): void {
    if (elapsedTimer) {
      clearInterval(elapsedTimer)
      elapsedTimer = null
    }
    if (chunkTimer) {
      clearTimeout(chunkTimer)
      chunkTimer = null
    }
    stream?.getTracks().forEach((track) => track.stop())
    stream = null
    recorder = null
    recording.value = false
    window.removeEventListener('beforeunload', beforeUnloadGuard)
  }

  async function startRecording(): Promise<void> {
    if (recording.value || startingRecorder.value) {
      return
    }
    if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices) {
      options.onError?.('当前浏览器不支持录音，请上传音频文件')
      return
    }
    startingRecorder.value = true
    try {
      const audio = await audioApi.startLiveAudio(
        options.meetingId(),
        extensionOfRecorder(
          RECORDER_MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ??
            'audio/webm',
        ),
      )
      liveAudioId.value = audio.audio_id
      liveSegments.value = []
      chunkSeq = 0
      stopRequested = false
      recordingSeconds.value = 0
      chunkStartSeconds = 0

      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      mimeType =
        RECORDER_MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type)) ??
        'audio/webm'
      recorder = new MediaRecorder(stream, { mimeType })
      recorder.addEventListener('dataavailable', handleDataAvailable)
      recorder.addEventListener('stop', handleRecorderStop)
      recorder.start()
      scheduleNextChunk()

      elapsedTimer = setInterval(() => {
        recordingSeconds.value += 1
      }, 1000)
      recording.value = true
      window.addEventListener('beforeunload', beforeUnloadGuard)
      options.onSessionStarted?.(audio)
    } catch (caught) {
      teardown()
      liveAudioId.value = ''
      if (caught instanceof DOMException && caught.name === 'NotAllowedError') {
        options.onError?.('无法访问麦克风，请检查浏览器权限设置')
      } else {
        // 透出后端真实错误（如数据库迁移缺失、服务异常），避免被兜底文案掩盖
        options.onError?.(resolveErrorMessage(caught, '启动实时录音失败，请稍后重试'))
      }
    } finally {
      startingRecorder.value = false
    }
  }

  async function stopRecording(): Promise<MeetingAudio | null> {
    const current = recorder
    if (!current || stoppingRecorder.value) {
      return null
    }
    stopRequested = true
    stoppingRecorder.value = true
    if (chunkTimer) {
      clearTimeout(chunkTimer)
      chunkTimer = null
    }
    // dataavailable 为异步派发：必须先等最后一片数据落地并进入 uploadChain，
    // 否则 finish 会先于末片到达后端（409 冲突）导致尾部分片丢失。
    const willProduceData = current.state === 'recording'
    let guard: ReturnType<typeof setTimeout> | undefined
    const finalDataLanded = willProduceData
      ? Promise.race([
          new Promise<void>((resolve) => {
            current.addEventListener('dataavailable', () => resolve(), { once: true })
          }),
          new Promise<void>((resolve) => {
            guard = setTimeout(resolve, 5000)
          }),
        ])
      : Promise.resolve()
    if (willProduceData) {
      current.stop()
    }
    await finalDataLanded
    if (guard) {
      clearTimeout(guard)
    }
    try {
      await uploadChain
    } catch {
      /* 单片错误已在链内处理 */
    }
    teardown()
    try {
      const finished = await audioApi.finishLiveAudio(liveAudioId.value)
      options.onSessionFinished?.(finished)
      return finished
    } catch (caught) {
      options.onError?.(
        resolveErrorMessage(caught, '结束转写会话失败，请稍后在音频列表中重试或删除该音频'),
      )
      return null
    } finally {
      stoppingRecorder.value = false
    }
  }

  /** 实时会话中重试某个失败分片 */
  async function retrySegment(seq: number): Promise<void> {
    if (!liveAudioId.value) {
      return
    }
    try {
      const updated = await audioApi.retrySegment(liveAudioId.value, seq)
      const segment = (updated.segments ?? []).find((item) => item.seq === seq)
      if (segment) {
        insertSegment(segment)
      }
    } catch {
      options.onError?.(`第 ${seq} 段重试失败，请稍后再试`)
    }
  }

  onBeforeUnmount(() => {
    if (recording.value) {
      stopRequested = true
      recorder?.stop()
      void uploadChain
      teardown()
    }
  })

  return {
    recording,
    startingRecorder,
    stoppingRecorder,
    recordingSeconds,
    recordingLabel,
    liveSegments,
    liveAudioId,
    startRecording,
    stopRecording,
    retrySegment,
  }
}
