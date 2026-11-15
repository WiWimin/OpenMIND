/**
 * 纪要 HTML 与 Markdown 双向转换（本地工作区同步用）。
 * - htmlToMarkdown：把纪要 HTML 导出为可编辑的 Markdown，供用户在本地 .md 文件中修改；
 * - markdownToHtml：把用户本地编辑的 Markdown 回写为纪要 HTML（复用 renderMarkdown 口径）。
 * 纯手写实现，不引入第三方 Markdown 依赖。
 */
import { renderMarkdown } from '@/utils/markdown'

/** 块级标签：转换时按独立块（段落/列表/表格等）处理 */
const BLOCK_TAGS = new Set([
  'address',
  'article',
  'aside',
  'blockquote',
  'dd',
  'details',
  'div',
  'dl',
  'dt',
  'fieldset',
  'figcaption',
  'figure',
  'footer',
  'form',
  'h1',
  'h2',
  'h3',
  'h4',
  'h5',
  'h6',
  'header',
  'hr',
  'li',
  'main',
  'nav',
  'ol',
  'p',
  'pre',
  'section',
  'summary',
  'table',
  'tbody',
  'td',
  'tfoot',
  'th',
  'thead',
  'tr',
  'ul',
])

/** 行内标签：转换时嵌入所在段落 */
const INLINE_TAGS = new Set([
  'a',
  'abbr',
  'b',
  'br',
  'cite',
  'code',
  'del',
  'em',
  'i',
  'img',
  'ins',
  'kbd',
  'mark',
  'q',
  's',
  'samp',
  'small',
  'span',
  'strike',
  'strong',
  'sub',
  'sup',
  'time',
  'u',
  'wbr',
])

function isElement(node: Node): node is HTMLElement {
  return node.nodeType === Node.ELEMENT_NODE
}

function tagOf(node: Node): string {
  return isElement(node) ? node.tagName.toLowerCase() : ''
}

function hasBlockDescendant(element: Element): boolean {
  for (const child of Array.from(element.children)) {
    if (BLOCK_TAGS.has(child.tagName.toLowerCase())) {
      return true
    }
    if (hasBlockDescendant(child)) {
      return true
    }
  }
  return false
}

function isBlockNode(node: Node): node is HTMLElement {
  if (!isElement(node)) {
    return false
  }
  const tag = node.tagName.toLowerCase()
  if (BLOCK_TAGS.has(tag)) {
    return true
  }
  if (INLINE_TAGS.has(tag)) {
    return false
  }
  // 未知标签：含块级后代按块处理，否则按行内处理（只透传文本，不丢字）
  return hasBlockDescendant(node)
}

/** 把行内内容包进成对标记（内容为空时不加标记） */
function wrapInline(marker: string, content: string): string {
  const leading = /^\s*/.exec(content)?.[0] ?? ''
  const trailing = /\s*$/.exec(content)?.[0] ?? ''
  const core = content.slice(leading.length, content.length - trailing.length)
  return core ? `${leading}${marker}${core}${marker}${trailing}` : content
}

/** 行内代码：内容含反引号时改用双反引号并补边界空格 */
function codeToMarkdown(content: string): string {
  const fence = content.includes('`') ? '``' : '`'
  const pad = content.startsWith('`') || content.endsWith('`') ? ' ' : ''
  return `${fence}${pad}${content}${pad}${fence}`
}

/** 行内节点转 Markdown；lineBreak 控制 <br> 的输出（表格单元格内用 <br>） */
function inlineToMarkdown(node: Node, lineBreak = '\n'): string {
  if (node.nodeType === Node.TEXT_NODE) {
    // HTML 文本中的换行等价于空格，段内换行只由 <br> 产生
    return (node.textContent ?? '').replace(/[\r\n]+/g, ' ')
  }
  if (!isElement(node)) {
    return ''
  }
  const tag = node.tagName.toLowerCase()
  const inner = Array.from(node.childNodes)
    .map((child) => inlineToMarkdown(child, lineBreak))
    .join('')
  switch (tag) {
    case 'strong':
    case 'b':
      return wrapInline('**', inner)
    case 'em':
    case 'i':
      return wrapInline('*', inner)
    case 'del':
    case 's':
    case 'strike':
      return wrapInline('~~', inner)
    case 'code':
      return codeToMarkdown((node.textContent ?? '').replace(/[\r\n]+/g, ' '))
    case 'a': {
      const href = node.getAttribute('href') ?? ''
      return href ? `[${inner || href}](${href})` : inner
    }
    case 'br':
      return lineBreak
    case 'img': {
      const alt = node.getAttribute('alt') ?? ''
      const src = node.getAttribute('src') ?? ''
      return src ? `![${alt}](${src})` : alt
    }
    default:
      // 未知行内标签：只透传内容，不加任何标记
      return inner
  }
}

/** 段落文本规整：连续空行压缩为一个空行并去掉首尾空白 */
function paragraphFromText(text: string): string {
  return text.replace(/\n{3,}/g, '\n\n').trim()
}

function headingToMarkdown(element: HTMLElement): string[] {
  const level = Number(tagOf(element).slice(1))
  const text = inlineToMarkdown(element).replace(/\n+/g, ' ').trim()
  return text ? [`${'#'.repeat(level)} ${text}`] : []
}

function listItemToMarkdown(item: HTMLElement, marker: string, indent: string): string[] {
  const nested: string[] = []
  let text = ''
  for (const child of Array.from(item.childNodes)) {
    if (
      isElement(child) &&
      (child.tagName.toLowerCase() === 'ul' || child.tagName.toLowerCase() === 'ol')
    ) {
      nested.push(...listToMarkdown(child, `${indent}  `))
      continue
    }
    text += inlineToMarkdown(child)
  }
  const content = text.replace(/\n+/g, ' ').trim()
  return [`${indent}${marker} ${content}`.trimEnd(), ...nested]
}

