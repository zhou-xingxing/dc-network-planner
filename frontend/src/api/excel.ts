import request from './request'
import type {
  ChangeLog,
  ChangeLogQueryParams,
  EntityId,
  ExcelExportParams,
  ImportPreview,
  ImportResult,
  PaginatedResponse,
  SystemStats,
} from '@/types'

export function downloadTemplate(): Promise<Blob> {
  return request.get<Blob, Blob>('/excel/template', { responseType: 'blob' })
}

export function previewImport(file: File): Promise<ImportPreview> {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ImportPreview, ImportPreview>('/excel/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

export function confirmImport(previewId: EntityId): Promise<ImportResult> {
  return request.post<ImportResult, ImportResult>('/excel/import/confirm', { preview_id: previewId })
}

export function exportExcel(params?: ExcelExportParams): Promise<Blob> {
  return request.get<Blob, Blob>('/excel/export', { params, responseType: 'blob' })
}

export function fetchStats(): Promise<SystemStats> {
  return request.get<SystemStats, SystemStats>('/stats')
}

export function fetchChangeLogs(params?: ChangeLogQueryParams): Promise<PaginatedResponse<ChangeLog>> {
  return request.get<PaginatedResponse<ChangeLog>, PaginatedResponse<ChangeLog>>('/change-logs', { params })
}
