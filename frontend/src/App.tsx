import { useEffect, useMemo, useRef, useState } from 'react'
import { Document, Page } from 'react-pdf'
import ReactMarkdown from 'react-markdown'
import { Check, ChevronLeft, ChevronRight, Clipboard, Copy, Download, Eraser, FileText, Heart, HelpCircle, Images, Menu, Moon, Plus, RotateCw, Search, Sun, Trash2, UploadCloud, X, ZoomIn, ZoomOut } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { deleteJob, exportUrl, extractImages, fileUrl, getConfig, getPages, getStatus, stripMetadata, uploadPdf } from './api'
import type { AppConfig, JobStatus, PageResult } from './types'

type Tab='preview'|'markdown'|'text'
type Tool='extract'|'metadata'|'images'

function formatBytes(bytes:number){ if(bytes<1024*1024) return `${(bytes/1024).toFixed(0)} KB`; return `${(bytes/1024/1024).toFixed(1)} MB` }

function App(){
  const [status,setStatus]=useState<JobStatus|null>(null)
  const [pages,setPages]=useState<PageResult[]>([])
  const [currentPage,setCurrentPage]=useState(1)
  const [tab,setTab]=useState<Tab>('preview')
  const [zoom,setZoom]=useState(0.9)
  const [rotation,setRotation]=useState(0)
  const [theme,setTheme]=useState<'light'|'dark'>(()=>localStorage.getItem('pdfpress-theme')==='dark'?'dark':'light')
  const [error,setError]=useState<string|null>(null)
  const [drag,setDrag]=useState(false)
  const [config,setConfig]=useState<AppConfig|null>(null)
  const [settingsOpen,setSettingsOpen]=useState(false)
  const [search,setSearch]=useState('')
  const [activeTool,setActiveTool]=useState<Tool>('extract')
  const [legalOpen,setLegalOpen]=useState<'impressum'|'datenschutz'|null>(()=>{
    const p=window.location.pathname
    return p==='/impressum'?'impressum':p==='/datenschutz'?'datenschutz':null
  })
  const inputRef=useRef<HTMLInputElement>(null)

  useEffect(()=>{ document.documentElement.dataset.theme=theme; localStorage.setItem('pdfpress-theme',theme) },[theme])
  useEffect(()=>{ getConfig().then(setConfig).catch(()=>{}) },[])

  useEffect(()=>{
    function onPop(){
      const p=window.location.pathname
      setLegalOpen(p==='/impressum'?'impressum':p==='/datenschutz'?'datenschutz':null)
    }
    window.addEventListener('popstate',onPop)
    return ()=>window.removeEventListener('popstate',onPop)
  },[])

  function openLegal(kind:'impressum'|'datenschutz',e?:{preventDefault():void}){
    e?.preventDefault()
    window.history.pushState({},'',`/${kind}`)
    setLegalOpen(kind)
  }
  function closeLegal(){
    window.history.pushState({},'','/')
    setLegalOpen(null)
  }

  useEffect(()=>{
    if(!status?.id || ['COMPLETE','FAILED'].includes(status.state)) return
    const timer=window.setInterval(async()=>{
      try {
        const [s,p]=await Promise.all([getStatus(status.id),getPages(status.id)])
        setStatus(s); setPages(p)
        if(currentPage>Math.max(1,s.processed_pages)) setCurrentPage(Math.max(1,s.processed_pages))
      } catch(e){ setError((e as Error).message) }
    },700)
    return ()=>clearInterval(timer)
  },[status?.id,status?.state,currentPage])

  useEffect(()=>{
    if(status?.state==='COMPLETE') getPages(status.id).then(setPages).catch(()=>{})
  },[status?.state,status?.id])

  const pageData=pages.find(p=>p.page===currentPage)
  const filteredPages=useMemo(()=> search.trim()?pages.filter(p=>(p.text+' '+p.markdown).toLowerCase().includes(search.toLowerCase())):pages,[pages,search])

  async function handleFile(file?:File){
    if(!file) return
    setError(null)
    if(file.type!=='application/pdf' && !file.name.toLowerCase().endsWith('.pdf')){ setError('Bitte eine PDF-Datei auswählen.'); return }
    try{
      const s=await uploadPdf(file); setStatus(s); setPages([]); setCurrentPage(1); setTab('preview')
    }catch(e){ setError((e as Error).message) }
  }
  async function reset(deleteExisting=true){
    if(deleteExisting && status?.id){ try{await deleteJob(status.id)}catch{} }
    setStatus(null);setPages([]);setCurrentPage(1);setSearch('');setError(null);setRotation(0);setZoom(.9)
  }
  async function copyCurrent(){
    const content=tab==='markdown'?pageData?.markdown:pageData?.text
    if(content) await navigator.clipboard.writeText(content)
  }

  if(!status){
    return <div className="app-shell start-shell">
      <Header theme={theme} setTheme={setTheme} onSettings={()=>setSettingsOpen(true)} activeTool={activeTool} onToolChange={setActiveTool} />
      <main className="start-main">
        <section className="hero">
          <img src="/PDFPressLogo.png" className="hero-logo" alt="PDFPress – PDF rein. Strukturierter Text raus." />
          {activeTool==='extract' ? <>
            <div className={`dropzone ${drag?'dragging':''}`} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);handleFile(e.dataTransfer.files[0])}} onClick={()=>inputRef.current?.click()} role="button" tabIndex={0} onKeyDown={e=>{if(e.key==='Enter'||e.key===' ') inputRef.current?.click()}}>
              <div className="upload-icon"><UploadCloud size={32}/></div>
              <h2>PDF hier ablegen</h2>
              <p>oder eine Datei von deinem Gerät auswählen</p>
              <button className="primary" onClick={e=>{e.stopPropagation();inputRef.current?.click()}}>PDF auswählen</button>
              <span className="limits">Max. {config?.max_file_size_mb ?? 100} MB · bis {config?.max_pages ?? 200} Seiten</span>
              <input ref={inputRef} hidden type="file" accept="application/pdf,.pdf" onChange={e=>handleFile(e.target.files?.[0])}/>
            </div>
            {error && <div className="error-banner">{error}</div>}
          </> : <ToolPage key={activeTool} tool={activeTool}/>}
        </section>
        {activeTool==='extract' && <section className="seo-info">
          <h1>Datenfreundlicher PDF-Konverter: PDF zu Markdown, Text und JSON</h1>
          <p>PDFPress extrahiert Text und Struktur aus PDF-Dateien und wandelt sie in sauberes Markdown, reinen Text oder JSON um — inklusive automatischer Texterkennung (OCR) für gescannte Dokumente. Überschriften, Listen und Tabellen werden dabei erkannt, nicht nur roher Fließtext.</p>
          <h2>Warum PDFPress datenfreundlich ist</h2>
          <p>Hochgeladene Dokumente werden ausschließlich auf diesem Server verarbeitet und automatisch gelöscht — es gibt keine Benutzerkonten, keine Dokumentbibliothek und keine Weitergabe an Cloud-Dienste Dritter. Details dazu in der <a href="/datenschutz" onClick={e=>openLegal('datenschutz',e)}>Datenschutzerklärung</a>.</p>
          <h2>Häufige Fragen zum Datenumgang</h2>
          <div className="faq">
            <details>
              <summary>Was passiert mit meinem PDF nach dem Hochladen?</summary>
              <p>Es wird ausschließlich auf diesem Server verarbeitet (Textextraktion, OCR, Strukturerkennung) und liegt dabei nur im flüchtigen Arbeitsspeicher-Dateisystem (tmpfs) des Backend-Containers — nicht auf einer dauerhaften Festplatte. Es gibt keine Weitergabe an externe Cloud-Dienste.</p>
            </details>
            <details>
              <summary>Wie lange wird mein Dokument gespeichert?</summary>
              <p>Standardmäßig {config?.retention_minutes ?? 60} Minuten, danach automatisch und unwiderruflich gelöscht. Du kannst es jederzeit auch manuell vorher löschen.</p>
            </details>
            <details>
              <summary>Wer kann mein Dokument sehen, solange es existiert?</summary>
              <p>Jede Person mit dem Link zu deinem Dokument (einer zufälligen, nicht erratbaren ID) kann während der Aufbewahrungsdauer darauf zugreifen — es gibt keinen zusätzlichen Passwortschutz. Teile den Link deshalb nur mit Personen, denen du das Dokument auch sonst zeigen würdest.</p>
            </details>
            <details>
              <summary>Wird meine IP-Adresse oder mein Zugriff protokolliert?</summary>
              <p>Nein. Der Webserver, der als einziger externer Zugangspunkt dient, führt kein Zugriffs-Log. Es werden keine Seitenaufrufe oder IP-Adressen dauerhaft gespeichert oder ausgewertet.</p>
            </details>
            <details>
              <summary>Wird mein Dokument für KI-Training verwendet?</summary>
              <p>Nein. Es findet kein Training statt. Die optionale KI-Strukturierungsstufe ist auf dieser Instanz standardmäßig deaktiviert; falls sie aktiv ist, läuft sie über ein selbst betriebenes, lokales Sprachmodell (Ollama) — Textinhalte verlassen den Server auch dann nicht.</p>
            </details>
          </div>
        </section>}
        {activeTool==='metadata' && <section className="seo-info">
          <h1>PDF-Metadaten entfernen — Autor, Software und Erstellungsdatum löschen</h1>
          <p>Jede PDF-Datei trägt unsichtbare Metadaten in sich: Autorenname, verwendete Software (z. B. "Microsoft Word – PC-BUERO-03"), Erstellungs- und Änderungsdatum, teils sogar interne Dateipfade. Bevor du ein Dokument weitergibst oder veröffentlichst, verrät das oft mehr über dich oder dein Unternehmen, als beabsichtigt. Dieses Tool entfernt Dokumentinformationen (Docinfo) und eingebettete XMP-Metadaten vollständig aus deiner PDF-Datei — der eigentliche Inhalt bleibt unverändert.</p>
          <h2>Warum das datenfreundlich ist</h2>
          <p>Die Verarbeitung läuft vollständig im Arbeitsspeicher des Servers, ohne dass die Datei zwischengespeichert wird — noch unmittelbarer als bei der PDF-Extraktion. Details dazu in der <a href="/datenschutz" onClick={e=>openLegal('datenschutz',e)}>Datenschutzerklärung</a>.</p>
        </section>}
        {activeTool==='images' && <section className="seo-info">
          <h1>Bilder aus PDF extrahieren — als ZIP herunterladen</h1>
          <p>Ob Fotos, Diagramme, Scans oder Grafiken: PDFPress durchsucht dein PDF nach allen eingebetteten Bildern und lädt sie dir gesammelt als ZIP-Datei herunter — in ihrer ursprünglichen Qualität, ohne Umweg über Screenshots oder verlustbehaftete Bildschirmabfotografie.</p>
          <h2>Warum das datenfreundlich ist</h2>
          <p>Auch hier läuft die Verarbeitung ausschließlich im Arbeitsspeicher des Servers, ohne dauerhafte Speicherung. Details dazu in der <a href="/datenschutz" onClick={e=>openLegal('datenschutz',e)}>Datenschutzerklärung</a>.</p>
        </section>}
        <nav className="legal-links footer-links"><a href="/impressum" onClick={e=>openLegal('impressum',e)}>Impressum</a><span>·</span><a href="/datenschutz" onClick={e=>openLegal('datenschutz',e)}>Datenschutz</a><span>·</span><a href="mailto:t.ley@outlook.de?subject=PDFPress%20Feedback">Kontakt</a><span>·</span><a href="https://github.com/ley338-gif/PDFPress" target="_blank" rel="noopener noreferrer">Quellcode</a></nav>
      </main>
      {settingsOpen&&<SettingsModal config={config} onClose={()=>setSettingsOpen(false)} onOpenLegal={kind=>{setSettingsOpen(false);openLegal(kind)}}/>}
      {legalOpen&&<LegalModal kind={legalOpen} onClose={closeLegal}/>}
    </div>
  }

  return <div className="app-shell workspace-shell">
    <Header theme={theme} setTheme={setTheme} onSettings={()=>setSettingsOpen(true)} meta={<div className="doc-meta"><strong>{status.filename}</strong><span>·</span><span>{status.total_pages||'…'} Seiten</span><span>·</span><span>{formatBytes(status.size_bytes)}</span></div>} />
    <StatusBar status={status}/>
    {status.state!=='COMPLETE'&&status.state!=='FAILED'&&<div className="processing-hint">Die Verarbeitung kann bei umfangreichen oder gescannten PDFs mehrere Minuten dauern.</div>}
    {error&&<div className="inline-error">{error}</div>}
    <main className="workspace">
      <aside className="thumb-panel">
        <div className="panel-title">SEITEN</div>
        <div className="thumb-scroll">
          <Document file={fileUrl(status.id)} loading={<div className="tiny-muted">PDF wird geladen…</div>}>
            {(filteredPages.length?filteredPages:Array.from({length:status.total_pages||status.processed_pages},(_,i)=>({page:i+1} as PageResult))).map(p=><button key={p.page} className={`thumb ${currentPage===p.page?'active':''}`} onClick={()=>setCurrentPage(p.page)} aria-label={`Seite ${p.page}`}>
              <div className="thumb-canvas"><Page pageNumber={p.page} width={88} renderTextLayer={false} renderAnnotationLayer={false}/></div>
              <span>{p.page}</span>
              {'warning' in p && p.warning && <span className="warning-dot" title={p.warning}/>} 
            </button>)}
          </Document>
        </div>
      </aside>

      <section className="pdf-panel">
        <div className="viewer-toolbar">
          <div className="page-control"><button disabled={currentPage<=1} onClick={()=>setCurrentPage(n=>Math.max(1,n-1))}><ChevronLeft size={18}/></button><input value={currentPage} onChange={e=>setCurrentPage(Math.min(Math.max(1,Number(e.target.value)||1),Math.max(1,status.total_pages)))} /><span>/ {status.total_pages||'…'}</span><button disabled={currentPage>=status.total_pages} onClick={()=>setCurrentPage(n=>Math.min(status.total_pages,n+1))}><ChevronRight size={18}/></button></div>
          <div className="toolbar-divider"/>
          <button onClick={()=>setZoom(z=>Math.max(.4,z-.1))} title="Verkleinern"><ZoomOut size={18}/></button>
          <span className="zoom-value">{Math.round(zoom*100)}%</span>
          <button onClick={()=>setZoom(z=>Math.min(2,z+.1))} title="Vergrößern"><ZoomIn size={18}/></button>
          <div className="toolbar-spacer"/>
          <button onClick={()=>setRotation(r=>(r+90)%360)} title="Drehen"><RotateCw size={18}/></button>
        </div>
        <div className="pdf-stage">
          <Document file={fileUrl(status.id)} loading={<div className="center-loading">PDF wird geladen…</div>} error={<div className="center-loading">PDF konnte nicht dargestellt werden.</div>}>
            <Page pageNumber={currentPage} scale={zoom} rotate={rotation} renderAnnotationLayer={true} renderTextLayer={true}/>
          </Document>
        </div>
      </section>

      <section className="text-panel">
        <div className="text-toolbar">
          <div className="tabs"><button className={tab==='preview'?'active':''} onClick={()=>setTab('preview')}>Vorschau</button><button className={tab==='markdown'?'active':''} onClick={()=>setTab('markdown')}>Markdown</button><button className={tab==='text'?'active':''} onClick={()=>setTab('text')}>Text</button></div>
          <button onClick={copyCurrent} title="Aktuelle Seite kopieren"><Copy size={18}/></button>
        </div>
        <div className="search-row"><Search size={16}/><input placeholder="Dokument durchsuchen" value={search} onChange={e=>setSearch(e.target.value)}/>{search&&<button onClick={()=>setSearch('')}><X size={15}/></button>}</div>
        <div className="text-content">
          <div className="page-label">Seite {currentPage}{pageData?.source==='ocr'&&<span className="source-pill">OCR{pageData.confidence!=null?` · ${Math.round(pageData.confidence*100)}%`:''}</span>}{pageData?.source==='embedded_text'&&<span className="source-pill">PDF-Text</span>}</div>
          {!pageData ? <div className="processing-placeholder"><div className="spinner"/><strong>Seite wird verarbeitet</strong><span>{status.current_message}</span></div> : pageData.warning ? <><div className="quality-warning">{pageData.warning}</div><TextView tab={tab} page={pageData}/></> : <TextView tab={tab} page={pageData}/>} 
        </div>
        <div className="text-footer"><span>{(pageData?.text||'').length.toLocaleString('de-DE')} Zeichen</span><button className="copy-button" onClick={copyCurrent}><Clipboard size={16}/> Kopieren</button></div>
      </section>
    </main>
    <footer className="bottom-bar">
      <div className="bottom-bar-left">
        <button className="danger-outline" onClick={()=>reset(true)}><Trash2 size={17}/> Dokument löschen</button>
        <nav className="legal-links workspace-legal-links"><a href="/impressum" onClick={e=>openLegal('impressum',e)}>Impressum</a><span>·</span><a href="/datenschutz" onClick={e=>openLegal('datenschutz',e)}>Datenschutz</a></nav>
      </div>
      <div className={`completion ${status.state==='COMPLETE'?'done':''}`}>{status.state==='COMPLETE'?<Check size={17}/>:<div className="mini-spinner"/>}<span>{status.state==='COMPLETE'?'Verarbeitung abgeschlossen':status.current_message}</span></div>
      <div className="exports"><a className={status.state!=='COMPLETE'?'disabled':''} href={status.state==='COMPLETE'?exportUrl(status.id,'markdown'):undefined}><Download size={17}/> Markdown</a><a className={status.state!=='COMPLETE'?'disabled':''} href={status.state==='COMPLETE'?exportUrl(status.id,'text'):undefined}><Download size={17}/> TXT</a><a className={status.state!=='COMPLETE'?'disabled':''} href={status.state==='COMPLETE'?exportUrl(status.id,'json'):undefined}><Download size={17}/> JSON</a><button className="primary" onClick={()=>reset(true)}><Plus size={18}/> Neue PDF</button></div>
    </footer>
    {settingsOpen&&<SettingsModal config={config} onClose={()=>setSettingsOpen(false)} onOpenLegal={kind=>{setSettingsOpen(false);openLegal(kind)}}/>}
    {legalOpen&&<LegalModal kind={legalOpen} onClose={closeLegal}/>}
  </div>
}

