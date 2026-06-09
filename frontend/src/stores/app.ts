import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { CurrentUser, EntityId } from '@/types'

function loadCurrentUser(): CurrentUser | null {
  const raw = localStorage.getItem('dc_network_planner_current_user')
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as CurrentUser
  } catch {
    localStorage.removeItem('dc_network_planner_current_user')
    return null
  }
}

export const useAppStore = defineStore('app', () => {
  const token = ref(localStorage.getItem('dc_network_planner_token') || '')
  const currentUser = ref<CurrentUser | null>(loadCurrentUser())
  const sidebarCollapsed = ref(false)
  const isAuthenticated = computed(() => Boolean(token.value))
  const isAdministrator = computed(() => currentUser.value?.role === 'administrator')
  const permittedRegionIds = computed(() =>
    new Set((currentUser.value?.permitted_regions || []).map((item) => item.id))
  )

  function setSession(accessToken: string, user: CurrentUser) {
    token.value = accessToken
    currentUser.value = user
    localStorage.setItem('dc_network_planner_token', accessToken)
    localStorage.setItem('dc_network_planner_current_user', JSON.stringify(user))
  }

  function setCurrentUser(user: CurrentUser) {
    currentUser.value = user
    localStorage.setItem('dc_network_planner_current_user', JSON.stringify(user))
  }

  function logout() {
    token.value = ''
    currentUser.value = null
    localStorage.removeItem('dc_network_planner_token')
    localStorage.removeItem('dc_network_planner_current_user')
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function canManageRegionBusiness(regionId: EntityId) {
    return currentUser.value?.role === 'user' && permittedRegionIds.value.has(regionId)
  }

  return {
    token,
    currentUser,
    sidebarCollapsed,
    isAuthenticated,
    isAdministrator,
    permittedRegionIds,
    setSession,
    setCurrentUser,
    logout,
    toggleSidebar,
    canManageRegionBusiness,
  }
})