function listToMarkdown(list: HTMLElement, indent = ''): string[] {
  const ordered = tagOf(list) === 'ol'
  const lines: string[] = []
  let index = 0
  for (const item of Array.from(list.childNodes)) {
    if (!isElement(item) || item.tagName.toLowerCase() !== 'li') {
      continue
    }
    index += 1
    const marker = ordered ? `${index}.` : '-'
    lines.push(...listItemToMarkdown(item, marker, indent))
  }
  return lines
}

/** 围栏代码块：按内容中最长反引号串确定围栏长度，语言取 code.language-* */
function preToMarkdown(element: HTMLElement): string {
  const language =
    (element.querySelector('code')?.className ?? '').match(/language-([\w+-]+)/)?.[1] ?? ''
  const content = (element.textContent ?? '').replace(/\n$/, '')
  const runs = content.match(/`+/g) ?? []
  const fence = '`'.repeat(Math.max(3, ...runs.map((run) => run.length + 1)))
  return `${fence}${language}\n${content}\n${fence}`
}

function blockquoteToMarkdown(element: HTMLElement): string {
  const lines: string[] = []
  blocksFromChildren(element).forEach((block, index) => {
    if (index > 0) {
      lines.push('>')
    }
    for (const line of block.split('\n')) {
      lines.push(line ? `> ${line}` : '>')
    }
  })
  return lines.join('\n')
}

/** 表格单元格转行内文本（单元格内换行统一输出 <br>，避免破坏管道行） */
function tableCellToMarkdown(cell: HTMLElement): string {
  return blocksFromChildren(cell).join('<br>').replace(/\n/g, '<br>')
}

/** 表格转 GitHub 管道表格：表头行 + `| --- |` 分隔行 + 数据行 */
function tableToMarkdown(table: HTMLElement): string[] {
  const rows = Array.from(table.querySelectorAll('tr'))
  if (rows.length === 0) {
    return []
  }
  const headerRow =
    rows.find((row) => (row.parentElement?.tagName.toLowerCase() ?? '') === 'thead') ??
    (rows[0].cells.length > 0 &&
    Array.from(rows[0].cells).every((cell) => cell.tagName.toLowerCase() === 'th')
      ? rows[0]
      : undefined)
  const bodyRows = rows.filter((row) => row !== headerRow)
  const columnCount = rows.reduce((max, row) => Math.max(max, row.cells.length), 0)
  const line = (cells: string[]): string => {
    const padded = [...cells]
    while (padded.length < columnCount) {
      padded.push('')
    }
    return `| ${padded.join(' | ')} |`
  }
  const headerCells = headerRow
    ? Array.from(headerRow.cells).map((cell) => tableCellToMarkdown(cell))
    : Array.from({ length: columnCount }, () => '')
  return [
    line(headerCells),
    `| ${Array.from({ length: columnCount }, () => '---').join(' | ')} |`,
    ...bodyRows.map((row) => line(Array.from(row.cells).map((cell) => tableCellToMarkdown(cell)))),
  ]
}

/** 子节点按块/行内分组转换：块级之间用空行分隔，零散行内文本按段落处理 */
function blocksFromChildren(container: Node): string[] {
  const blocks: string[] = []
  let loose = ''
  const flush = (): void => {
    const text = paragraphFromText(loose)
    if (text) {
      blocks.push(text)
    }
    loose = ''
  }
  for (const child of Array.from(container.childNodes)) {
    if (isBlockNode(child)) {
      flush()
      blocks.push(...blockToMarkdown(child))
    } else {
      loose += inlineToMarkdown(child)
    }
  }
  flush()
  return blocks.filter((block) => block.trim().length > 0)
}

function blockToMarkdown(element: HTMLElement): string[] {
  const tag = tagOf(element)
  if (/^h[1-6]$/.test(tag)) {
    return headingToMarkdown(element)
  }
  if (tag === 'p') {
    const text = paragraphFromText(inlineToMarkdown(element))
    return text ? [text] : []
  }
  if (tag === 'ul' || tag === 'ol') {
    const lines = listToMarkdown(element)
    return lines.length > 0 ? [lines.join('\n')] : []
  }
  if (tag === 'pre') {
    return [preToMarkdown(element)]
  }
  if (tag === 'blockquote') {
    const quote = blockquoteToMarkdown(element)
    return quote ? [quote] : []
  }
  if (tag === 'table') {
    const lines = tableToMarkdown(element)
    return lines.length > 0 ? [lines.join('\n')] : []
  }
  if (tag === 'hr') {
    return ['---']
  }
  // 未知块级标签与 div.md-table-wrap 等容器：透传子块，内容不丢字
  return blocksFromChildren(element)
}

/**
 * 把纪要 HTML 转为 Markdown（用于导出到本地 .md 文件，供用户编辑）。
 * 连续空行压缩为一个空行；输出以单个换行结尾；空输入返回空字符串。
 */
export function htmlToMarkdown(html: string): string {
  if (!html.trim()) {
    return ''
  }
  const doc = new DOMParser().parseFromString(html, 'text/html')
  const text = blocksFromChildren(doc.body).join('\n\n')
  return text ? `${text.replace(/\n+$/, '')}\n` : ''
}

/**
 * 把用户本地编辑的 Markdown 转回 HTML（用于回写服务端纪要）。
 * 直接复用 renderMarkdown，保证与项目其他 Markdown 渲染口径一致；空输入返回空字符串。
 */
export function markdownToHtml(markdown: string): string {
  if (!markdown.trim()) {
    return ''
  }
  return renderMarkdown(markdown)
}