function openKofi(){
  if(window.confirm('Du verlässt PDFPress.de und wirst zu Ko-fi (extern) weitergeleitet. Fortfahren?')){
    window.open('https://ko-fi.com/thomas1809','_blank','noopener,noreferrer')
  }
}

const TOOL_ITEMS:[Tool,string,LucideIcon][]=[['extract','PDF → Text',FileText],['metadata','Metadaten entfernen',Eraser],['images','Bilder extrahieren',Images]]

function Header({theme,setTheme,onSettings,meta,activeTool,onToolChange}:{theme:'light'|'dark';setTheme:(t:'light'|'dark')=>void;onSettings:()=>void;meta?:JSX.Element;activeTool?:Tool;onToolChange?:(t:Tool)=>void}){
  const [menuOpen,setMenuOpen]=useState(false)
  const hasNav=activeTool!==undefined && onToolChange!==undefined
  return <header className="header">
    <div className="brand"><img src="/PDFPressCompactLogo.png" className="header-logo" alt="PDFPress" /></div>
    {meta || (hasNav ? <ToolNav active={activeTool} onChange={onToolChange}/> : <div/>)}
    <div className="header-actions">
      <button className="icon-heart" onClick={openKofi} title="Unterstütze PDFPress auf Ko-fi (extern)"><Heart size={21}/></button>
      <button className="icon-theme" onClick={()=>setTheme(theme==='light'?'dark':'light')} title="Darstellung wechseln">{theme==='light'?<Moon size={21}/>:<Sun size={21}/>}</button>
      <button className="icon-info" onClick={onSettings} title="Info"><HelpCircle size={21}/></button>
      {hasNav && <button className="hamburger" onClick={()=>setMenuOpen(o=>!o)} aria-label="Menü" aria-expanded={menuOpen}><Menu size={21}/></button>}
    </div>
    {hasNav && menuOpen && <MobileMenu active={activeTool} onChange={t=>{onToolChange(t);setMenuOpen(false)}} onClose={()=>setMenuOpen(false)} theme={theme} setTheme={setTheme} onSettings={()=>{onSettings();setMenuOpen(false)}}/>}
  </header>
}

