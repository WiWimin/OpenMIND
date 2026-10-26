// 长耗时请求的超时上限：AI 生成、音频转写、解析/向量化上传。
// 后端 LLM 单次调用超时为 60s 且可能重试，前端需要留出足够余量。
export const LONG_REQUEST_TIMEOUT_MS = 240_000
