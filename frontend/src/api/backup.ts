import request from './request'
import type { BackupConfig, BackupConfigUpdatePayload, BackupRecord, ListQueryParams, PaginatedResponse } from '@/types'

export function fetchBackupConfig(): Promise<BackupConfig> {
  return request.get<BackupConfig, BackupConfig>('/backup/config')
}

export function updateBackupConfig(data: BackupConfigUpdatePayload): Promise<BackupConfig> {
  return request.put<BackupConfig, BackupConfig>('/backup/config', data)
}

export function runBackup(): Promise<BackupRecord> {
  return request.post<BackupRecord, BackupRecord>('/backup/run')
}

export function fetchBackupRecords(params?: ListQueryParams): Promise<PaginatedResponse<BackupRecord>> {
  return request.get<PaginatedResponse<BackupRecord>, PaginatedResponse<BackupRecord>>('/backup/records', { params })
}
