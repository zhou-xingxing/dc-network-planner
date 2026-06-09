import type { DateTimeString, EntityId } from "./common"

export type BackupMethod = "local" | "object_storage"

export interface BackupConfig {
  id: EntityId
  enabled: boolean
  cron_expression: string
  backup_file_prefix: string
  method: BackupMethod
  local_path?: string | null
  endpoint_url?: string | null
  access_key?: string | null
  secret_key_configured: boolean
  bucket?: string | null
  object_prefix?: string | null
  next_run_at?: DateTimeString | null
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface BackupConfigUpdatePayload {
  enabled: boolean
  cron_expression: string
  backup_file_prefix: string
  method: BackupMethod
  local_path?: string | null
  endpoint_url?: string | null
  access_key?: string | null
  secret_key?: string | null
  bucket?: string | null
  object_prefix?: string | null
}

export interface BackupRecord {
  id: EntityId
  status: string
  method: string
  target?: string | null
  file_size?: number | null
  error_message?: string | null
  operator: string
  started_at: DateTimeString
  finished_at?: DateTimeString | null
}
