import type { DateTimeString, EntityId, ListQueryParams } from './common'

export interface Rack {
  id: EntityId
  region_id: EntityId
  region_name: string
  name: string
  room_name: string
  rack_column: string
  rack_number: number
  u_height: number
  switch_count: number
  cable_count: number
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface RackCreatePayload {
  items: RackCreateItemPayload[]
  u_height: number
}

export interface RackCreateItemPayload {
  room_name: string
  rack_column: string
  rack_number: number
}

export interface RackUpdatePayload {
  room_name?: string
  rack_column?: string
  rack_number?: number
  u_height?: number
}

export interface RackListQuery extends ListQueryParams {
  search?: string
  room_name?: string
  rack_column?: string
}

export interface RackColumnSummary {
  room_name: string
  rack_column: string
  rack_count: number
  switch_count: number
  cable_count: number
}

export interface RackColumnListResponse {
  items: RackColumnSummary[]
  total_columns: number
  total_racks: number
  skip: number
  limit: number
}

export interface SwitchBusinessType {
  id: EntityId
  code: string
  name: string
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface SwitchBusinessTypeCreatePayload {
  code: string
  name: string
}

export type SwitchBusinessTypeUpdatePayload = Partial<SwitchBusinessTypeCreatePayload>

export type SwitchGroupMode = 'pair' | 'single'
export type SwitchMemberRole = 'a' | 'b' | 'single'
export type SwitchGroupReadinessIssueCode =
  | 'MISSING_MEMBER_A'
  | 'MISSING_MEMBER_B'
  | 'MISSING_SINGLE_MEMBER'
  | 'UNEXPECTED_MEMBER_COUNT'
  | 'PORT_SPEED_MISMATCH'

export interface SwitchGroupReadinessIssue {
  code: SwitchGroupReadinessIssueCode
  message: string
}

export interface SwitchGroup {
  id: EntityId
  region_id: EntityId
  region_name: string
  business_type_id: EntityId
  business_type_code: string
  business_type_name: string
  name: string
  group_mode: SwitchGroupMode
  member_count: number
  is_member_config_ready: boolean
  readiness_issues: SwitchGroupReadinessIssue[]
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface SwitchGroupCreatePayload {
  business_type_id: EntityId
  name: string
  group_mode: SwitchGroupMode
  members: SwitchGroupMemberCreatePayload[]
  port_range: SwitchPortBulkCreatePayload
}

export interface SwitchGroupMemberCreatePayload {
  rack_id: EntityId
  member_role: SwitchMemberRole
  name: string
  port_speed_mbps: number
  start_u: number
  height_u: number
}

export type SwitchGroupUpdatePayload = Partial<
  Pick<SwitchGroupCreatePayload, 'business_type_id' | 'name' | 'group_mode'>
>

export interface SwitchGroupListQuery extends ListQueryParams {
  search?: string
  business_type_id?: EntityId
}

export interface NetworkSwitch {
  id: EntityId
  region_id: EntityId
  region_name: string
  rack_id: EntityId
  rack_name: string
  switch_group_id?: EntityId | null
  switch_group_name?: string | null
  business_type_name?: string | null
  member_role?: SwitchMemberRole | null
  name: string
  port_speed_mbps: number
  start_u: number
  height_u: number
  port_count: number
  used_port_count: number
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface SwitchGroupCreateResult {
  group: SwitchGroup
  members: NetworkSwitch[]
}

/** 交换机前端表单数据，仅供视图层使用，不对应独立的创建接口（交换机通过交换机组组合接口创建）。 */
export interface SwitchFormData {
  rack_id: EntityId
  switch_group_id?: EntityId | null
  member_role?: SwitchMemberRole | null
  name: string
  port_speed_mbps: number
  start_u: number
  height_u: number
}

export type SwitchUpdatePayload = Partial<SwitchFormData>

export interface SwitchListQuery extends ListQueryParams {
  search?: string
  rack_id?: EntityId
  switch_group_id?: EntityId
}

export interface SwitchPort {
  id: EntityId
  switch_id: EntityId
  card_number: number
  subcard_number: number
  port_number: number
  is_occupied: boolean
  cable_entry_id?: EntityId | null
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface SwitchPortListQuery extends ListQueryParams {
  card_number?: number
  subcard_number?: number
}

export interface SwitchPortBulkCreatePayload {
  card_number: number
  subcard_number: number
  start_port_number: number
  end_port_number: number
}
