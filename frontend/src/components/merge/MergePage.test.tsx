import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { MergePage } from './MergePage'
import * as api from '../../api'

vi.mock('react-pdf', async () => {
  const React = await import('react')
  return {
    Document: ({ file, children, onLoadSuccess, onLoadError }: any) => {
      const name: string = file?.name ?? ''
      React.useEffect(() => {
        if (name.includes('broken')) onLoadError?.(new Error('broken'))
        else onLoadSuccess?.({ numPages: 3 })
      }, [name])
      return <div data-testid="mock-document">{children}</div>
    },
    Page: () => <div data-testid="mock-page" />,
  }
})

function pdfFile(name: string) {
  return new File(['%PDF-1.4 test content'], name, { type: 'application/pdf' })
}

beforeEach(() => {
  vi.restoreAllMocks()
  global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  global.URL.revokeObjectURL = vi.fn()
})

async function uploadFiles(files: File[]) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  await userEvent.upload(input, files)
}

describe('MergePage', () => {
  it('adds multiple uploaded PDFs as cards', async () => {
    render(<MergePage />)
    await uploadFiles([pdfFile('rechnung.pdf'), pdfFile('vertrag.pdf')])
    expect(await screen.findByText('rechnung.pdf')).toBeInTheDocument()
    expect(screen.getByText('vertrag.pdf')).toBeInTheDocument()
    expect(screen.getByTestId('merge-summary')).toHaveTextContent('2 PDFs')
  })

  it('rejects non-PDF files', async () => {
    // Drag & drop can deliver arbitrary file types regardless of the input's
    // accept attribute, so bypass user-event's accept emulation here to
    // exercise the app's own validation.
    render(<MergePage />)
    const user = userEvent.setup({ applyAccept: false })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, new File(['x'], 'notizen.txt', { type: 'text/plain' }))
    expect(await screen.findByText(/ist keine PDF-Datei/)).toBeInTheDocument()
    expect(screen.queryByText('notizen.txt')).not.toBeInTheDocument()
  })

  it('reorders files via the move controls', async () => {
    render(<MergePage />)
    await uploadFiles([pdfFile('a.pdf'), pdfFile('b.pdf'), pdfFile('c.pdf')])
    await screen.findByText('a.pdf')

    const cards = () => screen.getAllByRole('listitem')
    expect(within(cards()[0]).getByText('a.pdf')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByLabelText('a.pdf nach hinten verschieben'))

    await waitFor(() => {
      expect(within(cards()[0]).getByText('b.pdf')).toBeInTheDocument()
      expect(within(cards()[1]).getByText('a.pdf')).toBeInTheDocument()
    })
  })

  it('removes a PDF from the list', async () => {
    render(<MergePage />)
    await uploadFiles([pdfFile('a.pdf'), pdfFile('b.pdf')])
    await screen.findByText('a.pdf')

    const user = userEvent.setup()
    await user.click(screen.getByLabelText('a.pdf entfernen'))

    await waitFor(() => expect(screen.queryByText('a.pdf')).not.toBeInTheDocument())
    expect(screen.getByText('b.pdf')).toBeInTheDocument()
  })

  it('requires at least two PDFs before merging', async () => {
    render(<MergePage />)
    await uploadFiles([pdfFile('a.pdf')])
    await screen.findByText('a.pdf')
    expect(screen.getByRole('button', { name: /PDF.*zusammenführen/ })).toBeDisabled()
  })

  it('supports adding further PDFs after the first upload', async () => {
    render(<MergePage />)
    await uploadFiles([pdfFile('a.pdf')])
    await screen.findByText('a.pdf')

    const addMoreInput = screen.getByLabelText(/Weitere PDFs hinzufügen/i)
    await userEvent.upload(addMoreInput, [pdfFile('b.pdf')])

    await waitFor(() => expect(screen.getByText('b.pdf')).toBeInTheDocument())
    expect(screen.getByTestId('merge-summary')).toHaveTextContent('2 PDFs')
  })

  it('merges files in the current visual order', async () => {
    const mergeSpy = vi.spyOn(api, 'mergePdfs').mockResolvedValue(new Blob(['merged'], { type: 'application/pdf' }))
    render(<MergePage />)
    await uploadFiles([pdfFile('a.pdf'), pdfFile('b.pdf')])
    await screen.findByText('a.pdf')

    const user = userEvent.setup()
    await user.click(screen.getByLabelText('a.pdf nach hinten verschieben'))
    await waitFor(() => {
      const cards = screen.getAllByRole('listitem')
      expect(within(cards[0]).getByText('b.pdf')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /PDFs zusammenführen/ }))

    await waitFor(() => expect(mergeSpy).toHaveBeenCalledTimes(1))
    const mergedFiles = mergeSpy.mock.calls[0][0]
    expect(mergedFiles.map(f => f.name)).toEqual(['b.pdf', 'a.pdf'])
  })

  it('still allows merging when a thumbnail fails to render', async () => {
    const mergeSpy = vi.spyOn(api, 'mergePdfs').mockResolvedValue(new Blob(['merged'], { type: 'application/pdf' }))
    render(<MergePage />)
    await uploadFiles([pdfFile('broken.pdf'), pdfFile('ok.pdf')])
    await screen.findByText('broken.pdf')

    expect(await screen.findByText('Vorschau nicht möglich')).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /PDFs zusammenführen/ }))
    await waitFor(() => expect(mergeSpy).toHaveBeenCalledTimes(1))
  })
})
