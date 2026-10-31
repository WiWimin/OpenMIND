/**
 * 模型提供商预设（OpenAI 兼容协议）。
 *
 * 预设用于免填 API 地址，并提供常用模型清单供使用时的模型选择器展示。
 * 后端保存校验要求 api_base + api_key + model 三者齐全，因此用户只填
 * API Key 时，前端会自动采用该提供商的第一个推荐模型作为默认模型。
 */

export interface ModelProviderPreset {
  id: string
  name: string
  apiBase: string
  /** 常用模型清单（第一个为保存时的默认模型） */
  models: string[]
  /** 申请密钥的提示 */
  hint?: string
}

export const MODEL_PROVIDER_PRESETS: ModelProviderPreset[] = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    apiBase: 'https://api.deepseek.com/v1',
    models: ['deepseek-chat', 'deepseek-reasoner'],
    hint: 'platform.deepseek.com',
  },
  {
    id: 'zhipu',
    name: '智谱 GLM',
    apiBase: 'https://open.bigmodel.cn/api/paas/v4',
    models: ['glm-4.5', 'glm-4-plus', 'glm-4-flash'],
    hint: 'open.bigmodel.cn',
  },
  {
    id: 'moonshot',
    name: '月之暗面 Kimi',
    apiBase: 'https://api.moonshot.cn/v1',
    models: ['kimi-k2-0711-preview', 'moonshot-v1-8k', 'moonshot-v1-32k'],
    hint: 'platform.moonshot.cn',
  },
  {
    id: 'qwen',
    name: '阿里通义千问',
    apiBase: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    models: ['qwen-max', 'qwen-plus', 'qwen-turbo'],
    hint: 'dashscope 控制台申请 Key',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    apiBase: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
    hint: 'platform.openai.com',
  },
  {
    id: 'siliconflow',
    name: '硅基流动',
    apiBase: 'https://api.siliconflow.cn/v1',
    models: ['deepseek-ai/DeepSeek-V3', 'Qwen/Qwen2.5-72B-Instruct'],
    hint: 'cloud.siliconflow.cn',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    apiBase: 'https://openrouter.ai/api/v1',
    models: ['openai/gpt-4o', 'anthropic/claude-sonnet-4', 'google/gemini-2.0-flash-001'],
    hint: 'openrouter.ai',
  },
]

export const CUSTOM_PROVIDER_ID = 'custom'

/** 按已保存的 API 地址反查预设（匹配不到即为自定义/未知提供商） */
export function findPresetByApiBase(apiBase: string): ModelProviderPreset | null {
  const normalized = apiBase.trim().replace(/\/+$/, '').toLowerCase()
  if (!normalized) {
    return null
  }
  return (
    MODEL_PROVIDER_PRESETS.find(
      (preset) => preset.apiBase.replace(/\/+$/, '').toLowerCase() === normalized,
    ) ?? null
  )
}
