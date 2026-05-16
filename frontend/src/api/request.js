import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

const ERROR_MESSAGE_OPTIONS = {
  duration: 8000,
  showClose: true,
}

function showErrorMessage(message) {
  // 报错信息通常比成功提示更长，给用户留足阅读和手动关闭时间。
  ElMessage.error({
    message,
    ...ERROR_MESSAGE_OPTIONS,
  })
}

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
        showErrorMessage(error.response?.data?.detail || '用户名或密码错误')
        return Promise.reject(error)
      }
      appStore.logout()
      if (window.location.pathname !== '/login') {
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?redirect=${redirect}`
      }
      showErrorMessage('登录已失效，请重新登录')
      return Promise.reject(error)
    }
    if (error.response?.status === 403) {
      showErrorMessage(error.response?.data?.detail || '无权限执行该操作')
      return Promise.reject(error)
    }
    const msg = error.response?.data?.detail || error.message || '网络错误'
    showErrorMessage(msg)
    return Promise.reject(error)
  }
)

export default request
