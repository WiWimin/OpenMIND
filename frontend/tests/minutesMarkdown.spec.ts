/**
 * minutesMarkdown 单测：纪要 HTML ↔ Markdown 双向转换（本地工作区同步用）。
 */
import { describe, expect, it } from 'vitest'

import { htmlToMarkdown, markdownToHtml } from '@/utils/minutesMarkdown'

/** 往返辅助：Markdown → HTML → Markdown，用于断言二次转换稳定 */
function roundTrip(markdown: string): string {
  return htmlToMarkdown(markdownToHtml(markdown))
}

describe('minutesMarkdown', () => {
  it('converts headings, paragraphs, ordered and unordered lists', () => {
    const html =
      '<h1>标题</h1><h2>小节</h2><h3>细节</h3><p>段落一</p><p>段落二</p>' +
      '<ul><li>项目一</li><li>项目二</li></ul><ol><li>步骤一</li><li>步骤二</li></ol>'
    const expected = [
      '# 标题',
      '## 小节',
      '### 细节',
      '段落一',
      '段落二',
      '- 项目一\n- 项目二',
      '1. 步骤一\n2. 步骤二',
    ].join('\n\n')
    expect(htmlToMarkdown(html)).toBe(`${expected}\n`)
  })

  it('converts inline styles (bold, italic, strike, code, link)', () => {
    const html =
      '<p><strong>粗体</strong> <em>斜体</em> <del>删除</del> <code>code</code> ' +
      '<a href="https://example.com">链接</a></p>'
    expect(htmlToMarkdown(html)).toBe(
      '**粗体** *斜体* ~~删除~~ `code` [链接](https://example.com)\n',
    )
    expect(htmlToMarkdown('<p><b>粗</b> <i>斜</i></p>')).toBe('**粗** *斜*\n')
  })

  it('converts tables (inside md-table-wrap) to pipe tables with separator row', () => {
    const html =
      '<div class="md-table-wrap"><table><thead><tr><th>名称</th><th>数量</th></tr></thead>' +
      '<tbody><tr><td>苹果</td><td>3</td></tr><tr><td>香蕉</td><td>5</td></tr></tbody></table></div>'
    const expected = ['| 名称 | 数量 |', '| --- | --- |', '| 苹果 | 3 |', '| 香蕉 | 5 |'].join('\n')
    expect(htmlToMarkdown(html)).toBe(`${expected}\n`)
  })

  it('converts blockquotes and fenced code blocks', () => {
    const html =
      '<blockquote><p>引用内容</p></blockquote>' +
      '<pre><code class="language-python">print("hi")</code></pre>'
    expect(htmlToMarkdown(html)).toBe('> 引用内容\n\n```python\nprint("hi")\n```\n')
  })

  it('keeps <br> as line breaks and collapses consecutive blank lines', () => {
    expect(htmlToMarkdown('<p>第一行<br>第二行</p>')).toBe('第一行\n第二行\n')
    const md = htmlToMarkdown('<p>甲<br><br><br><br>乙</p><p></p><p>丙</p>')
    expect(md).toBe('甲\n\n乙\n\n丙\n')
    expect(md).not.toContain('\n\n\n')
  })

  it('keeps text of unknown tags without dropping characters', () => {
    expect(htmlToMarkdown('<p>前<unknown-tag>中<strong>重</strong></unknown-tag>后</p>')).toBe(
      '前中**重**后\n',
    )
    expect(htmlToMarkdown('<custom-block>块级文本</custom-block>')).toBe('块级文本\n')
    expect(htmlToMarkdown('<foo><p>甲</p>乙</foo>')).toBe('甲\n\n乙\n')
  })

  it('returns empty string for empty input and ends with a single newline', () => {
    expect(htmlToMarkdown('')).toBe('')
    expect(htmlToMarkdown('   ')).toBe('')
    expect(htmlToMarkdown('<p></p>')).toBe('')
    const md = htmlToMarkdown('<p>内容</p>')
    expect(md).toBe('内容\n')
    expect(md.endsWith('\n')).toBe(true)
    expect(md.endsWith('\n\n')).toBe(false)
  })

  it('round-trips through markdownToHtml with stable second conversion', () => {
    const html =
      '<h1>会议纪要</h1><p>主持人<strong>张三</strong></p>' +
      '<ul><li>要点一</li><li>要点<strong>二</strong></li></ul>'
    const markdown = htmlToMarkdown(html)
    expect(markdown).toBe('# 会议纪要\n\n主持人**张三**\n\n- 要点一\n- 要点**二**\n')
    expect(roundTrip(markdown)).toBe(markdown)
  })

  it('renders markdown back to HTML with the shared renderMarkdown wording', () => {
    expect(markdownToHtml('')).toBe('')
    expect(markdownToHtml('   ')).toBe('')
    expect(markdownToHtml('# 标题')).toBe('<h1>标题</h1>')
    expect(markdownToHtml('**粗体**')).toBe('<p><strong>粗体</strong></p>')
  })
})
