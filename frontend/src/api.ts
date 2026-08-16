import type { AppConfig, JobStatus, PageResult } from './types'

async function checked<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try { const d = await res.json(); message = d.detail || message } catch {}
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export async function uploadPdf(file: File): Promise<JobStatus> {
  const body = new FormData(); body.append('file', file)
  return checked(await fetch('/api/documents', { method:'POST', body }))
}
export async function getStatus(id:string):Promise<JobStatus>{ return checked(await fetch(`/api/documents/${id}/status`)) }
export async function getPages(id:string):Promise<PageResult[]>{ return checked(await fetch(`/api/documents/${id}/pages`)) }
export async function getConfig():Promise<AppConfig>{ return checked(await fetch('/api/config')) }
export async function deleteJob(id:string){ const r=await fetch(`/api/documents/${id}`,{method:'DELETE'}); if(!r.ok && r.status!==404) throw new Error('Dokument konnte nicht gelöscht werden.') }
export const fileUrl=(id:string)=>`/api/documents/${id}/file`
export const exportUrl=(id:string, kind:'markdown'|'text'|'json')=>`/api/documents/${id}/export/${kind}`

async function checkedBlob(res:Response):Promise<Blob>{
  if(!res.ok){
    let message=`HTTP ${res.status}`
    try{ const d=await res.json(); message=d.detail||message }catch{}
    throw new Error(message)
  }
  return res.blob()
}
export async function stripMetadata(file:File):Promise<Blob>{
  const body=new FormData(); body.append('file',file)
  return checkedBlob(await fetch('/api/tools/metadata/strip',{method:'POST',body}))
}
export async function extractImages(file:File):Promise<Blob>{
  const body=new FormData(); body.append('file',file)
  return checkedBlob(await fetch('/api/tools/images/extract',{method:'POST',body}))
}
export async function mergePdfs(files:File[]):Promise<Blob>{
  const body=new FormData(); files.forEach(f=>body.append('files',f))
  return checkedBlob(await fetch('/api/tools/merge',{method:'POST',body}))
}
