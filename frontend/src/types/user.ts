import type { DateTimeString, EntityId } from "./common"

export type UserRole = "administrator" | "user"

export interface PermittedRegion {
  id: EntityId
  name: string
}

export interface User {
  id: EntityId
  username: string
  role: UserRole
  is_active: boolean
  permitted_regions: PermittedRegion[]
  created_at: DateTimeString
  updated_at: DateTimeString
}

export interface CurrentUser {
  id: EntityId
  username: string
  role: UserRole
  is_active: boolean
  permitted_regions: PermittedRegion[]
  permissions: string[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: CurrentUser
}

export interface UserCreatePayload {
  username: string
  password: string
  role?: UserRole
  is_active?: boolean
  permitted_region_ids?: EntityId[]
}

export interface UserUpdatePayload {
  role?: UserRole
  is_active?: boolean
  permitted_region_ids?: EntityId[]
}
