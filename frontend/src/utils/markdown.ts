const ESCAPE_MAP: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}

function escapeHtml(input: string): string {
  return input.replace(/[&<>"']/g, (char) => ESCAPE_MAP[char] ?? char)
}

function renderInline(raw: string): string {
  let text = escapeHtml(raw)
  const codeSpans: string[] = []

  text = text.replace(/`([^`]+)`/g, (_match, code: string) => {
    const index = codeSpans.push(`<code>${code}</code>`) - 1
    return `\uE000CODE${index}\uE001`
  })

  text = text.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_match, label: string, href: string) =>
      `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`,
  )
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  text = text.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  text = text.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>')

  return text.replace(
    /\uE000CODE(\d+)\uE001/g,
    (_match, index: string) => codeSpans[Number(index)] ?? '',
  )
}

function splitTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  return trimmed.split('|').map((cell) => cell.trim())
}

function isTableSeparator(line: string): boolean {
  return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(line)
}

function renderTable(rows: string[]): string {
  if (rows.length < 2) {
    return rows.map((row) => `<p>${renderInline(row)}</p>`).join('')
  }
  const head = splitTableRow(rows[0])
  const body = rows.slice(2).map(splitTableRow)
  const headHtml = head.map((cell) => `<th>${renderInline(cell)}</th>`).join('')
  const bodyHtml = body
    .map(
      (cells) =>
        `<tr>${head
          .map((_cell, index) => `<td>${renderInline(cells[index] ?? '')}</td>`)
          .join('')}</tr>`,
    )
    .join('')
  return `<div class="md-table-wrap"><table class="md-table"><thead><tr>${headHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`
}

function renderList(lines: string[], ordered: boolean): string {
  const items = lines.map((line) => {
    const text = line.replace(/^\s*(?:[-*+]|\d+[.)])\s+/, '')
    return `<li>${renderInline(text)}</li>`
  })
  const tag = ordered ? 'ol' : 'ul'
  return `<${tag}>${items.join('')}</${tag}>`
}

export function renderMarkdown(source: string): string {
  if (!source.trim()) {
    return ''
  }

  const lines = source.replace(/\r\n?/g, '\n').split('\n')
  const blocks: string[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]

    if (!line.trim()) {
      index += 1
      continue
    }

    const fence = line.match(/^\s*```([\w-]*)\s*$/)
    if (fence) {
      const language = fence[1] ?? ''
      const code: string[] = []
      index += 1
      while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
        code.push(lines[index])
        index += 1
      }
      index += 1
      const languageClass = language ? ` class="language-${escapeHtml(language)}"` : ''
      blocks.push(
        `<pre class="md-pre"><code${languageClass}>${escapeHtml(code.join('\n'))}</code></pre>`,
      )
      continue
    }

    const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/)
    if (heading) {
      const level = heading[1].length
      blocks.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      index += 1
      continue
    }

    if (/^\s*(?:---+|\*\*\*+|___+)\s*$/.test(line)) {
      blocks.push('<hr />')
      index += 1
      continue
    }

    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = []
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ''))
        index += 1
      }
      blocks.push(`<blockquote>${quote.map(renderInline).join('<br />')}</blockquote>`)
      continue
    }

    if (line.includes('|') && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const rows: string[] = []
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(lines[index])
        index += 1
      }
      blocks.push(renderTable(rows))
      continue
    }

    if (/^\s*(?:[-*+]|\d+[.)])\s+/.test(line)) {
      const ordered = /^\s*\d+[.)]\s+/.test(line)
      const items: string[] = []
      while (index < lines.length && /^\s*(?:[-*+]|\d+[.)])\s+/.test(lines[index])) {
        items.push(lines[index])
        index += 1
      }
      blocks.push(renderList(items, ordered))
      continue
    }

    const paragraph: string[] = []
    while (index < lines.length && lines[index].trim()) {
      const current = lines[index]
      if (
        /^\s*(?:```|#{1,6}\s|>|[-*+]\s|\d+[.)]\s)/.test(current) ||
        /^\s*(?:---+|\*\*\*+|___+)\s*$/.test(current)
      ) {
        break
      }
      paragraph.push(current)
      index += 1
    }
    if (paragraph.length) {
      blocks.push(`<p>${paragraph.map(renderInline).join('<br />')}</p>`)
    }
  }

  return blocks.join('\n')
}
