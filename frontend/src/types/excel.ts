import type { EntityId } from "./common"

export type ImportErrorType = "validation" | "permission" | "business"

export interface ImportRow {
  row_number: number
  region_name: string
  plane_type_name: string
  scope: string
  ip_range: string
  vlan_id?: number | null
  gateway_position?: string | null
  gateway_ip?: string | null
}

export interface ImportErrorItem {
  row: number
  errors: string[]
  region_name?: string | null
  error_type: ImportErrorType
}

export interface ImportPreview {
  preview_id: EntityId
  total_rows: number
  valid_rows: number
  error_rows: ImportErrorItem[]
  rows: ImportRow[]
}

export interface ImportResult {
  success: boolean
  imported_count: number
  error_count: number
  errors: ImportErrorItem[]
}

export interface ExcelExportParams {
  region_id?: EntityId
}
