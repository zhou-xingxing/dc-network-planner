import request from './request'
import type { EntityId, ExternalAccessToken, ListQueryParams, PaginatedResponse } from '@/types'

export function fetchExternalAccessTokens(
  params?: ListQueryParams,
): Promise<PaginatedResponse<ExternalAccessToken>> {
  return request.get<PaginatedResponse<ExternalAccessToken>, PaginatedResponse<ExternalAccessToken>>(
    '/external-access-tokens',
    { params },
  )
}

export async function revokeExternalAccessToken(id: EntityId): Promise<void> {
  await request.delete(`/external-access-tokens/${id}`)
}
