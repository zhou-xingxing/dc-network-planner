import request from './request'
import type {
  EntityId,
  PaginatedResponse,
  Rack,
  RackColumnListResponse,
  RackCreatePayload,
  RackListQuery,
  RackUpdatePayload,
} from '@/types'

export function fetchRacks(regionId: EntityId, params?: RackListQuery): Promise<PaginatedResponse<Rack>> {
  return request.get<PaginatedResponse<Rack>, PaginatedResponse<Rack>>(`/regions/${regionId}/racks`, { params })
}

export function fetchRackColumns(
  regionId: EntityId,
  params?: RackListQuery
): Promise<RackColumnListResponse> {
  return request.get<RackColumnListResponse, RackColumnListResponse>(
    `/regions/${regionId}/racks/columns`,
    { params }
  )
}

export function createRacks(regionId: EntityId, data: RackCreatePayload): Promise<Rack[]> {
  return request.post<Rack[], Rack[]>(`/regions/${regionId}/racks`, data)
}

export function updateRack(regionId: EntityId, rackId: EntityId, data: RackUpdatePayload): Promise<Rack> {
  return request.put<Rack, Rack>(`/regions/${regionId}/racks/${rackId}`, data)
}

export function deleteRack(regionId: EntityId, rackId: EntityId): Promise<void> {
  return request.delete<void, void>(`/regions/${regionId}/racks/${rackId}`)
}
