import type { DateTimeString, EntityId } from "./common"

export interface ChangeLog {
  id: EntityId
  entity_type: string
  entity_id: EntityId
  entity_name?: string | null
  action: string
  field_name?: string | null
  old_value?: string | null
  new_value?: string | null
  operator: string
  comment?: string | null
  created_at: DateTimeString
}

export interface ChangeLogQueryParams {
  entity_type?: string
  entity_id?: EntityId
  action?: string
  operator?: string
  date_from?: string
  date_to?: string
  skip?: number
  limit?: number
}
