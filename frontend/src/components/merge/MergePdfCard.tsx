import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ChevronLeft, ChevronRight, GripVertical, X } from 'lucide-react'
import { formatBytes } from '../../format'
import type { MergeFile } from '../../types'
import { PdfThumbnail } from './PdfThumbnail'

export function MergePdfCard({ entry, position, total, onRemove, onMove, onPageCount }: {
  entry: MergeFile
  position: number
  total: number
  onRemove: (id: string) => void
  onMove: (id: string, dir: -1 | 1) => void
  onPageCount: (id: string, count: number) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: entry.id })
  const style = { transform: CSS.Transform.toString(transform), transition }
  const name = entry.file.name

  return <li
    ref={setNodeRef}
    style={style}
    className={`merge-card${isDragging ? ' dragging' : ''}`}
  >
    <div className="merge-card-thumb">
      <PdfThumbnail file={entry.file} onPageCount={count => onPageCount(entry.id, count)} />
      <span className="merge-card-position" aria-hidden="true">{position}</span>
      <button type="button" className="merge-card-remove" onClick={() => onRemove(entry.id)} aria-label={`${name} entfernen`}>
        <X size={15} />
      </button>
    </div>
    <div className="merge-card-info">
      <div className="merge-card-name" title={name}>{name}</div>
      <div className="merge-card-meta">{entry.pageCount != null ? `${entry.pageCount} Seiten · ` : ''}{formatBytes(entry.file.size)}</div>
    </div>
    <div className="merge-card-footer">
      <button
        type="button"
        className="merge-card-handle"
        {...attributes}
        {...listeners}
        aria-label={`${name} verschieben, aktuell Position ${position} von ${total}. Pfeiltasten zum Verschieben verwenden.`}
      >
        <GripVertical size={16} />
      </button>
      <div className="merge-card-order-buttons">
        <button type="button" onClick={() => onMove(entry.id, -1)} disabled={position === 1} aria-label={`${name} nach vorne verschieben`}>
          <ChevronLeft size={15} />
        </button>
        <button type="button" onClick={() => onMove(entry.id, 1)} disabled={position === total} aria-label={`${name} nach hinten verschieben`}>
          <ChevronRight size={15} />
        </button>
      </div>
    </div>
  </li>
}
