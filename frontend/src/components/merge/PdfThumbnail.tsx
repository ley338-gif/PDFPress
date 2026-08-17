import { useEffect, useRef, useState } from 'react'
import { Document, Page } from 'react-pdf'
import { FileWarning } from 'lucide-react'

// Small width keeps pdf.js from rendering the page at high resolution — this is
// only a list thumbnail, not a reading view.
const THUMBNAIL_WIDTH = 160

export function PdfThumbnail({ file, onPageCount }: { file: File; onPageCount?: (count: number) => void }) {
  const [failed, setFailed] = useState(false)
  const [visible, setVisible] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    const observer = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { setVisible(true); observer.disconnect() }
    }, { rootMargin: '200px' })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  if (failed) return <div className="pdf-thumbnail pdf-thumbnail-fallback" ref={rootRef}>
    <FileWarning size={22} />
    <span>Vorschau nicht möglich</span>
  </div>

  return <div className="pdf-thumbnail" ref={rootRef}>
    {visible
      ? <Document file={file} loading={<div className="pdf-thumbnail-loading" />} error={<div className="pdf-thumbnail-loading" />} onLoadSuccess={doc => onPageCount?.(doc.numPages)} onLoadError={() => setFailed(true)}>
          <Page pageNumber={1} width={THUMBNAIL_WIDTH} renderTextLayer={false} renderAnnotationLayer={false} />
        </Document>
      : <div className="pdf-thumbnail-loading" />}
  </div>
}