function ToolNav({active,onChange}:{active:Tool;onChange:(t:Tool)=>void}){
  return <nav className="tool-nav">{TOOL_ITEMS.map(([key,label,Icon])=><button key={key} className={active===key?'active':''} onClick={()=>onChange(key)}><Icon size={16}/>{label}</button>)}</nav>
}

function MobileMenu({active,onChange,onClose,theme,setTheme,onSettings}:{active:Tool;onChange:(t:Tool)=>void;onClose:()=>void;theme:'light'|'dark';setTheme:(t:'light'|'dark')=>void;onSettings:()=>void}){
  useEffect(()=>{
    function onKeyDown(e:KeyboardEvent){ if(e.key==='Escape') onClose() }
    document.addEventListener('keydown',onKeyDown)
    return ()=>document.removeEventListener('keydown',onKeyDown)
  },[onClose])
  return <>
    <div className="menu-backdrop" onClick={onClose}/>
    <div className="mobile-menu" role="menu">
      {TOOL_ITEMS.map(([key,label,Icon])=><button key={key} role="menuitem" className={active===key?'active':''} onClick={()=>onChange(key)}><Icon size={18}/>{label}</button>)}
      <div className="mobile-menu-divider"/>
      <button role="menuitem" onClick={onSettings}><HelpCircle size={18}/>Info</button>
      <button role="menuitem" onClick={()=>setTheme(theme==='light'?'dark':'light')}>{theme==='light'?<Moon size={18}/>:<Sun size={18}/>}Darstellung wechseln</button>
      <button role="menuitem" onClick={openKofi}><Heart size={18}/>Unterstützen (Ko-fi)</button>
    </div>
  </>
}

