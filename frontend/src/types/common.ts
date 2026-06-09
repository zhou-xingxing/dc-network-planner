export type EntityId = string
export type DateTimeString = string

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

export interface MessageResponse {
  detail: string
}

export interface ListQueryParams {
  skip?: number
  limit?: number
}
