import { ref, type Ref } from 'vue'

export type ToastTone = 'success' | 'error'

export interface Toast {
  id: number
  message: string
  tone: ToastTone
}

export interface ToastApi {
  toasts: Ref<Toast[]>
  success: (message: string) => void
  error: (message: string) => void
  dismiss: (id: number) => void
}

const DEFAULT_DURATION_MS = 3200

const toasts = ref<Toast[]>([])
let nextId = 1

function dismiss(id: number): void {
  toasts.value = toasts.value.filter((toast) => toast.id !== id)
}

function push(message: string, tone: ToastTone): void {
  const text = message.trim()
  if (!text) {
    return
  }
  const id = nextId
  nextId += 1
  toasts.value = [...toasts.value, { id, message: text, tone }]
  setTimeout(() => dismiss(id), DEFAULT_DURATION_MS)
}

const api: ToastApi = {
  toasts,
  success: (message: string) => push(message, 'success'),
  error: (message: string) => push(message, 'error'),
  dismiss,
}

export function useToast(): ToastApi {
  return api
}