function ToolPage({tool}:{tool:'metadata'|'images'}){
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string|null>(null)
  const [result,setResult]=useState<{url:string;name:string}|null>(null)
  const [drag,setDrag]=useState(false)
  const inputRef=useRef<HTMLInputElement>(null)

  useEffect(()=>()=>{ if(result) URL.revokeObjectURL(result.url) },[result])

  async function handleFile(file?:File){
    if(!file) return
    setError(null)
    if(file.type!=='application/pdf' && !file.name.toLowerCase().endsWith('.pdf')){ setError('Bitte eine PDF-Datei auswählen.'); return }
    setBusy(true)
    try{
      const blob=tool==='metadata'?await stripMetadata(file):await extractImages(file)
      const suffix=tool==='metadata'?'-ohne-metadaten.pdf':'-bilder.zip'
      setResult({url:URL.createObjectURL(blob), name:file.name.replace(/\.pdf$/i,'')+suffix})
    }catch(e){ setError((e as Error).message) }
    finally{ setBusy(false) }
  }

  const title=tool==='metadata'?'Metadaten entfernen':'Bilder extrahieren'
  const desc=tool==='metadata'?'Entfernt Autor, Erstellungsdatum, Software-Angaben und andere Metadaten aus deinem PDF.':'Extrahiert alle eingebetteten Bilder aus deinem PDF als ZIP-Datei.'

  return <>
    <div className={`dropzone ${drag?'dragging':''}`} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);handleFile(e.dataTransfer.files[0])}} onClick={()=>!busy&&inputRef.current?.click()} role="button" tabIndex={0} onKeyDown={e=>{if(!busy&&(e.key==='Enter'||e.key===' ')) inputRef.current?.click()}}>
      <div className="upload-icon"><UploadCloud size={32}/></div>
      <h2>{title}</h2>
      <p>{desc}</p>
      {busy ? <div className="spinner"/> : result ? <a className="primary" href={result.url} download={result.name} onClick={e=>e.stopPropagation()}><Download size={18}/> {result.name}</a> : <button className="primary" onClick={e=>{e.stopPropagation();inputRef.current?.click()}}>PDF auswählen</button>}
      <input ref={inputRef} hidden type="file" accept="application/pdf,.pdf" onChange={e=>handleFile(e.target.files?.[0])}/>
    </div>
    {error && <div className="error-banner">{error}</div>}
  </>
}

