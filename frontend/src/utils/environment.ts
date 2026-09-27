const ENVIRONMENT_LABELS: Record<string, string> = {
  development: '开发环境',
  production: '生产环境',
}

export function resolveEnvironmentLabel(value: string): string {
  return ENVIRONMENT_LABELS[value] ?? value
}
