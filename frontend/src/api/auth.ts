import request from './request'
import type { CurrentUser, LoginResponse, MessageResponse } from '@/types'

export function login(username: string, password: string): Promise<LoginResponse> {
  return request.post<LoginResponse, LoginResponse>('/auth/login', { username, password })
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return request.get<CurrentUser, CurrentUser>('/auth/me')
}

export function changeMyPassword(currentPassword: string, newPassword: string): Promise<MessageResponse> {
  return request.put<MessageResponse, MessageResponse>('/auth/password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