function StatusBar({status}:{status:JobStatus}){
  const complete=status.state==='COMPLETE'
  const items=[['Analyse',status.total_pages>0], [`${status.text_pages} Seiten mit Text`,status.text_pages>0||complete],[`${status.ocr_pages} Seiten per OCR`,status.ocr_pages>0||complete],['Struktur erkannt',complete]] as const
  return <div className="statusbar"><div className="status-items">{items.map(([label,ok])=><div key={label} className={ok?'ok':''}><span className="status-icon">{ok?<Check size={14}/>:<div className="mini-spinner"/>}</span>{label}</div>)}</div><div className="status-progress"><strong>{status.processed_pages} / {status.total_pages||'…'} Seiten</strong><span className={complete?'badge done':'badge'}>{complete?'Fertig':status.state==='FAILED'?'Fehler':'Läuft'}</span></div></div>
}

function TextView({tab,page}:{tab:Tab;page:PageResult}){
  if(tab==='markdown') return <pre className="code-view">{page.markdown||'—'}</pre>
  if(tab==='text') return <pre className="plain-view">{page.text||'—'}</pre>
  return <div className="markdown-view"><ReactMarkdown>{page.markdown||page.text||'—'}</ReactMarkdown></div>
}

function SettingsModal({config,onClose,onOpenLegal}:{config:AppConfig|null;onClose:()=>void;onOpenLegal:(kind:'impressum'|'datenschutz')=>void}){
  return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal" onMouseDown={e=>e.stopPropagation()}><div className="modal-head"><div><h3>PDFPress Einstellungen</h3><p>Laufende Serverkonfiguration</p></div><button onClick={onClose}><X size={20}/></button></div><div className="settings-grid"><span>Maximale Dateigröße</span><strong>{config?.max_file_size_mb ?? '—'} MB</strong><span>Maximale Seiten</span><strong>{config?.max_pages ?? '—'}</strong><span>Automatisches Löschen</span><strong>{config?.retention_minutes ?? '—'} Minuten</strong><span>OCR-Sprache</span><strong>{config?.ocr_language ?? '—'}</strong><span>Lokales LLM</span><strong>{config?.llm_enabled?config.llm_model:'Deaktiviert'}</strong></div><p className="modal-note">Serverwerte werden über die <code>.env</code>-Datei geändert. PDFPress speichert keine Dokumentbibliothek. PDFPress ist freie Software (AGPL-3.0) — der Quellcode dieser Instanz ist unten verlinkt.</p><nav className="legal-links"><a href="/impressum" onClick={e=>{e.preventDefault();onOpenLegal('impressum')}}>Impressum</a><span>·</span><a href="/datenschutz" onClick={e=>{e.preventDefault();onOpenLegal('datenschutz')}}>Datenschutz</a><span>·</span><a href="mailto:t.ley@outlook.de?subject=PDFPress%20Feedback">Kontakt</a><span>·</span><a href="https://github.com/ley338-gif/PDFPress" target="_blank" rel="noopener noreferrer">Quellcode</a></nav></div></div>
}

