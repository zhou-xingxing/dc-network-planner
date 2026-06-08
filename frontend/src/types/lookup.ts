import type { EntityId } from "./common"

export interface LookupResult {
  id: EntityId
  cidr: string
  region_name: string
  plane_type_name: string
  scope: string
  vlan_id?: number | null
  gateway_position?: string | null
  gateway_ip?: string | null
  parent_id?: EntityId | null
  plane_type_parent_id?: EntityId | null
  is_match: boolean
  children: LookupResult[]
}

export interface LookupResponse {
  results: LookupResult[]
  total: number
}
