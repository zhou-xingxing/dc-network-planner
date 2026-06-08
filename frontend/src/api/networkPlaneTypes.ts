import request from './request'
import type {
  EntityId,
  ListQueryParams,
  MessageResponse,
  NetworkPlaneType,
  NetworkPlaneTypeCreatePayload,
  NetworkPlaneTypeUpdatePayload,
  PaginatedResponse,
} from '@/types'

export function fetchPlaneTypes(params?: ListQueryParams): Promise<PaginatedResponse<NetworkPlaneType>> {
  return request.get<PaginatedResponse<NetworkPlaneType>, PaginatedResponse<NetworkPlaneType>>(
    '/network-plane-types',
    { params }
  )
}

export function getPlaneType(id: EntityId): Promise<NetworkPlaneType> {
  return request.get<NetworkPlaneType, NetworkPlaneType>(`/network-plane-types/${id}`)
}

export function createPlaneType(data: NetworkPlaneTypeCreatePayload): Promise<NetworkPlaneType> {
  return request.post<NetworkPlaneType, NetworkPlaneType>('/network-plane-types', data)
}

export function updatePlaneType(id: EntityId, data: NetworkPlaneTypeUpdatePayload): Promise<NetworkPlaneType> {
  return request.put<NetworkPlaneType, NetworkPlaneType>(`/network-plane-types/${id}`, data)
}

export function deletePlaneType(id: EntityId): Promise<MessageResponse> {
  return request.delete<MessageResponse, MessageResponse>(`/network-plane-types/${id}`)
}
