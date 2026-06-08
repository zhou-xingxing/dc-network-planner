import type { DateTimeString, EntityId } from "./common"

export interface PlaneByRegionStat {
  region_name: string
  count: number
}

export interface RecentChangeStat {
  id: EntityId
  entity_type: string
  action: string
  operator: string
  summary: string
  created_at: DateTimeString
}

export interface SystemStats {
  total_regions: number
  total_plane_types: number
  total_region_planes: number
  total_change_logs: number
  plane_by_scope: Record<string, number>
  plane_by_region: PlaneByRegionStat[]
  recent_changes: RecentChangeStat[]
}
