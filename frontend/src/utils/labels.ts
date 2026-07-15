export function entityTypeLabel(entityType: string) {
  const labels: Record<string, string> = {
    region: 'Region',
    network_plane_type: '网络平面类型',
    region_network_plane: 'Region 网络平面',
    external_access_token: '外部 API 访问令牌',
  }
  return labels[entityType] || entityType
}

export function actionTag(action: string) {
  const tags: Record<string, string> = {
    create: 'success',
    update: 'warning',
    delete: 'danger',
    import: 'primary',
  }
  return tags[action] || 'info'
}

export function actionLabel(action: string) {
  const labels: Record<string, string> = {
    create: '创建',
    update: '更新',
    delete: '删除',
    import: '导入',
  }
  return labels[action] || action
}
