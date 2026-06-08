import request from './request'
import type {
  EntityId,
  ListQueryParams,
  MessageResponse,
  PaginatedResponse,
  User,
  UserCreatePayload,
  UserUpdatePayload,
} from '@/types'

export function fetchUsers(params?: ListQueryParams): Promise<PaginatedResponse<User>> {
  return request.get<PaginatedResponse<User>, PaginatedResponse<User>>('/users', { params })
}

export function createUser(data: UserCreatePayload): Promise<User> {
  return request.post<User, User>('/users', data)
}

export function updateUser(id: EntityId, data: UserUpdatePayload): Promise<User> {
  return request.put<User, User>(`/users/${id}`, data)
}

export function resetUserPassword(id: EntityId, password: string): Promise<MessageResponse> {
  return request.post<MessageResponse, MessageResponse>(`/users/${id}/reset-password`, { password })
}

export function deleteUser(id: EntityId): Promise<MessageResponse> {
  return request.delete<MessageResponse, MessageResponse>(`/users/${id}`)
}
