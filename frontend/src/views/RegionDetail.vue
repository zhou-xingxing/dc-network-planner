<template>
  <div v-loading="loading">
    <div class="page-heading">
      <div>
        <el-button size="small" text @click="$router.push('/regions')" :icon="ArrowLeft" style="margin-bottom: 8px">返回 Region 列表</el-button>
        <h2 class="page-title">{{ region.name }}</h2>
        <p class="page-desc">Region 详情与网络平面管理</p>
      </div>
      <div v-if="appStore.isAdministrator" class="header-actions">
        <el-button size="small" plain @click="editRegion">
          <el-icon><Edit /></el-icon>编辑
        </el-button>
        <el-button size="small" plain type="danger" @click="deleteRegion">
          <el-icon><Delete /></el-icon>删除
        </el-button>
      </div>
    </div>

    <!-- Region Info -->
    <el-card shadow="never" class="region-info">
      <template #header>
        <div class="card-header">
          <span class="card-title">基本信息</span>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="描述" :content-style="desContentStyle">{{ region.description || '无' }}</el-descriptions-item>
        <el-descriptions-item label="网络平面数" :content-style="desContentStyle">{{ region.plane_count }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :content-style="desContentStyle">{{ formatDateTime(region.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间" :content-style="desContentStyle">{{ formatDateTime(region.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 网络平面列表 -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">Region 网络平面</span>
          <div v-if="canManageBusiness" class="header-actions" style="gap: 8px">
            <el-button size="small" type="primary" :icon="Plus" @click="showPlaneDialog">添加</el-button>
          </div>
        </div>
      </template>
      <el-table
        v-if="planeTree.length > 0"
        :data="planeTree"
        row-key="id"
        default-expand-all
        :tree-props="{ children: 'children' }"
        stripe
        border
        empty-text="尚未配置任何网络平面"
        table-layout="auto"
        :fit="false"
        scrollbar-always-on
        show-overflow-tooltip
      >
        <el-table-column prop="plane_type_name" label="网络平面" min-width="180" class-name="plane-name-column">
          <template #default="{ row }">
            <span class="plane-name-cell">
              <el-icon><Connection /></el-icon>
              <span>{{ row.plane_type_name }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="scope" label="作用域" min-width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.scope || 'Global' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cidr" label="CIDR" min-width="160">
          <template #default="{ row }">
            <span class="plane-address-text">{{ row.cidr }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="gateway_ip" label="网关IP" min-width="140">
          <template #default="{ row }">
            <span class="plane-address-text">{{ row.gateway_ip || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="vlan_id" label="VLAN" width="110" align="center">
          <template #default="{ row }">
            <span>{{ row.vlan_id || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="gateway_position" label="网关位置" min-width="160">
          <template #default="{ row }">{{ row.gateway_position || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column v-if="canManageBusiness" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="warning" link @click="showEditPlaneDialog(row)">
              <el-icon style="margin-right: 3px"><Edit /></el-icon>编辑
            </el-button>
            <el-popconfirm
              title="确定删除此平面？若存在子平面，请先删除子平面"
              @confirm="deletePlane(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" link>
                  <el-icon style="margin-right: 3px"><Delete /></el-icon>删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="尚未配置任何网络平面" :image-size="80" />
    </el-card>

    <el-dialog
      v-model="planeDialogVisible"
      :title="isEditPlane ? '编辑 Region 网络平面' : '添加 Region 网络平面'"
      width="560px"
      :close-on-click-modal="false"
      @closed="resetPlaneForm"
    >
      <el-form ref="planeFormRef" :model="planeForm" :rules="planeRules" label-width="110px">
        <el-form-item label="网络平面类型" prop="plane_type_id">
          <el-tree-select
            v-model="planeForm.plane_type_id"
            :data="planeTypeTree"
            node-key="id"
            value-key="id"
            :props="{ label: 'name', children: 'children' }"
            placeholder="选择网络平面类型"
            clearable
            check-strictly
            default-expand-all
            :render-after-expand="false"
            :disabled="isEditPlane"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="作用域" prop="scope">
          <div class="scope-input-wrap form-scope-input">
            <el-input v-model="planeForm.scope" placeholder="Global" maxlength="100" clearable />
            <el-tooltip
              content="未填写时保存为 Global；同一 Region 内，同一网络平面类型只能有一个 Global 作用域实例。"
              placement="top"
            >
              <el-icon class="scope-tip-icon"><InfoFilled /></el-icon>
            </el-tooltip>
          </div>
        </el-form-item>
        <el-form-item
          v-if="planeForm.plane_type_id"
          label="父平面实例"
          class="parent-context-form-item"
        >
          <div
            class="parent-context-card"
            :class="{
              'is-success': parentPlaneContext?.status === 'found',
              'is-danger': parentPlaneContext?.status === 'missing' || parentPlaneContextError,
              'is-info': parentPlaneContext?.status === 'root',
            }"
          >
            <div v-if="parentPlaneContextLoading" class="parent-context-state">
              <el-icon class="is-loading"><Loading /></el-icon>
              <div>
                <strong>正在查找父平面实例</strong>
                <span>按当前网络平面类型和作用域进行匹配</span>
              </div>
            </div>
            <div v-else-if="parentPlaneContextError" class="parent-context-state">
              <el-icon><WarningFilled /></el-icon>
              <div>
                <strong>父平面信息查询失败</strong>
                <span>{{ parentPlaneContextError }}</span>
              </div>
              <el-button type="danger" link @click="scheduleParentPlaneContextLookup(0)">重试</el-button>
            </div>
            <div v-else-if="parentPlaneContext?.status === 'root'" class="parent-context-state">
              <el-icon><InfoFilled /></el-icon>
              <div>
                <strong>根级网络平面</strong>
                <span>该网络平面类型无需父平面实例，可直接配置 CIDR。</span>
              </div>
            </div>
            <div v-else-if="parentPlaneContext?.status === 'missing'" class="parent-context-state">
              <el-icon><WarningFilled /></el-icon>
              <div>
                <strong>未找到父平面实例</strong>
                <span>
                  当前 Region 中不存在作用域为 {{ parentPlaneLookupScopeText }} 的
                  “{{ parentPlaneContext.parent_type_name }}”实例。
                </span>
              </div>
            </div>
            <template v-else-if="parentPlaneContext?.status === 'found' && parentPlaneContext.parent_plane">
              <div class="parent-context-heading">
                <div class="parent-context-title">
                  <el-icon><CircleCheckFilled /></el-icon>
                  <strong>已匹配父平面实例</strong>
                </div>
                <el-tag v-if="parentPlaneUsesGlobalFallback" size="small" type="warning" effect="plain">
                  Global 兜底
                </el-tag>
              </div>
              <div class="parent-context-details">
                <span>父平面类型</span>
                <strong>{{ parentPlaneContext.parent_type_name }}</strong>
                <span>实际作用域</span>
                <strong>{{ parentPlaneContext.parent_plane.scope }}</strong>
                <span>CIDR</span>
                <strong class="plane-address-text">{{ parentPlaneContext.parent_plane.cidr }}</strong>
                <span>VLAN</span>
                <strong>{{ parentPlaneContext.parent_plane.vlan_id ?? '未配置' }}</strong>
                <span>网关位置</span>
                <strong>{{ parentPlaneContext.parent_plane.gateway_position || '未配置' }}</strong>
                <span>网关 IP</span>
                <strong class="plane-address-text">{{ parentPlaneContext.parent_plane.gateway_ip || '未配置' }}</strong>
              </div>
            </template>
          </div>
        </el-form-item>
        <el-form-item label="CIDR" prop="network_address" class="cidr-form-item">
          <div class="cidr-input-group" :class="{ 'has-recommendation-action': !isEditPlane }">
            <el-input
              v-model="planeForm.network_address"
              class="cidr-address-input"
              placeholder="例如: 10.0.0.0"
              maxlength="45"
              clearable
              aria-label="网络地址"
            />
            <span class="cidr-separator" aria-hidden="true">/</span>
            <el-input
              v-model="planeForm.prefix_length"
              class="cidr-prefix-input"
              placeholder="例如：24"
              maxlength="3"
              clearable
              inputmode="numeric"
              aria-label="子网掩码位数"
              @blur="validateCidrField"
            />
            <el-tooltip
              v-if="!isEditPlane"
              :disabled="!cidrRecommendationDisabledReason"
              :content="cidrRecommendationDisabledReason"
              placement="top"
            >
              <span class="cidr-recommendation-action">
                <el-button
                  type="primary"
                  plain
                  :disabled="Boolean(cidrRecommendationDisabledReason)"
                  :loading="cidrRecommendationLoading"
                  @click="fillRecommendedCidr"
                >
                  自动分配
                </el-button>
              </span>
            </el-tooltip>
          </div>
        </el-form-item>
        <el-form-item label="VLAN" prop="vlan_id">
          <el-input v-model="planeForm.vlan_id" placeholder="可选" maxlength="4" clearable />
        </el-form-item>
        <el-form-item label="网关位置" prop="gateway_position">
          <el-input v-model="planeForm.gateway_position" placeholder="可选，例如: Core-A" maxlength="255" clearable />
        </el-form-item>
        <el-form-item label="网关IP" prop="gateway_ip">
          <el-input
            v-model="planeForm.gateway_ip"
            placeholder="可选，聚焦时按 CIDR 自动推荐"
            maxlength="45"
            clearable
            @focus="fillRecommendedGatewayIp"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planeDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="parentPlaneContextSubmitBlocked"
          :loading="planeSubmitting"
          @click="submitPlaneForm"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getRegion,
  fetchParentPlaneContext,
  recommendRegionPlaneCidr,
  createRegionPlane,
  updateRegionPlane,
  deleteRegionPlane,
} from '@/api/regions'
import { fetchPlaneTypes } from '@/api/networkPlaneTypes'
import { useAppStore } from '@/stores/app'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import {
  ArrowLeft,
  CircleCheckFilled,
  Connection,
  Delete,
  Edit,
  InfoFilled,
  Loading,
  Plus,
  WarningFilled,
} from '@element-plus/icons-vue'
import { analyzeCidr, getIpVersion, recommendedGatewayIp } from '@/utils/ip'
import { formatDateTime } from '@/utils/time'
import { buildPlaneTypeTree } from '@/utils/tree'
import type {
  EntityId,
  NetworkPlaneType,
  ParentPlaneContext,
  RegionDetail as RegionDetailData,
  RegionPlane,
  RegionPlaneCreatePayload,
  RegionPlaneUpdatePayload,
} from '@/types'

interface PlaneForm {
  plane_type_id: EntityId | ''
  scope: string
  network_address: string
  prefix_length: string
  vlan_id: string
  gateway_position: string
  gateway_ip: string
}

function createEmptyRegion(): RegionDetailData {
  return {
    id: '',
    name: '',
    description: '',
    plane_count: 0,
    created_at: '',
    updated_at: '',
    planes: [],
  }
}

const props = defineProps<{ id: EntityId }>()
const router = useRouter()
const appStore = useAppStore()

const loading = ref(false)
const region = ref<RegionDetailData>(createEmptyRegion())

// ---- 平面相关状态 ----
const availablePlaneTypes = ref<NetworkPlaneType[]>([])
const planeDialogVisible = ref(false)
const planeSubmitting = ref(false)
const planeFormRef = ref<FormInstance>()
const planeForm = ref(createEmptyPlaneForm())
const isEditPlane = ref(false)
const editingPlaneId = ref<EntityId | ''>('')
const parentPlaneContext = ref<ParentPlaneContext | null>(null)
const parentPlaneContextLoading = ref(false)
const parentPlaneContextError = ref('')
const cidrRecommendationLoading = ref(false)
let cidrRecommendationRequestId = 0
let cancelActiveParentPlaneContextLookup: (() => void) | undefined

// ---- 计算属性 ----
const planeTree = computed(() => region.value.planes || [])
const planeTypeTree = computed(() => buildPlaneTypeTree(availablePlaneTypes.value))
const canManageBusiness = computed(() => appStore.canManageRegionBusiness(props.id))
const parentPlaneContextSubmitBlocked = computed(() => {
  if (!planeForm.value.plane_type_id) return false
  return (
    parentPlaneContextLoading.value
    || Boolean(parentPlaneContextError.value)
    || !parentPlaneContext.value
    || parentPlaneContext.value.status === 'missing'
  )
})
const parentPlaneUsesGlobalFallback = computed(() => {
  const context = parentPlaneContext.value
  return (
    context?.status === 'found'
    && context.requested_scope !== 'Global'
    && context.parent_plane?.scope === 'Global'
  )
})
const parentPlaneLookupScopeText = computed(() => {
  const scope = parentPlaneContext.value?.requested_scope
  if (!scope) return ''
  return scope === 'Global' ? 'Global' : `${scope} 或 Global`
})
const cidrRecommendationDisabledReason = computed(() => {
  if (!planeForm.value.plane_type_id) return '请先选择网络平面类型'
  if (parentPlaneContextLoading.value) return '正在查询父平面实例'
  if (parentPlaneContextError.value) return '父平面信息查询失败，请先重试'

  const context = parentPlaneContext.value
  if (!context) return '请先确认父平面实例'
  if (context.status === 'root') return '根网络平面没有父平面，无法自动分配'
  if (context.status === 'missing' || !context.parent_plane) return '请先创建有效的父平面实例'

  const prefixText = planeForm.value.prefix_length.trim()
  if (!prefixText) return '请先填写子网掩码位数'
  if (!/^\d+$/.test(prefixText)) return '子网掩码位数必须是整数'

  const prefix = Number(prefixText)
  const { networkAddress: parentAddress, prefixLength: parentPrefixText } = splitCidr(
    context.parent_plane.cidr
  )
  const parentIpVersion = getIpVersion(parentAddress)
  const maxPrefix = parentIpVersion === 4 ? 32 : 128
  if (!parentIpVersion || prefix > maxPrefix) {
    return `${parentIpVersion === 4 ? 'IPv4' : 'IPv6'} 子网掩码位数范围为 0-${maxPrefix}`
  }
  if (prefix < Number(parentPrefixText)) {
    return `子网掩码位数不能小于父平面的 /${parentPrefixText}`
  }
  return ''
})

const desContentStyle = { color: 'var(--color-text-primary)', fontSize: '13px' }
const planeRules = {
  plane_type_id: [{ required: true, message: '请选择网络平面类型', trigger: 'change' }],
  network_address: [{ validator: validateCidrInput, trigger: 'blur' }],
  vlan_id: [{ validator: validateOptionalVlanId, trigger: 'blur' }],
}

async function fetchRegion() {
  region.value = await getRegion(props.id)
}

async function fetchPlanes() {
  const res = await fetchPlaneTypes({ skip: 0, limit: 500 })
  availablePlaneTypes.value = res.items || []
}

// ---------- 平面操作 ----------

function createEmptyPlaneForm(): PlaneForm {
  return {
    plane_type_id: '',
    scope: 'Global',
    network_address: '',
    prefix_length: '',
    vlan_id: '',
    gateway_position: '',
    gateway_ip: '',
  }
}

function normalizePlaneScope(scope: string) {
  return scope.trim() || 'Global'
}

function clearParentPlaneContextLookup() {
  cancelActiveParentPlaneContextLookup?.()
  cancelActiveParentPlaneContextLookup = undefined
  parentPlaneContext.value = null
  parentPlaneContextLoading.value = false
  parentPlaneContextError.value = ''
}

function scheduleParentPlaneContextLookup(delay = 300) {
  clearParentPlaneContextLookup()
  if (!planeDialogVisible.value || !planeForm.value.plane_type_id) return

  const planeTypeId = planeForm.value.plane_type_id
  const scope = normalizePlaneScope(planeForm.value.scope)
  let active = true
  parentPlaneContextLoading.value = true
  const timer = setTimeout(() => {
    void loadParentPlaneContext()
  }, delay)
  cancelActiveParentPlaneContextLookup = () => {
    active = false
    clearTimeout(timer)
  }

  async function loadParentPlaneContext() {
    try {
      const context = await fetchParentPlaneContext(props.id, planeTypeId, scope)
      if (active) parentPlaneContext.value = context
    } catch {
      if (active) {
        parentPlaneContextError.value = '请检查网络连接后重试，或重新选择网络平面类型和作用域。'
      }
    } finally {
      if (active) {
        parentPlaneContextLoading.value = false
        cancelActiveParentPlaneContextLookup = undefined
      }
    }
  }
}

watch(
  () => [
    planeDialogVisible.value,
    isEditPlane.value,
    planeForm.value.plane_type_id,
    planeForm.value.scope,
  ],
  () => scheduleParentPlaneContextLookup(),
)

function validateCidrInput(_rule: unknown, _value: string, callback: (error?: Error) => void) {
  const address = planeForm.value.network_address.trim()
  const prefixText = planeForm.value.prefix_length.trim()
  if (!address) {
    callback(new Error('请输入网络地址'))
    return
  }
  const ipVersion = getIpVersion(address)
  if (!ipVersion) {
    callback(new Error('请输入有效的 IPv4 或 IPv6 地址'))
    return
  }
  if (!prefixText) {
    callback(new Error('请输入子网掩码位数'))
    return
  }
  if (!/^\d+$/.test(prefixText)) {
    callback(new Error('子网掩码位数必须是整数'))
    return
  }
  const prefix = Number(prefixText)
  const maxPrefix = ipVersion === 4 ? 32 : 128
  if (prefix < 0 || prefix > maxPrefix) {
    callback(new Error(`${ipVersion === 4 ? 'IPv4' : 'IPv6'} 子网掩码位数范围为 0-${maxPrefix}`))
    return
  }
  const analysis = analyzeCidr(`${address}/${prefix}`)
  if (analysis?.usesHostAddress) {
    callback(
      new Error(`CIDR 必须使用网段的网络地址，当前输入 ${address}/${prefix}，建议使用 ${analysis.networkCidr}`)
    )
    return
  }
  callback()
}

function validateCidrField() {
  void planeFormRef.value?.validateField('network_address').catch(() => false)
}

function validateOptionalVlanId(_rule: unknown, value: string, callback: (error?: Error) => void) {
  if (!value) {
    callback()
    return
  }
  if (!/^\d+$/.test(value)) {
    callback(new Error('VLAN 必须是数字'))
    return
  }
  const vlanId = Number(value)
  if (vlanId < 1 || vlanId > 4094) {
    callback(new Error('VLAN 范围为 1-4094'))
    return
  }
  callback()
}

async function showPlaneDialog() {
  resetPlaneForm()
  planeDialogVisible.value = true
  await nextTick()
  planeFormRef.value?.clearValidate()
}

async function showEditPlaneDialog(row: RegionPlane) {
  const { networkAddress, prefixLength } = splitCidr(row.cidr || '')
  isEditPlane.value = true
  editingPlaneId.value = row.id
  planeForm.value = {
    plane_type_id: row.plane_type_id,
    scope: row.scope || 'Global',
    network_address: networkAddress,
    prefix_length: prefixLength,
    vlan_id: row.vlan_id ? String(row.vlan_id) : '',
    gateway_position: row.gateway_position || '',
    gateway_ip: row.gateway_ip || '',
  }
  planeDialogVisible.value = true
  await nextTick()
  planeFormRef.value?.clearValidate()
}

function resetPlaneForm() {
  clearParentPlaneContextLookup()
  cidrRecommendationRequestId += 1
  cidrRecommendationLoading.value = false
  planeForm.value = createEmptyPlaneForm()
  isEditPlane.value = false
  editingPlaneId.value = ''
  planeSubmitting.value = false
  planeFormRef.value?.clearValidate()
}

async function fillRecommendedCidr() {
  if (cidrRecommendationDisabledReason.value || !planeForm.value.plane_type_id) return

  const planeTypeId = planeForm.value.plane_type_id
  const scope = normalizePlaneScope(planeForm.value.scope)
  const prefixLength = Number(planeForm.value.prefix_length.trim())
  const requestId = ++cidrRecommendationRequestId
  cidrRecommendationLoading.value = true
  try {
    const recommendation = await recommendRegionPlaneCidr(
      props.id,
      planeTypeId,
      scope,
      prefixLength
    )
    if (
      requestId !== cidrRecommendationRequestId
      || isEditPlane.value
      || planeForm.value.plane_type_id !== planeTypeId
      || normalizePlaneScope(planeForm.value.scope) !== scope
      || Number(planeForm.value.prefix_length.trim()) !== prefixLength
    ) return

    const { networkAddress, prefixLength: recommendedPrefix } = splitCidr(recommendation.cidr)
    planeForm.value.network_address = networkAddress
    planeForm.value.prefix_length = recommendedPrefix
    await nextTick()
    planeFormRef.value?.clearValidate('network_address')
    ElMessage.success(`已自动分配 ${recommendation.cidr}`)
  } catch {
    // Error handled by Axios interceptor
  } finally {
    if (requestId === cidrRecommendationRequestId) {
      cidrRecommendationLoading.value = false
    }
  }
}

async function submitPlaneForm() {
  if (parentPlaneContextSubmitBlocked.value) {
    ElMessage.warning('请先确认当前网络平面类型和作用域存在有效的父平面实例')
    return
  }
  const valid = await planeFormRef.value?.validate().catch(() => false)
  if (!valid) return
  planeSubmitting.value = true
  try {
    const cidr = buildCidr()
    const payload: RegionPlaneUpdatePayload = {
      scope: normalizePlaneScope(planeForm.value.scope),
      cidr,
      vlan_id: planeForm.value.vlan_id ? Number(planeForm.value.vlan_id) : null,
      gateway_position: planeForm.value.gateway_position || null,
      gateway_ip: planeForm.value.gateway_ip || null,
    }
    const createPayload: RegionPlaneCreatePayload = {
      ...payload,
      plane_type_id: planeForm.value.plane_type_id,
      cidr,
    }
    const result = isEditPlane.value
      ? await updateRegionPlane(props.id, editingPlaneId.value, payload)
      : await createRegionPlane(props.id, createPayload)
    ElMessage.success(isEditPlane.value ? '网络平面已更新' : '网络平面已添加')
    if (result.gateway_ip_warning) {
      ElMessage.warning(result.gateway_ip_warning)
    }
    planeDialogVisible.value = false
    await fetchRegion()
    await fetchPlanes()
  } catch {
    // Error handled by Axios interceptor
  } finally {
    planeSubmitting.value = false
  }
}

function fillRecommendedGatewayIp() {
  if (
    planeForm.value.gateway_ip
    || !planeForm.value.network_address
    || !planeForm.value.prefix_length
    || !planeForm.value.plane_type_id
  ) return
  const planeType = availablePlaneTypes.value.find(pt => pt.id === planeForm.value.plane_type_id)
  const recommended = recommendedGatewayIp(buildCidr(), Boolean(planeType?.is_private))
  if (recommended) {
    planeForm.value.gateway_ip = recommended
  }
}

function buildCidr() {
  return `${planeForm.value.network_address.trim()}/${planeForm.value.prefix_length.trim()}`
}

function splitCidr(cidr: string) {
  const separatorIndex = cidr.lastIndexOf('/')
  if (separatorIndex <= 0) {
    return { networkAddress: cidr, prefixLength: '' }
  }
  return {
    networkAddress: cidr.slice(0, separatorIndex),
    prefixLength: cidr.slice(separatorIndex + 1),
  }
}

async function deletePlane(planeId: EntityId) {
  try {
    await deleteRegionPlane(props.id, planeId)
    ElMessage.success('网络平面已删除')
    await fetchRegion()
    await fetchPlanes()
  } catch { /* handled */ }
}

// ---------- Region 操作 ----------

function editRegion() {
  ElMessageBox.prompt('Region 名称', '编辑 Region', { inputValue: region.value.name, inputPattern: /.+/, inputErrorMessage: '名称不能为空' })
    .then(async ({ value }: { value: string }) => {
      const { updateRegion: updateRegionApi } = await import('@/api/regions')
      await updateRegionApi(props.id, { name: value })
      ElMessage.success('更新成功')
      await fetchRegion()
    }).catch(() => {})
}

async function deleteRegion() {
  try {
    await ElMessageBox.confirm('确定删除该 Region？所有相关数据将被删除', '警告', { type: 'warning' })
    const { deleteRegion: deleteRegionApi } = await import('@/api/regions')
    await deleteRegionApi(props.id)
    ElMessage.success('删除成功')
    router.push('/regions')
  } catch (e) {
    if (e !== 'cancel') throw e
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchRegion()
    await fetchPlanes()
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(clearParentPlaneContextLookup)
</script>

<style scoped>
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--spacing-lg);
}
.page-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 4px 0 0; }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin-top: 4px; }
.header-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.region-info { margin-bottom: var(--spacing-md); }
.section-card { margin-bottom: var(--spacing-md); }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--color-text-primary);
  position: relative;
  padding-left: 12px;
}
.card-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 2px;
  bottom: 2px;
  width: 3px;
  background: var(--color-primary);
  border-radius: 2px;
}
.plane-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}
.plane-address-text { font-family: 'SF Mono', Menlo, Consolas, monospace; }
.cidr-input-group {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 24px 92px;
  align-items: center;
  width: 100%;
}
.cidr-input-group.has-recommendation-action {
  grid-template-columns: minmax(0, 1fr) 24px 92px auto;
}
.cidr-recommendation-action {
  display: inline-flex;
  margin-left: 8px;
}
:deep(.cidr-recommendation-action .el-button) {
  width: 88px;
}
:deep(.cidr-form-item .el-form-item__error) {
  position: static;
  width: 100%;
  padding-top: 4px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.cidr-separator {
  color: var(--color-text-secondary);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 17px;
  font-weight: 600;
  text-align: center;
}
:deep(.cidr-address-input .el-input__inner),
:deep(.cidr-prefix-input .el-input__inner) {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}
:deep(.cidr-prefix-input .el-input__inner) {
  text-align: center;
}
.scope-input-wrap {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.form-scope-input {
  width: 100%;
}
.scope-tip-icon {
  color: var(--color-text-tertiary);
  cursor: help;
  font-size: 15px;
}
.parent-context-card {
  box-sizing: border-box;
  width: 100%;
  min-height: 68px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color);
  border-left-width: 3px;
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
  color: var(--color-text-secondary);
}
.parent-context-card.is-success {
  border-color: var(--el-color-success-light-5);
  border-left-color: var(--el-color-success);
  background: var(--el-color-success-light-9);
}
.parent-context-card.is-danger {
  border-color: var(--el-color-danger-light-5);
  border-left-color: var(--el-color-danger);
  background: var(--el-color-danger-light-9);
}
.parent-context-card.is-info {
  border-color: var(--el-color-primary-light-7);
  border-left-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.parent-context-state,
.parent-context-heading,
.parent-context-title {
  display: flex;
  align-items: flex-start;
}
.parent-context-state {
  gap: 9px;
}
.parent-context-state > .el-icon,
.parent-context-title > .el-icon {
  flex: 0 0 auto;
  margin-top: 2px;
  font-size: 17px;
}
.parent-context-state > div {
  flex: 1;
  min-width: 0;
}
.parent-context-state strong,
.parent-context-state span {
  display: block;
  line-height: 1.5;
}
.parent-context-state strong,
.parent-context-title strong,
.parent-context-details strong {
  color: var(--color-text-primary);
}
.parent-context-state span {
  margin-top: 2px;
  color: var(--color-text-tertiary);
  font-size: 12px;
}
.parent-context-heading {
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.parent-context-title {
  gap: 7px;
}
.parent-context-title > .el-icon {
  color: var(--el-color-success);
}
.parent-context-details {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  row-gap: 5px;
  font-size: 12px;
  line-height: 1.5;
}
.parent-context-details > span {
  color: var(--color-text-tertiary);
}
.parent-context-details > strong {
  min-width: 0;
  overflow-wrap: anywhere;
  font-weight: 500;
}
.form-tip { display: block; color: var(--color-text-tertiary); font-size: 12px; margin-top: 4px; line-height: 1.4; }

:deep(.plane-name-column .cell) {
  display: flex;
  align-items: center;
  gap: 4px;
}

:deep(.plane-name-column .el-table__indent) {
  flex: 0 0 auto;
}

:deep(.plane-name-column .el-table__expand-icon),
:deep(.plane-name-column .el-table__placeholder) {
  flex: 0 0 20px;
}

</style>
