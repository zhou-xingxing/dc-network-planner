import type { EntityId, NetworkPlaneType, PlaneTypeTreeNode } from '@/types'

export function buildPlaneTypeTree(sourceItems: NetworkPlaneType[]): PlaneTypeTreeNode[] {
  const itemMap = new Map<EntityId, PlaneTypeTreeNode>()
  for (const item of sourceItems) {
    itemMap.set(item.id, { ...item, children: [], level: 1 })
  }

  const roots: PlaneTypeTreeNode[] = []
  for (const item of sourceItems) {
    const node = itemMap.get(item.id)
    if (!node) continue
    const parent = item.parent_id ? itemMap.get(item.parent_id) : null
    if (parent) {
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  }

  markTreeLevel(roots)
  return roots
}

function markTreeLevel(nodes: PlaneTypeTreeNode[], level = 1) {
  for (const node of nodes) {
    node.level = level
    markTreeLevel(node.children, level + 1)
  }
}
