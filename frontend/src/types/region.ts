import type { DateTimeString, EntityId } from "./common"

export interface Region {
  id: EntityId
  name: string
  description?: string | null
  plane_count: number
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface RegionCreatePayload {
  name: string
  description?: string | null
}

export interface RegionUpdatePayload {
  name?: string
  description?: string | null
}

export interface RegionPlane {
  id: EntityId
  region_id: EntityId
  plane_type_id: EntityId
  plane_type_name: string
  scope: string
  cidr?: string | null
  vlan_id?: number | null
  gateway_position?: string | null
  gateway_ip?: string | null
  gateway_ip_warning?: string | null
  parent_id?: EntityId | null
  plane_type_parent_id?: EntityId | null
  created_at: DateTimeString
  updated_at: DateTimeString
  children: RegionPlane[]
}

export interface RegionDetail extends Region {
  planes: RegionPlane[]
}

export interface RegionPlaneCreatePayload {
  plane_type_id: EntityId
  scope?: string | null
  cidr: string
  vlan_id?: number | null
  gateway_position?: string | null
  gateway_ip?: string | null
}

export interface RegionPlaneUpdatePayload {
  scope?: string | null
  cidr?: string | null
  vlan_id?: number | null
  gateway_position?: string | null
  gateway_ip?: string | null
}
