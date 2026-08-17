import { describe, expect, it } from 'vitest'
import { isPdfFile, makeId, moveByOffset, reorderById } from './reorder'
import type { MergeFile } from '../../types'

function pdf(name: string): MergeFile {
  return { id: name, file: new File(['%PDF-1.4'], name, { type: 'application/pdf' }) }
}

describe('makeId', () => {
  it('returns unique ids', () => {
    const ids = new Set(Array.from({ length: 50 }, () => makeId()))
    expect(ids.size).toBe(50)
  })
})

describe('isPdfFile', () => {
  it('accepts application/pdf mime type', () => {
    expect(isPdfFile(new File(['x'], 'a.dat', { type: 'application/pdf' }))).toBe(true)
  })
  it('accepts .pdf extension even without mime type', () => {
    expect(isPdfFile(new File(['x'], 'a.PDF', { type: '' }))).toBe(true)
  })
  it('rejects other files', () => {
    expect(isPdfFile(new File(['x'], 'a.txt', { type: 'text/plain' }))).toBe(false)
  })
})

describe('reorderById', () => {
  it('moves an item to the dropped position', () => {
    const files = [pdf('a'), pdf('b'), pdf('c')]
    const result = reorderById(files, 'a', 'c')
    expect(result.map(f => f.id)).toEqual(['b', 'c', 'a'])
  })
  it('is a no-op when dropped on itself', () => {
    const files = [pdf('a'), pdf('b')]
    expect(reorderById(files, 'a', 'a')).toBe(files)
  })
  it('is a no-op for unknown ids', () => {
    const files = [pdf('a'), pdf('b')]
    expect(reorderById(files, 'a', 'missing')).toBe(files)
  })
})

describe('moveByOffset', () => {
  it('moves an item one position forward', () => {
    const files = [pdf('a'), pdf('b'), pdf('c')]
    expect(moveByOffset(files, 'a', 1).map(f => f.id)).toEqual(['b', 'a', 'c'])
  })
  it('moves an item one position backward', () => {
    const files = [pdf('a'), pdf('b'), pdf('c')]
    expect(moveByOffset(files, 'c', -1).map(f => f.id)).toEqual(['a', 'c', 'b'])
  })
  it('does not move past the boundaries', () => {
    const files = [pdf('a'), pdf('b')]
    expect(moveByOffset(files, 'a', -1)).toBe(files)
    expect(moveByOffset(files, 'b', 1)).toBe(files)
  })
})
