import { describe, expect, it } from 'vitest'

import { renderMarkdown } from '@/utils/markdown'

describe('renderMarkdown', () => {
  it('renders headings, emphasis and lists', () => {
    const html = renderMarkdown('## 会议议题\n\n- **议题一**\n- 议题二\n\n1. 第一步\n2. 第二步')

    expect(html).toContain('<h2>会议议题</h2>')
    expect(html).toContain('<strong>议题一</strong>')
    expect(html).toContain('<ul>')
    expect(html).toContain('<ol>')
  })

  it('escapes raw html from model output', () => {
    const html = renderMarkdown('<script>alert(1)</script>')

    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })

  it('renders code fences and inline code safely', () => {
    const html = renderMarkdown('```ts\nconst a = 1 < 2\n```\n\n使用 `npm run dev` 启动')

    expect(html).toContain('<pre class="md-pre"><code class="language-ts">')
    expect(html).toContain('const a = 1 &lt; 2')
    expect(html).toContain('<code>npm run dev</code>')
  })

  it('renders tables and only allows http links', () => {
    const html = renderMarkdown(
      '| 字段 | 值 |\n| --- | --- |\n| 状态 | 已完成 |\n\n[文档](https://example.com) [危险](javascript:alert(1))',
    )

    expect(html).toContain('<table class="md-table">')
    expect(html).toContain('<a href="https://example.com"')
    expect(html).not.toContain('href="javascript:')
  })
})
