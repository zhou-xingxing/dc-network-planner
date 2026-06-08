import axios from 'axios'
import type { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { useAppStore } from '@/stores/app'

interface ApiErrorBody {
  detail?: unknown
}

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

const ERROR_MESSAGE_OPTIONS = {
  duration: 8000,
  showClose: true,
}

function showErrorMessage(message: string) {
  // 报错信息通常比成功提示更长，给用户留足阅读和手动关闭时间。
  ElMessage.error({
    message,
    ...ERROR_MESSAGE_OPTIONS,
  })
}

function getResponseDetail(data: unknown): string | undefined {
  if (!data || typeof data !== 'object') {
    return undefined
  }
  const detail = (data as ApiErrorBody).detail
  return typeof detail === 'string' && detail.trim() ? detail : undefined
}

function resolveErrorMessage(error: AxiosError<unknown>) {
  const detail = getResponseDetail(error.response?.data)
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  if (error.code === 'ECONNABORTED') {
    return '请求超时，请稍后重试'
  }
  if (!error.response) {
    return '网络连接异常，请检查网络后重试'
  }
  return '操作失败，请稍后重试'
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
  (error: AxiosError<unknown>) => {
    const appStore = useAppStore()
    if (error.response?.status === 401) {
      if (error.config?.url === '/auth/login') {
        showErrorMessage(getResponseDetail(error.response?.data) || '用户名或密码错误')
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
      showErrorMessage(getResponseDetail(error.response?.data) || '无权限执行该操作')
      return Promise.reject(error)
    }
    showErrorMessage(resolveErrorMessage(error))
    return Promise.reject(error)
  }
)

export default request
