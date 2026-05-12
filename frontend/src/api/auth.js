import request from './request'

export function login(username, password) {
  return request.post('/auth/login', { username, password })
}

export function fetchCurrentUser() {
  return request.get('/auth/me')
}

export function changeMyPassword(currentPassword, newPassword) {
  return request.put('/auth/password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
