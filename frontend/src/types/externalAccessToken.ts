import type { DateTimeString, EntityId } from './common'

export interface ExternalAccessToken {
  id: EntityId
  username: string
  owner_is_active: boolean
  created_at: DateTimeString
  expires_at: DateTimeString
}
