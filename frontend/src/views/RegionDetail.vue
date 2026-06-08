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
        <el-form-item label="CIDR" prop="cidr">
          <el-input v-model="planeForm.cidr" placeholder="例如: 10.0.0.0/22" maxlength="43" clearable />
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
            maxlength="39"
            clearable
            @focus="fillRecommendedGatewayIp"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="planeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPlaneForm" :loading="planeSubmitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getRegion, createRegionPlane, updateRegionPlane, deleteRegionPlane } from '@/api/regions'
import { fetchPlaneTypes } from '@/api/networkPlaneTypes'
import { useAppStore } from '@/stores/app'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { ArrowLeft, Edit, Delete, Connection, InfoFilled, Plus } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/time'
import { buildPlaneTypeTree } from '@/utils/tree'
import type {
  EntityId,
  NetworkPlaneType,
  RegionDetail as RegionDetailData,
  RegionPlane,
  RegionPlaneCreatePayload,
  RegionPlaneUpdatePayload,
} from '@/types'

interface PlaneForm {
  plane_type_id: EntityId | ''
  scope: string
  cidr: string
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

// ---- 计算属性 ----
const planeTree = computed(() => region.value.planes || [])
const planeTypeTree = computed(() => buildPlaneTypeTree(availablePlaneTypes.value))
const canManageBusiness = computed(() => appStore.canManageRegionBusiness(props.id))

const desContentStyle = { color: 'var(--color-text-primary)', fontSize: '13px' }
const planeRules = {
  plane_type_id: [{ required: true, message: '请选择网络平面类型', trigger: 'change' }],
  cidr: [{ required: true, message: '请输入 CIDR', trigger: 'blur' }],
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
    cidr: '',
    vlan_id: '',
    gateway_position: '',
    gateway_ip: '',
  }
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
  isEditPlane.value = true
  editingPlaneId.value = row.id
  planeForm.value = {
    plane_type_id: row.plane_type_id,
    scope: row.scope || 'Global',
    cidr: row.cidr || '',
    vlan_id: row.vlan_id ? String(row.vlan_id) : '',
    gateway_position: row.gateway_position || '',
    gateway_ip: row.gateway_ip || '',
  }
  planeDialogVisible.value = true
  await nextTick()
  planeFormRef.value?.clearValidate()
}

function resetPlaneForm() {
  planeForm.value = createEmptyPlaneForm()
  isEditPlane.value = false
  editingPlaneId.value = ''
  planeSubmitting.value = false
  planeFormRef.value?.clearValidate()
}

async function submitPlaneForm() {
  const valid = await planeFormRef.value?.validate().catch(() => false)
  if (!valid) return
  planeSubmitting.value = true
  try {
    const payload: RegionPlaneUpdatePayload = {
      scope: planeForm.value.scope || 'Global',
      cidr: planeForm.value.cidr,
      vlan_id: planeForm.value.vlan_id ? Number(planeForm.value.vlan_id) : null,
      gateway_position: planeForm.value.gateway_position || null,
      gateway_ip: planeForm.value.gateway_ip || null,
    }
    const createPayload: RegionPlaneCreatePayload = {
      ...payload,
      plane_type_id: planeForm.value.plane_type_id,
      cidr: planeForm.value.cidr,
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
  } catch (e) {
    // Error handled by Axios interceptor
  } finally {
    planeSubmitting.value = false
  }
}

function fillRecommendedGatewayIp() {
  if (planeForm.value.gateway_ip || !planeForm.value.cidr || !planeForm.value.plane_type_id) return
  const planeType = availablePlaneTypes.value.find(pt => pt.id === planeForm.value.plane_type_id)
  const recommended = recommendedGatewayIp(planeForm.value.cidr, Boolean(planeType?.is_private))
  if (recommended) {
    planeForm.value.gateway_ip = recommended
  }
}

function recommendedGatewayIp(cidr: string, isPrivate: boolean) {
  const [ip, prefixText] = cidr.trim().split('/')
  const prefix = Number(prefixText)
  if (!isValidIpv4(ip) || !Number.isInteger(prefix) || prefix < 0 || prefix > 32) return ''
  const base = ipv4ToNumber(ip)
  const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0
  const network = base & mask
  const broadcast = (network | (~mask >>> 0)) >>> 0
  if (network === broadcast) return numberToIpv4(network)
  if (isPrivate) {
    return numberToIpv4(prefix < 31 ? network + 1 : network)
  }
  return numberToIpv4(prefix < 31 ? broadcast - 1 : broadcast)
}

function isValidIpv4(ip: string) {
  const parts = ip.split('.')
  return parts.length === 4 && parts.every(part => {
    if (!/^\d+$/.test(part)) return false
    const value = Number(part)
    return value >= 0 && value <= 255
  })
}

function ipv4ToNumber(ip: string) {
  return ip.split('.').reduce((acc: number, part: string) => ((acc << 8) + Number(part)) >>> 0, 0)
}

function numberToIpv4(value: number) {
  return [24, 16, 8, 0].map((shift: number) => (value >>> shift) & 255).join('.')
}

async function deletePlane(planeId: EntityId) {
  try {
    await deleteRegionPlane(props.id, planeId)
    ElMessage.success('网络平面已删除')
    await fetchRegion()
    await fetchPlanes()
  } catch (e) { /* handled */ }
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