function LegalModal({kind,onClose}:{kind:'impressum'|'datenschutz';onClose:()=>void}){
  const modalRef=useRef<HTMLDivElement>(null)
  const closeRef=useRef<HTMLButtonElement>(null)

  useEffect(()=>{
    const previouslyFocused=document.activeElement as HTMLElement|null
    closeRef.current?.focus()
    const prevOverflow=document.body.style.overflow
    document.body.style.overflow='hidden'
    function onKeyDown(e:KeyboardEvent){
      if(e.key==='Escape'){ onClose(); return }
      if(e.key==='Tab' && modalRef.current){
        const focusables=modalRef.current.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])')
        if(!focusables.length) return
        const first=focusables[0], last=focusables[focusables.length-1]
        if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus() }
        else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown',onKeyDown)
    return ()=>{
      document.removeEventListener('keydown',onKeyDown)
      document.body.style.overflow=prevOverflow
      previouslyFocused?.focus?.()
    }
  },[onClose])

  return <div className="modal-backdrop legal-modal-backdrop" onMouseDown={onClose}>
    <div className="modal legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-modal-title" ref={modalRef} onMouseDown={e=>e.stopPropagation()}>
      <div className="modal-head">
        <h3 id="legal-modal-title">{kind==='impressum'?'Impressum':'Datenschutzerklärung'}</h3>
        <button ref={closeRef} onClick={onClose} aria-label="Schließen"><X size={20}/></button>
      </div>
      <div className="legal-modal-body legal-page">
        {kind==='impressum' ? <>
          <p>Angaben gemäß § 5 DDG (Digitale-Dienste-Gesetz)</p>
          <h2>Verantwortlich</h2>
          <p>Thomas Ley<br/>Ringstraße 129<br/>59821 Arnsberg<br/>Deutschland</p>
          <h2>Kontakt</h2>
          <p>E-Mail: t.ley@outlook.de</p>
          <h2>Inhaltlich verantwortlich gemäß § 18 Abs. 2 MStV</h2>
          <p>Thomas Ley<br/>Ringstraße 129, 59821 Arnsberg</p>
        </> : <>
          <h2>1. Verantwortlicher</h2>
          <p>Thomas Ley<br/>Ringstraße 129, 59821 Arnsberg<br/>E-Mail: t.ley@outlook.de</p>
          <h2>2. Verarbeitung hochgeladener PDF-Dokumente</h2>
          <p>PDFPress verarbeitet von dir hochgeladene PDF-Dateien ausschließlich temporär auf diesem Server, um Text zu extrahieren und die Dokumentstruktur zu rekonstruieren. Es gibt keine Benutzerkonten, keine Dokumentbibliothek und keine Weitergabe an Cloud-Dienste Dritter. Dokumente und daraus erzeugte Ergebnisse werden automatisch gelöscht — standardmäßig nach 60 Minuten (serverseitig konfigurierbar). Rechtsgrundlage ist Art. 6 Abs. 1 lit. b bzw. f DSGVO.</p>
          <h2>3. Server-Logs</h2>
          <p>Der vorgeschaltete Reverse Proxy (Caddy) verarbeitet beim Aufruf dieser Website technisch notwendige Verbindungsdaten (u. a. IP-Adresse) ausschließlich im Arbeitsspeicher, um die Anfrage weiterzuleiten. Es ist kein Zugriffs-Logging (Access-Log) aktiviert — es werden keine einzelnen Seitenaufrufe dauerhaft gespeichert oder ausgewertet.</p>
          <h2>4. Lokale Speicherung im Browser</h2>
          <p>PDFPress verwendet keine Cookies. Im lokalen Speicher (localStorage) deines Browsers wird lediglich die Hell/Dunkel-Modus-Einstellung gespeichert — rein funktional, ohne Personenbezug oder Trackingzweck.</p>
          <h2>5. Optionale lokale KI-Strukturierung</h2>
          <p>Diese Instanz von PDFPress betreibt aktuell keine optionale KI-Strukturierungsstufe (Ollama ist deaktiviert). Die Dokumentstruktur wird ausschließlich regelbasiert auf diesem Server rekonstruiert; Textinhalte verlassen den Server dafür nicht.</p>
          <h2>6. Deine Rechte</h2>
          <p>Du hast das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung der Verarbeitung, Datenübertragbarkeit und Widerspruch (Art. 15–21 DSGVO) sowie das Recht auf Beschwerde bei einer Datenschutzaufsichtsbehörde.</p>
        </>}
      </div>
    </div>
  </div>
}

export default App
