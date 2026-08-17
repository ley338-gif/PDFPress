import { useEffect, useRef, useState } from 'react'
import { DndContext, DragOverlay, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core'
import type { DragEndEvent, DragStartEvent } from '@dnd-kit/core'
import { SortableContext, rectSortingStrategy, sortableKeyboardCoordinates } from '@dnd-kit/sortable'
import { Check, Combine, Download, GripVertical, Plus } from 'lucide-react'
import { formatBytes } from '../../format'
import { mergePdfs } from '../../api'
import type { MergeFile } from '../../types'
import { MergePdfCard } from './MergePdfCard'
import { isPdfFile, makeId, moveByOffset, reorderById } from './reorder'

export function MergePage() {
  const [mergeFiles, setMergeFiles] = useState<MergeFile[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<{ url: string; name: string } | null>(null)
  const [drag, setDrag] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  useEffect(() => () => { if (result) URL.revokeObjectURL(result.url) }, [result])

  function addFiles(list?: FileList | File[] | null) {
    if (!list) return
    const picked = Array.from(list)
    if (!picked.length) return
    const nonPdf = picked.find(f => !isPdfFile(f))
    if (nonPdf) { setError(`"${nonPdf.name}" ist keine PDF-Datei.`); return }
    setError(null); setResult(null)
    setMergeFiles(prev => [...prev, ...picked.map(file => ({ id: makeId(), file }))])
  }

  function removeFile(id: string) {
    setMergeFiles(prev => prev.filter(f => f.id !== id))
  }

  function moveFile(id: string, dir: -1 | 1) {
    setMergeFiles(prev => moveByOffset(prev, id, dir))
  }

  function handlePageCount(id: string, count: number) {
    setMergeFiles(prev => prev.map(f => f.id === id ? { ...f, pageCount: count } : f))
  }

  function handleDragStart(event: DragStartEvent) {
    setActiveId(String(event.active.id))
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null)
    const { active, over } = event
    if (!over) return
    setMergeFiles(prev => reorderById(prev, String(active.id), String(over.id)))
  }

  async function merge() {
    if (mergeFiles.length < 2) { setError('Bitte mindestens zwei PDF-Dateien auswählen.'); return }
    setError(null); setBusy(true)
    try {
      const blob = await mergePdfs(mergeFiles.map(f => f.file))
      setResult({ url: URL.createObjectURL(blob), name: 'zusammengefuehrt.pdf' })
    } catch (e) { setError((e as Error).message) }
    finally { setBusy(false) }
  }

  function startOver() {
    setMergeFiles([]); setResult(null); setError(null)
  }

  const activeEntry = mergeFiles.find(f => f.id === activeId)
  const knownPages = mergeFiles.every(f => f.pageCount != null)
  const totalPages = mergeFiles.reduce((sum, f) => sum + (f.pageCount ?? 0), 0)
  const totalSize = mergeFiles.reduce((sum, f) => sum + f.file.size, 0)

  if (mergeFiles.length === 0) {
    return <>
      <div
        className={`dropzone ${drag ? 'dragging' : ''}`}
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={e => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files) }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click() }}
      >
        <div className="upload-icon"><Combine size={32} /></div>
        <h2>PDFs zusammenführen</h2>
        <p>Dateien hier ablegen oder mehrere PDF-Dateien auswählen</p>
        <button className="primary" onClick={e => { e.stopPropagation(); inputRef.current?.click() }}>PDFs auswählen</button>
        <input ref={inputRef} hidden type="file" accept="application/pdf,.pdf" multiple onChange={e => { addFiles(e.target.files); e.target.value = '' }} />
      </div>
      {error && <div className="error-banner">{error}</div>}
    </>
  }

  return <div className="merge-workspace">
    <p className="merge-hint">Ziehe die PDFs in die gewünschte Reihenfolge.</p>

    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd} onDragCancel={() => setActiveId(null)}>
      <SortableContext items={mergeFiles.map(f => f.id)} strategy={rectSortingStrategy}>
        <ul className="merge-grid">
          {mergeFiles.map((entry, i) => <MergePdfCard
            key={entry.id}
            entry={entry}
            position={i + 1}
            total={mergeFiles.length}
            onRemove={removeFile}
            onMove={moveFile}
            onPageCount={handlePageCount}
          />)}
        </ul>
      </SortableContext>
      <DragOverlay>
        {activeEntry && <div className="merge-card-overlay"><GripVertical size={16} /><span>{activeEntry.file.name}</span></div>}
      </DragOverlay>
    </DndContext>

    <label className="merge-add-more" onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files) }} data-dragging={drag || undefined}>
      <Plus size={16} /> Weitere PDFs hinzufügen
      <input hidden type="file" accept="application/pdf,.pdf" multiple onChange={e => { addFiles(e.target.files); e.target.value = '' }} />
    </label>

    <div className="merge-summary" data-testid="merge-summary">
      {mergeFiles.length} PDF{mergeFiles.length === 1 ? '' : 's'}{knownPages && totalPages > 0 ? ` · ${totalPages} Seiten` : ''} · {formatBytes(totalSize)}
    </div>

    {error && <div className="error-banner">{error}</div>}

    {!result ? (
      <button className="primary" disabled={busy || mergeFiles.length < 2} onClick={merge}>
        {busy ? 'Wird zusammengeführt…' : `${mergeFiles.length} PDFs zusammenführen`}
      </button>
    ) : (
      <div className="merge-result">
        <div className="merge-result-status"><Check size={18} /> PDF erfolgreich zusammengeführt</div>
        <a className="primary" href={result.url} download={result.name}><Download size={18} /> Herunterladen</a>
        <button className="secondary" onClick={startOver}>Neue PDFs zusammenführen</button>
      </div>
    )}
  </div>
}
