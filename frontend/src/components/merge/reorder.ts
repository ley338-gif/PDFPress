import { arrayMove } from '@dnd-kit/sortable'
import type { MergeFile } from '../../types'

export function makeId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

export function isPdfFile(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

export function reorderById(files: MergeFile[], activeId: string, overId: string): MergeFile[] {
  if (activeId === overId) return files
  const oldIndex = files.findIndex(f => f.id === activeId)
  const newIndex = files.findIndex(f => f.id === overId)
  if (oldIndex === -1 || newIndex === -1) return files
  return arrayMove(files, oldIndex, newIndex)
}

export function moveByOffset(files: MergeFile[], id: string, dir: -1 | 1): MergeFile[] {
  const index = files.findIndex(f => f.id === id)
  if (index === -1) return files
  const target = index + dir
  if (target < 0 || target >= files.length) return files
  return arrayMove(files, index, target)
}
