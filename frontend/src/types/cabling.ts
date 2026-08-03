import type { EntityId } from './common'

export interface RackSwitchPosition {
  switch_id: EntityId
  switch_name: string
  start_u: number
  height_u: number
}

export interface RackServerPosition {
  start_u: number
  height_u: number
  server_port_names: string[]
  cable_count: number
}

export interface RackOccupancy {
  rack_id: EntityId
  rack_name: string
  u_height: number
  switch_positions: RackSwitchPosition[]
  server_positions: RackServerPosition[]
}

export interface CablingPlanningLineInput {
  server_port_name: string
}

export interface CablingPlanningConnectionInput {
  switch_group_id: EntityId
  lines: CablingPlanningLineInput[]
}

export interface CablingPlanningServerInput {
  server_rack_id: EntityId
  server_start_u: number
  server_height_u: number
  connections: CablingPlanningConnectionInput[]
}

/** 前端完成输入校验后生成的规范化布线需求，不包含页面临时状态。 */
export interface CablingPlanningInput {
  region_id: EntityId
  batch_name: string
  comment: string
  servers: CablingPlanningServerInput[]
}
