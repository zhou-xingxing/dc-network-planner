import request from './request'
import type {
  EntityId,
  ListQueryParams,
  MessageResponse,
  PaginatedResponse,
  Region,
  RegionCreatePayload,
  RegionDetail,
  RegionPlane,
  RegionPlaneCreatePayload,
  RegionPlaneUpdatePayload,
  RegionUpdatePayload,
} from '@/types'

export function fetchRegions(params?: ListQueryParams): Promise<PaginatedResponse<Region>> {
  return request.get<PaginatedResponse<Region>, PaginatedResponse<Region>>('/regions', { params })
}

export function getRegion(id: EntityId): Promise<RegionDetail> {
  return request.get<RegionDetail, RegionDetail>(`/regions/${id}`)
}

export function createRegion(data: RegionCreatePayload): Promise<Region> {
  return request.post<Region, Region>('/regions', data)
}

export function updateRegion(id: EntityId, data: RegionUpdatePayload): Promise<Region> {
  return request.put<Region, Region>(`/regions/${id}`, data)
}

export function deleteRegion(id: EntityId): Promise<MessageResponse> {
  return request.delete<MessageResponse, MessageResponse>(`/regions/${id}`)
}

export function fetchRegionPlanes(regionId: EntityId): Promise<RegionPlane[]> {
  return request.get<RegionPlane[], RegionPlane[]>(`/regions/${regionId}/planes`)
}

export function createRegionPlane(regionId: EntityId, data: RegionPlaneCreatePayload): Promise<RegionPlane> {
  return request.post<RegionPlane, RegionPlane>(`/regions/${regionId}/planes`, data)
}

export function updateRegionPlane(
  regionId: EntityId,
  planeId: EntityId,
  data: RegionPlaneUpdatePayload
): Promise<RegionPlane> {
  return request.put<RegionPlane, RegionPlane>(`/regions/${regionId}/planes/${planeId}`, data)
}

export function deleteRegionPlane(regionId: EntityId, planeId: EntityId): Promise<MessageResponse> {
  return request.delete<MessageResponse, MessageResponse>(`/regions/${regionId}/planes/${planeId}`)
}
