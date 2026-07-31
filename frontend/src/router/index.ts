import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import { fetchCurrentUser } from '@/api/auth'
import { useAppStore } from '@/stores/app'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean
    title?: string
    adminOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'regions',
        name: 'Regions',
        component: () => import('@/views/Regions.vue'),
        meta: { title: 'Region 管理' },
      },
      {
        path: 'regions/:id',
        name: 'RegionDetail',
        component: () => import('@/views/RegionDetail.vue'),
        props: true,
        meta: { title: 'Region 详情' },
      },
      {
        path: 'plane-types',
        name: 'PlaneTypes',
        component: () => import('@/views/PlaneTypes.vue'),
        meta: { title: '网络平面类型' },
      },
      {
        path: 'switch-cabling/racks',
        name: 'Racks',
        component: () => import('@/views/Racks.vue'),
        meta: { title: '机柜管理' },
      },
      {
        path: 'switch-cabling/racks/create',
        name: 'RackCreate',
        component: () => import('@/views/RackBulkCreate.vue'),
        meta: { title: '添加机柜' },
      },
      {
        path: 'switch-cabling/switches',
        name: 'Switches',
        component: () => import('@/views/Switches.vue'),
        meta: { title: '交换机管理' },
      },
      {
        path: 'lookup',
        name: 'Lookup',
        component: () => import('@/views/Lookup.vue'),
        meta: { title: 'IP 查找' },
      },
      {
        path: 'import-export',
        name: 'ImportExport',
        component: () => import('@/views/ImportExport.vue'),
        meta: { title: '导入 / 导出' },
      },
      {
        path: 'change-logs',
        name: 'ChangeLogs',
        component: () => import('@/views/ChangeLogs.vue'),
        meta: { title: '变更历史' },
      },
      {
        path: 'backup-config',
        name: 'BackupConfig',
        component: () => import('@/views/BackupConfig.vue'),
        meta: { title: '备份配置' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '个人主页' },
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/Users.vue'),
        meta: { title: '用户管理', adminOnly: true },
      },
      {
        path: 'external-access-tokens',
        name: 'ExternalAccessTokens',
        component: () => import('@/views/ExternalAccessTokens.vue'),
        meta: { title: '外部 API 访问令牌', adminOnly: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const appStore = useAppStore()
  if (to.meta.public) {
    if (to.path === '/login' && appStore.isAuthenticated) {
      const redirect = Array.isArray(to.query.redirect) ? to.query.redirect[0] : to.query.redirect
      return redirect || '/dashboard'
    }
    return true
  }
  if (!appStore.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (!appStore.currentUser) {
    try {
      const user = await fetchCurrentUser()
      appStore.setCurrentUser(user)
    } catch {
      appStore.logout()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
  if (to.meta.adminOnly && !appStore.isAdministrator) {
    return '/dashboard'
  }
  return true
})

export default router
