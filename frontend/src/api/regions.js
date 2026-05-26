import request from './request'

export function fetchRegions(params) {
  return request.get('/regions', { params })
}

export function getRegion(id) {
  return request.get(`/regions/${id}`)
}

export function createRegion(data) {
  return request.post('/regions', data)
}

export function updateRegion(id, data) {
  return request.put(`/regions/${id}`, data)
}

export function deleteRegion(id) {
  return request.delete(`/regions/${id}`)
}

export function fetchRegionPlanes(regionId) {
  return request.get(`/regions/${regionId}/planes`)
}

export function createRegionPlane(regionId, data) {
  return request.post(`/regions/${regionId}/planes`, data)
}

export function updateRegionPlane(regionId, planeId, data) {
  return request.put(`/regions/${regionId}/planes/${planeId}`, data)
}

export function deleteRegionPlane(regionId, planeId) {
  return request.delete(`/regions/${regionId}/planes/${planeId}`)
}
