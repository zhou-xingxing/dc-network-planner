import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

request.interceptors.request.use((config) => {
  const appStore = useAppStore()
  if (appStore.token) {
    config.headers.Authorization = `Bearer ${appStore.token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const appStore = useAppStore()
    if (error.response?.status === 401) {
      if (error.config?.url === '/auth/login') {
        ElMessage.error(error.response?.data?.detail || '用户名或密码错误')
        return Promise.reject(error)
      }
      appStore.logout()
      if (window.location.pathname !== '/login') {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?redirect=${redirect}`
      }
      ElMessage.error('登录已失效，请重新登录')
      return Promise.reject(error)
    }
    if (error.response?.status === 403) {
      ElMessage.error(error.response?.data?.detail || '无权限执行该操作')
      return Promise.reject(error)
    }
    const msg = error.response?.data?.detail || error.message || '网络错误'
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default request
