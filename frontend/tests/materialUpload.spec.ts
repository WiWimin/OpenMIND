import { describe, expect, it } from 'vitest'

import { fileExtension, validateMaterialFile } from '@/utils/materialUpload'

function makeFile(name: string, size = 1024): File {
  const file = new File(['x'], name, { type: 'application/octet-stream' })
  Object.defineProperty(file, 'size', { value: size })
  return file
}

describe('materialUpload utils', () => {
  it('extracts a lowercase extension', () => {
    expect(fileExtension('方案.PDF')).toBe('pdf')
    expect(fileExtension('noext')).toBe('')
  })

  it('accepts whitelisted extensions within the size limit', () => {
    expect(validateMaterialFile(makeFile('a.pdf'))).toBeNull()
    expect(validateMaterialFile(makeFile('a.docx'))).toBeNull()
    expect(validateMaterialFile(makeFile('a.txt'))).toBeNull()
  })

  it('rejects unsupported extensions', () => {
    expect(validateMaterialFile(makeFile('a.exe'))).toContain('仅支持')
  })

  it('rejects files over the size limit', () => {
    expect(validateMaterialFile(makeFile('a.pdf', 21 * 1024 * 1024))).toContain('20 MB')
  })
})
