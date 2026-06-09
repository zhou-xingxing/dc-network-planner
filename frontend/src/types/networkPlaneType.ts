import type { DateTimeString, EntityId } from "./common"

export interface NetworkPlaneType {
  id: EntityId
  name: string
  description?: string | null
  is_private: boolean
  vrf?: string | null
  parent_id?: EntityId | null
  parent_name?: string | null
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface PlaneTypeTreeNode extends NetworkPlaneType {
  children: PlaneTypeTreeNode[]
  level: number
}

export interface NetworkPlaneTypeCreatePayload {
  name: string
  description?: string | null
  is_private?: boolean
  vrf?: string | null
  parent_id?: EntityId | null
}

export interface NetworkPlaneTypeUpdatePayload {
  name?: string
  description?: string | null
  is_private?: boolean
  vrf?: string | null
  parent_id?: EntityId | null
}
