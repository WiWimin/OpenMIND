import { ref } from 'vue'

export type SettingsPanel = 'model' | 'memory' | 'knowledge'

/** 全局单例：设置弹窗的当前激活面板（null = 全部关闭） */
const activePanel = ref<SettingsPanel | null>(null)

export function useSettingsPanels() {
  function openPanel(panel: SettingsPanel): void {
    activePanel.value = panel
  }

  function closePanel(): void {
    activePanel.value = null
  }

  return { activePanel, openPanel, closePanel }
}
