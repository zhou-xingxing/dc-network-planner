import request from './request'
import type {
  EntityId,
  ListQueryParams,
  NetworkSwitch,
  PaginatedResponse,
  SwitchBusinessType,
  SwitchBusinessTypeCreatePayload,
  SwitchBusinessTypeUpdatePayload,
  SwitchGroup,
  SwitchGroupCreatePayload,
  SwitchGroupCreateResult,
  SwitchGroupListQuery,
  SwitchGroupUpdatePayload,
  SwitchListQuery,
  SwitchPort,
  SwitchPortBulkCreatePayload,
  SwitchPortListQuery,
  SwitchUpdatePayload,
} from '@/types'

export function fetchSwitchBusinessTypes(
  params?: ListQueryParams
): Promise<PaginatedResponse<SwitchBusinessType>> {
  return request.get<PaginatedResponse<SwitchBusinessType>, PaginatedResponse<SwitchBusinessType>>(
    '/switch-business-types',
    { params }
  )
}

export function createSwitchBusinessType(
  data: SwitchBusinessTypeCreatePayload
): Promise<SwitchBusinessType> {
  return request.post<SwitchBusinessType, SwitchBusinessType>('/switch-business-types', data)
}

export function updateSwitchBusinessType(
  id: EntityId,
  data: SwitchBusinessTypeUpdatePayload
): Promise<SwitchBusinessType> {
  return request.put<SwitchBusinessType, SwitchBusinessType>(`/switch-business-types/${id}`, data)
}

export function deleteSwitchBusinessType(id: EntityId): Promise<void> {
  return request.delete<void, void>(`/switch-business-types/${id}`)
}

export function fetchSwitchGroups(
  regionId: EntityId,
  params?: SwitchGroupListQuery
): Promise<PaginatedResponse<SwitchGroup>> {
  return request.get<PaginatedResponse<SwitchGroup>, PaginatedResponse<SwitchGroup>>(
    `/regions/${regionId}/switch-groups`,
    { params }
  )
}

export function createSwitchGroupWithMembers(
  regionId: EntityId,
  data: SwitchGroupCreatePayload
): Promise<SwitchGroupCreateResult> {
  return request.post<SwitchGroupCreateResult, SwitchGroupCreateResult>(
    `/regions/${regionId}/switch-groups`,
    data
  )
}

export function updateSwitchGroup(
  regionId: EntityId,
  groupId: EntityId,
  data: SwitchGroupUpdatePayload
): Promise<SwitchGroup> {
  return request.put<SwitchGroup, SwitchGroup>(`/regions/${regionId}/switch-groups/${groupId}`, data)
}

export function deleteSwitchGroup(regionId: EntityId, groupId: EntityId): Promise<void> {
  return request.delete<void, void>(`/regions/${regionId}/switch-groups/${groupId}`)
}

export function fetchSwitches(
  regionId: EntityId,
  params?: SwitchListQuery
): Promise<PaginatedResponse<NetworkSwitch>> {
  return request.get<PaginatedResponse<NetworkSwitch>, PaginatedResponse<NetworkSwitch>>(
    `/regions/${regionId}/switches`,
    { params }
  )
}

export function updateSwitch(
  regionId: EntityId,
  switchId: EntityId,
  data: SwitchUpdatePayload
): Promise<NetworkSwitch> {
  return request.put<NetworkSwitch, NetworkSwitch>(`/regions/${regionId}/switches/${switchId}`, data)
}

export function deleteSwitch(regionId: EntityId, switchId: EntityId): Promise<void> {
  return request.delete<void, void>(`/regions/${regionId}/switches/${switchId}`)
}

export function fetchSwitchPorts(
  regionId: EntityId,
  switchId: EntityId,
  params?: SwitchPortListQuery
): Promise<PaginatedResponse<SwitchPort>> {
  return request.get<PaginatedResponse<SwitchPort>, PaginatedResponse<SwitchPort>>(
    `/regions/${regionId}/switches/${switchId}/ports`,
    { params }
  )
}

export function createSwitchPortsBulk(
  regionId: EntityId,
  switchId: EntityId,
  data: SwitchPortBulkCreatePayload
): Promise<SwitchPort[]> {
  return request.post<SwitchPort[], SwitchPort[]>(`/regions/${regionId}/switches/${switchId}/ports/bulk`, data)
}

export function deleteSwitchPort(regionId: EntityId, switchId: EntityId, portId: EntityId): Promise<void> {
  return request.delete<void, void>(`/regions/${regionId}/switches/${switchId}/ports/${portId}`)
}
