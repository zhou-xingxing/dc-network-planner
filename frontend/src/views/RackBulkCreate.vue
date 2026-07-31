<template>
  <div v-loading="loading">
    <div class="page-heading">
      <div>
        <h2 class="page-title">添加机柜</h2>
        <p class="page-desc">按机房、机柜列和编号范围生成最终机柜名称，可一次创建一个或多个机柜</p>
      </div>
      <el-button :icon="Back" @click="backToRacks">返回机柜列表</el-button>
    </div>

    <el-alert
      v-if="!loading && manageableRegions.length === 0"
      class="permission-alert"
      type="info"
      :closable="false"
      show-icon
      title="当前账号没有可管理的 Region，无法添加机柜。"
    />

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-heading">
          <div>
            <strong>创建范围</strong>
            <span>本次生成的所有机柜使用同一个 Region 和总 U 数</span>
          </div>
        </div>
      </template>
      <div class="context-grid">
        <div class="field-block">
          <span class="field-label">Region</span>
          <el-select v-model="selectedRegionId" placeholder="请选择 Region" filterable>
            <el-option v-for="region in manageableRegions" :key="region.id" :label="region.name" :value="region.id" />
          </el-select>
        </div>
        <div class="field-block height-field">
          <span class="field-label">统一总 U 数</span>
          <div class="height-control">
            <el-input-number
              v-model="uHeight"
              class="height-input"
              :min="1"
              :step="1"
              controls-position="right"
            />
            <span>常见机柜为 42U 或 48U</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="card-heading rule-heading">
          <div>
            <strong>生成规则</strong>
            <span>机房名、机柜列和编号将作为结构化位置保存，最终名称由系统统一生成</span>
          </div>
          <el-button :icon="Plus" @click="addRule">添加一行</el-button>
        </div>
      </template>

      <el-table :data="generationRules" border empty-text="请添加生成规则">
        <el-table-column label="机房名" min-width="190">
          <template #default="{ row }">
            <el-input v-model="row.roomName" maxlength="100" placeholder="例如：A1-403" />
          </template>
        </el-table-column>
        <el-table-column label="机柜列" min-width="150">
          <template #default="{ row }">
            <el-input v-model="row.rackColumn" maxlength="30" placeholder="例如：A" />
          </template>
        </el-table-column>
        <el-table-column label="机柜编号范围" min-width="180">
          <template #default="{ row }">
            <el-input v-model="row.numberRange" maxlength="30" placeholder="例如：1-12" />
          </template>
        </el-table-column>
        <el-table-column label="生成预览" min-width="250">
          <template #default="{ row }">
            <span v-if="getRuleResult(row.id).error" class="rule-error">
              {{ getRuleResult(row.id).error }}
            </span>
            <div v-else class="rule-preview">
              <span>
                {{ getRuleResult(row.id).names[0] }}
                <template v-if="getRuleResult(row.id).names.length > 1">
                  ～ {{ getRuleResult(row.id).names.at(-1) }}
                </template>
              </span>
              <small>共 {{ getRuleResult(row.id).names.length }} 个</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button
              type="danger"
              link
              :icon="Delete"
              :disabled="generationRules.length === 1"
              @click="removeRule(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="preview-card">
      <template #header>
        <div class="card-heading preview-heading">
          <div>
            <strong>最终名称预览</strong>
            <span>请确认下列机柜位置及系统生成的最终名称</span>
          </div>
          <el-tag effect="plain" type="primary">共 {{ generationResult.names.length }} 个机柜</el-tag>
        </div>
      </template>

      <el-alert
        v-if="generationResult.error"
        class="preview-alert"
        type="error"
        :closable="false"
        show-icon
        :title="generationResult.error"
      />
      <el-empty
        v-else-if="generationResult.names.length === 0"
        :image-size="72"
        description="填写生成规则后，这里会显示最终机柜名称"
      />
      <el-scrollbar v-else max-height="360px">
        <div class="name-preview-grid">
          <div v-for="(name, index) in generationResult.names" :key="name" class="name-preview-item">
            <span class="name-index">{{ String(index + 1).padStart(2, '0') }}</span>
            <strong>{{ name }}</strong>
            <span>{{ uHeight }}U</span>
          </div>
        </div>
      </el-scrollbar>

      <div class="page-footer">
        <el-button :disabled="submitting" @click="backToRacks">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submitCreate">
          创建 {{ generationResult.names.length }} 个机柜
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Delete, Plus } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { createRacks } from '@/api/racks'
import { fetchRegions } from '@/api/regions'
import { useAppStore } from '@/stores/app'
import type { EntityId, RackCreateItemPayload, Region } from '@/types'

