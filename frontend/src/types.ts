export type Source = 'embedded_text' | 'ocr' | 'empty' | 'failed'
export interface TextBlock { text:string; type:string; bbox:number[]|null; confidence:number|null; source:Source }
export interface PageResult { page:number; source:Source; text:string; markdown:string; blocks:TextBlock[]; confidence:number|null; warning:string|null; width:number|null; height:number|null }
export interface JobStatus { id:string; filename:string; size_bytes:number; state:string; created_at:string; updated_at:string; total_pages:number; processed_pages:number; text_pages:number; ocr_pages:number; current_message:string; error:string|null }
export interface AppConfig { max_file_size_mb:number; max_pages:number; retention_minutes:number; ocr_language:string; llm_enabled:boolean; llm_model:string|null }

export interface MergeFile { id:string; file:File; pageCount?:number; thumbnailFailed?:boolean }
