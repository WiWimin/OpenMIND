/**
 * 前端特性开关（与后端 `AGENT_ENABLED` 对齐）。
 *
 * 默认开启：后端未启用时 `/agent/*` 返回 404，AgentChat 会自动回退
 * localStorage 缓存与页面既有发送链路，因此无需前后端同时关闭。
 */
export const agentEnabled =
  (import.meta.env.VITE_AGENT_ENABLED ?? 'true').toString() !== 'false'