interface RackGenerationRule {
  id: number
  roomName: string
  rackColumn: string
  numberRange: string
}

interface RuleGenerationResult {
  names: string[]
  items: RackCreateItemPayload[]
  error: string
}

interface GenerationResult {
  names: string[]
  items: RackCreateItemPayload[]
  ruleResults: Map<number, RuleGenerationResult>
  error: string
}

const MAX_CREATE_RACKS = 500
const appStore = useAppStore()
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const regions = ref<Region[]>([])
const selectedRegionId = ref<EntityId>('')
const uHeight = ref(42)
let nextRuleId = 1
const generationRules = ref<RackGenerationRule[]>([createEmptyRule()])

const manageableRegions = computed(() =>
  regions.value.filter((region) => appStore.canManageRegionBusiness(region.id))
)

const generationResult = computed<GenerationResult>(() => {
  const names: string[] = []
  const items: RackCreateItemPayload[] = []
  const ruleResults = new Map<number, RuleGenerationResult>()
  let error = ''

  for (const rule of generationRules.value) {
    const result = generateRuleNames(rule)
    ruleResults.set(rule.id, result)
    names.push(...result.names)
    items.push(...result.items)
    if (!error && result.error) error = '请先修正规则表中的错误'
  }

  if (!error) {
    const seen = new Set<string>()
    const duplicateName = names.find((name) => {
      if (seen.has(name)) return true
      seen.add(name)
      return false
    })
    if (duplicateName) error = `生成结果存在重复机柜名称：${duplicateName}`
  }
  if (!error && names.length > MAX_CREATE_RACKS) {
    error = `单次最多创建 ${MAX_CREATE_RACKS} 个机柜，当前共生成 ${names.length} 个`
  }

  return { names, items, ruleResults, error }
})

const canSubmit = computed(
  () =>
    Boolean(selectedRegionId.value)
    && uHeight.value > 0
    && generationResult.value.names.length > 0
    && !generationResult.value.error
    && !submitting.value
)

function createEmptyRule(): RackGenerationRule {
  return {
    id: nextRuleId++,
    roomName: '',
    rackColumn: '',
    numberRange: '',
  }
}

function generateRuleNames(rule: RackGenerationRule): RuleGenerationResult {
  const roomName = rule.roomName.trim()
  const rackColumn = rule.rackColumn.trim()
  const rangeText = rule.numberRange.trim()
  if (!roomName) return { names: [], items: [], error: '请输入机房名' }
  if (!rackColumn) return { names: [], items: [], error: '请输入机柜列' }

  const match = /^(\d+)\s*-\s*(\d+)$/.exec(rangeText)
  if (!match) return { names: [], items: [], error: '编号范围格式应为“起始编号-结束编号”' }
  const start = Number(match[1])
  const end = Number(match[2])
  if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 1) {
    return { names: [], items: [], error: '机柜编号必须是大于 0 的整数' }
  }
  if (start > end) return { names: [], items: [], error: '起始编号不能大于结束编号' }
  if (end - start + 1 > MAX_CREATE_RACKS) {
    return { names: [], items: [], error: `单行最多生成 ${MAX_CREATE_RACKS} 个机柜` }
  }

  const items = Array.from({ length: end - start + 1 }, (_, index) => ({
    room_name: roomName,
    rack_column: rackColumn,
    rack_number: start + index,
  }))
  const names = items.map((item) => {
    const number = String(item.rack_number).padStart(2, '0')
    return `${item.room_name}-${item.rack_column}${number}`
  })
  const tooLongName = names.find((name) => name.length > 100)
  if (tooLongName) {
    return { names: [], items: [], error: `生成的机柜名称超过 100 个字符：${tooLongName}` }
  }
  return { names, items, error: '' }
}

