import React from 'react'
import ReactDOM from 'react-dom/client'
import { pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import './styles.css'
import App from './App'

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()

// Zählt anonym nur "eine Seite wurde geladen" — kein Cookie, keine ID, kein Bezug zu
// Nutzer oder Session. Fehler werden bewusst ignoriert, das darf den App-Start nie stören.
fetch('/api/track/pageview', { method: 'POST' }).catch(() => {})

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
