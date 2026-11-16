import { describe, expect, it } from 'vitest'

import {
  ASR_QUICK_ACTIONS,
  MINUTES_QUICK_ACTIONS,
  PREPROCESS_QUICK_ACTIONS,
  type QuickActionGrounding,
  type QuickActionOutputKind,
  type QuickActionSpec,
} from '@/config/quickActions'
import type { AgentIntentName } from '@/types/agent'

const INTENTS: AgentIntentName[] = [
  'chat',
  'brief',
  'prepare',
  'organize',
  'minutes_generate',
  'action_items_extract',
  'issues_extract',
  'knowledge_search',
  'build_file',
  'web_search',
  'transcribe',
  'clarify',
  'help',
]

const OUTPUT_KINDS: QuickActionOutputKind[] = [
  'text',
  'brief_card',
  'summary_card',
  'polish_diff',
  'minutes',
  'checklist',
  'file',
]

const GROUNDINGS: QuickActionGrounding[] = [
  'materials_only',
  'materials_then_web',
  'web_first',
]

const ALL: QuickActionSpec[] = [
  ...PREPROCESS_QUICK_ACTIONS,
  ...ASR_QUICK_ACTIONS,
  ...MINUTES_QUICK_ACTIONS,
]

describe('quick action registry', () => {
  it('keeps keys unique across scenes', () => {
    const keys = ALL.map((action) => action.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('declares a valid execution contract for every action', () => {
    for (const action of ALL) {
      expect(action.label.trim()).not.toBe('')
      expect(INTENTS).toContain(action.intent)
      expect(OUTPUT_KINDS).toContain(action.outputKind)
      expect(GROUNDINGS).toContain(action.grounding)
      expect(action.mode).toBe('plan')
      expect(action.rationale.trim()).not.toBe('')
      expect(action.sourceUrls.length).toBeGreaterThan(0)
      expect(action.lastReviewed).toMatch(/^\d{4}-\d{2}$/)
    }
  })

  it('uses the brief intent for the pre-meeting overview', () => {
    const brief = PREPROCESS_QUICK_ACTIONS.find((action) => action.key === 'preprocess.brief')
    expect(brief).toBeDefined()
    expect(brief?.intent).toBe('brief')
    expect(brief?.outputKind).toBe('brief_card')
    expect(brief?.grounding).toBe('materials_only')
  })

  it('does not let the checklist duplicate the overview', () => {
    const checklist = PREPROCESS_QUICK_ACTIONS.find(
      (action) => action.key === 'preprocess.checklist',
    )
    expect(checklist?.intent).toBe('prepare')
    expect(checklist?.outputKind).toBe('checklist')
  })

  it('only sends simple text actions through prompt_task', () => {
    const quickTasks = ALL.filter((action) => action.quickTask)
    expect(quickTasks.map((action) => action.key)).toEqual(['asr.condense'])
    expect(quickTasks[0].grounding).toBe('materials_only')
  })
})