function getRuleResult(ruleId: number): RuleGenerationResult {
  return generationResult.value.ruleResults.get(ruleId) || { names: [], items: [], error: '' }
}

function addRule() {
  generationRules.value.push(createEmptyRule())
}

function removeRule(ruleId: number) {
  if (generationRules.value.length === 1) return
  generationRules.value = generationRules.value.filter((rule) => rule.id !== ruleId)
}

function backToRacks() {
  router.push({ path: '/switch-cabling/racks', query: { region_id: selectedRegionId.value || undefined } })
}

async function submitCreate() {
  if (!canSubmit.value) return
  try {
    await ElMessageBox.confirm(
      `确定在当前 Region 创建 ${generationResult.value.names.length} 个 ${uHeight.value}U 机柜吗？`,
      '创建机柜',
      { type: 'warning', confirmButtonText: '创建', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  submitting.value = true
  try {
    const names = [...generationResult.value.names]
    const created = await createRacks(selectedRegionId.value, {
      items: generationResult.value.items,
      u_height: uHeight.value,
    })
    const responseMatchesPreview = created.length === names.length
      && created.every((rack, index) => rack.name === names[index])
    if (!responseMatchesPreview) {
      ElMessage.warning('机柜已创建，但返回结果与提交预览不一致，请刷新列表核对')
    } else {
      ElMessage.success(`已创建 ${created.length} 个机柜`)
    }
    await router.push({ path: '/switch-cabling/racks', query: { region_id: selectedRegionId.value } })
  } finally {
    submitting.value = false
  }
}

async function initialize() {
  loading.value = true
  try {
    const response = await fetchRegions({ skip: 0, limit: 500 })
    regions.value = response.items
    const requestedRegionId = typeof route.query.region_id === 'string' ? route.query.region_id : ''
    const requestedRegion = manageableRegions.value.find((region) => region.id === requestedRegionId)
    selectedRegionId.value = requestedRegion?.id || manageableRegions.value[0]?.id || ''
  } finally {
    loading.value = false
  }
}

onMounted(initialize)
</script>

<style scoped>
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: var(--spacing-lg);
}

.page-title {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-xl);
  font-weight: 700;
}

.page-desc {
  margin: 4px 0 0;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
}

.permission-alert,
.section-card {
  margin-bottom: var(--spacing-md);
}

.card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-heading > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.card-heading strong {
  color: var(--color-text-primary);
  font-size: var(--font-size-md);
}

.card-heading span {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
}

.context-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(320px, 1fr);
  gap: 24px;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.height-control {
  display: flex;
  align-items: center;
  gap: 12px;
}

.height-control span {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
}

.height-input {
  width: 180px;
}

.height-input :deep(.el-input__inner) {
  text-align: left;
}

.rule-error {
  color: var(--el-color-danger);
  font-size: var(--font-size-xs);
}

.rule-preview {
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: var(--color-text-primary);
  font-variant-numeric: tabular-nums;
}

.rule-preview small {
  color: var(--color-text-tertiary);
}

.preview-card {
  margin-bottom: var(--spacing-lg);
}

.preview-heading {
  align-items: flex-start;
}

.preview-alert {
  margin-bottom: 16px;
}

.name-preview-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding-right: 12px;
}

.name-preview-item {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: #f8fafc;
}

.name-preview-item strong {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.name-preview-item > span:last-child {
  color: var(--color-primary);
  font-size: var(--font-size-xs);
  font-weight: 600;
}

.name-index {
  color: var(--color-text-tertiary);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.page-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border-light);
}

@media (max-width: 1100px) {
  .name-preview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .page-heading,
  .rule-heading {
    align-items: stretch;
    flex-direction: column;
  }

  .context-grid,
  .name-preview-grid {
    grid-template-columns: 1fr;
  }

  .height-control {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
