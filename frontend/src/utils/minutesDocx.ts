import { Document, HeadingLevel, Packer, Paragraph, TextRun } from 'docx'

function runsFromInline(node: Node, bold = false, italic = false): TextRun[] {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent ?? ''
    return text ? [new TextRun({ text, bold, italics: italic })] : []
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return []
  }
  const element = node as HTMLElement
  const tag = element.tagName.toLowerCase()
  const nextBold = bold || tag === 'strong' || tag === 'b'
  const nextItalic = italic || tag === 'em' || tag === 'i'
  const runs: TextRun[] = []
  for (const child of Array.from(element.childNodes)) {
    runs.push(...runsFromInline(child, nextBold, nextItalic))
  }
  return runs
}

function paragraphsFromElement(element: HTMLElement): Paragraph[] {
  const tag = element.tagName.toLowerCase()

  if (tag === 'h1') {
    return [new Paragraph({ heading: HeadingLevel.HEADING_1, children: runsFromInline(element) })]
  }
  if (tag === 'h2') {
    return [new Paragraph({ heading: HeadingLevel.HEADING_2, children: runsFromInline(element) })]
  }
  if (tag === 'h3') {
    return [new Paragraph({ heading: HeadingLevel.HEADING_3, children: runsFromInline(element) })]
  }
  if (tag === 'ul' || tag === 'ol') {
    const paragraphs: Paragraph[] = []
    for (const li of Array.from(element.querySelectorAll(':scope > li'))) {
      paragraphs.push(
        new Paragraph({
          bullet: tag === 'ul' ? { level: 0 } : undefined,
          numbering: tag === 'ol' ? { reference: 'minutes-numbered', level: 0 } : undefined,
          children: runsFromInline(li),
        }),
      )
    }
    return paragraphs
  }
  if (tag === 'br') {
    return [new Paragraph({ children: [] })]
  }

  return [new Paragraph({ children: runsFromInline(element) })]
}

export function htmlToParagraphs(html: string): Paragraph[] {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html || '<p></p>', 'text/html')
  const paragraphs: Paragraph[] = []
  for (const node of Array.from(doc.body.childNodes)) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      paragraphs.push(...paragraphsFromElement(node as HTMLElement))
    } else if (node.nodeType === Node.TEXT_NODE) {
      const text = (node.textContent ?? '').trim()
      if (text) {
        paragraphs.push(new Paragraph({ children: [new TextRun(text)] }))
      }
    }
  }
  return paragraphs.length > 0 ? paragraphs : [new Paragraph({ children: [new TextRun('')] })]
}

export async function buildMinutesDocxBlob(title: string, content: string): Promise<Blob> {
  const document = new Document({
    numbering: {
      config: [
        {
          reference: 'minutes-numbered',
          levels: [{ level: 0, format: 'decimal', text: '%1.', alignment: 'left' }],
        },
      ],
    },
    sections: [
      {
        children: [
          new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun(title)] }),
          ...htmlToParagraphs(content),
        ],
      },
    ],
  })
  return Packer.toBlob(document)
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
