import { describe, expect, it } from 'vitest'

import { buildMinutesDocxBlob, htmlToParagraphs } from '@/utils/minutesDocx'

describe('minutesDocx', () => {
  it('converts plain paragraphs', () => {
    const paragraphs = htmlToParagraphs('<p>第一段</p><p>第二段</p>')
    expect(paragraphs).toHaveLength(2)
  })

  it('converts headings and lists', () => {
    const paragraphs = htmlToParagraphs(
      '<h1>标题</h1><h2>小节</h2><ul><li>要点一</li></ul><ol><li>步骤一</li></ol>',
    )
    expect(paragraphs.length).toBeGreaterThanOrEqual(4)
  })

  it('handles empty content without throwing', () => {
    const paragraphs = htmlToParagraphs('')
    expect(paragraphs).toHaveLength(1)
  })

  it('builds a docx blob', async () => {
    const blob = await buildMinutesDocxBlob('会议纪要', '<p>内容</p><ul><li>要点</li></ul>')
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.size).toBeGreaterThan(0)
  })
})
