import request from './request'
import type { LookupResponse } from '@/types'

export function lookupIP(q: string, exact = true): Promise<LookupResponse> {
  return request.get<LookupResponse, LookupResponse>('/lookup', { params: { q, exact } })
}
