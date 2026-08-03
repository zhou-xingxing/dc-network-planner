<template>
  <div v-loading="loading" class="planning-page">
    <div class="page-heading">
      <div>
        <h1 class="page-title">布线规划</h1>
        <p class="page-desc">先填写布线批次信息，再按服务器位置录入交换机组连线需求</p>
      </div>
    </div>

    <el-alert
      v-if="!loading && manageableRegions.length === 0"
      type="info"
      :closable="false"
      show-icon
      title="当前账号没有可管理的 Region，无法录入布线需求。"
    />

    <template v-else-if="manageableRegions.length > 0">
      <section class="workflow-stage batch-stage">
        <header class="stage-heading">
          <div class="stage-title">
            <span class="stage-number">01</span>
            <div>
              <span class="stage-order">先填写</span>
              <h2>布线批次信息</h2>
              <p>确定本次规划所属的 Region，并填写便于后续识别和追踪的批次信息。</p>
            </div>
          </div>
          <span class="stage-state" :class="{ 'is-ready': batchInfoReady }">
            <el-icon><CircleCheck /></el-icon>
            {{ batchInfoReady ? '批次信息已填写' : '等待填写批次名称' }}
          </span>
        </header>

        <div class="context-panel">
          <div class="context-fields">
            <label class="field-block region-field">
              <span>Region</span>
              <el-select
                v-model="selectedRegionId"
                filterable
                placeholder="请选择 Region"
                @change="handleRegionChange"
              >
                <el-option
                  v-for="region in manageableRegions"
                  :key="region.id"
                  :label="region.name"
                  :value="region.id"
                />
              </el-select>
            </label>
            <label
              class="field-block batch-field"
              :class="{ 'is-field-invalid': Boolean(batchNameIssue) }"
            >
              <span>批次名称</span>
              <el-input
                v-model="batchName"
                :aria-describedby="batchNameIssue ? 'batch-name-error' : undefined"
                :aria-invalid="Boolean(batchNameIssue)"
                maxlength="150"
                show-word-limit
                placeholder="例如：第一批服务器布线"
                @input="markTouched"
              />
              <small v-if="batchNameIssue" id="batch-name-error" class="field-error">{{ batchNameIssue }}</small>
            </label>
            <label class="field-block comment-field">
              <span>批次备注</span>
              <el-input
                v-model="comment"
                placeholder="可选，记录本次规划背景"
                @input="markTouched"
              />
            </label>
          </div>
        </div>
      </section>

      <div class="stage-transition">
        <span></span>
        <strong>完成批次信息后，继续录入连线需求</strong>
        <span></span>
      </div>

      <el-alert
        v-if="validationErrors.length > 0"
        class="validation-alert"
        type="error"
        :closable="false"
        show-icon
        :title="validationErrors[0]"
      >
        <template #default>
          <span v-if="validationErrors.length > 1">
            共有 {{ validationErrors.length }} 项问题需要修正，请检查批次信息及各服务器卡片中的提示
          </span>
        </template>
      </el-alert>

      <section class="workflow-stage demand-stage">
        <header class="stage-heading demand-heading">
          <div class="stage-title">
            <span class="stage-number">02</span>
            <div>
              <span class="stage-order">再录入</span>
              <h2>服务器与交换机连线需求</h2>
              <p>为每台服务器指定机柜位置、目标交换机组、连线根数和服务器端口。</p>
            </div>
          </div>
          <el-button type="primary" :icon="Plus" :disabled="resourcesLoading" @click="addServer">
            添加服务器
          </el-button>
        </header>

        <div class="demand-overview">
          <div class="planning-metrics" aria-label="当前需求汇总">
            <div>
              <span>服务器</span>
              <strong>{{ servers.length }}</strong>
            </div>
            <div>
              <span>目标交换机组</span>
              <strong>{{ totalConnections }}</strong>
            </div>
            <div>
              <span>计划线缆</span>
              <strong>{{ totalLines }}</strong>
            </div>
          </div>
          <p>同一机柜和起始 U 位代表一台服务器，连接多个交换机组时请在同一张服务器卡片中录入。</p>
        </div>

        <el-alert
          v-if="!resourcesLoading && rackOptions.length === 0"
          class="resource-alert"
          type="warning"
          :closable="false"
          show-icon
          title="当前 Region 还没有机柜，请先完成机柜管理。"
        />
        <el-alert
          v-else-if="!resourcesLoading && readyGroupCount === 0"
          class="resource-alert"
          type="warning"
          :closable="false"
          show-icon
          title="当前 Region 没有成员配置完整的交换机组。"
        />

        <el-empty
          v-if="servers.length === 0"
          class="server-empty"
          description="还没有服务器需求"
        >
          <el-button type="primary" :icon="Plus" @click="addServer">添加第一台服务器</el-button>
        </el-empty>

        <article v-for="(server, serverIndex) in servers" :key="server.localId" class="server-card">
          <header class="server-card-header">
            <div class="server-heading">
              <div class="server-index">
                <span>服务器</span>
                <strong>{{ String(serverIndex + 1).padStart(2, '0') }}</strong>
              </div>
              <div class="server-identity">
                <h3>{{ serverTitle(server, serverIndex) }}</h3>
                <p>{{ serverSubtitle(server) }}</p>
              </div>
            </div>

            <div class="header-position-fields">
              <label
                class="field-block rack-select-field"
                :class="{ 'is-field-invalid': positionIssues(server).length > 0 }"
              >
                <span>服务器侧机柜</span>
                <el-select
                  v-model="server.rackId"
                  :aria-describedby="positionIssues(server).length > 0 ? `server-position-error-${server.localId}` : undefined"
                  :aria-invalid="positionIssues(server).length > 0"
                  filterable
                  placeholder="请选择机柜"
                  @change="handleRackChange(server)"
                >
                  <el-option
                    v-for="rack in rackOptions"
                    :key="rack.id"
                    :label="rack.name"
                    :value="rack.id"
                  />
                </el-select>
                <div
                  v-if="positionIssues(server).length > 0"
                  :id="`server-position-error-${server.localId}`"
                  class="field-error-list"
                >
                  <small v-for="issue in positionIssues(server)" :key="issue" class="field-error">
                    {{ issue }}
                  </small>
                </div>
              </label>
              <label class="field-block number-field">
                <span>起始 U 位</span>
                <el-input-number
                  :key="`server-start-${server.localId}-${server.serverStartInputVersion}`"
                  :model-value="server.serverStartU"
                  :min="1"
                  :step="1"
                  :precision="0"
                  controls-position="right"
                  @update:model-value="handleServerNumberInput(server, 'serverStartU', $event)"
                  @blur="refreshServerNumberInput(server, 'serverStartU')"
                />
              </label>
              <label class="field-block number-field">
                <span>设备高度 (U)</span>
                <el-input-number
                  :key="`server-height-${server.localId}-${server.serverHeightInputVersion}`"
                  :model-value="server.serverHeightU"
                  :min="1"
                  :step="1"
                  :precision="0"
                  controls-position="right"
                  @update:model-value="handleServerNumberInput(server, 'serverHeightU', $event)"
                  @blur="refreshServerNumberInput(server, 'serverHeightU')"
                />
              </label>
            </div>

            <div class="server-status">
              <el-tag v-if="occupancyLoading.has(server.rackId)" type="info" effect="plain">正在读取机柜占用</el-tag>
              <el-tag v-else-if="matchedExistingPosition(server)" type="success" effect="plain">
                已有服务器位置 · {{ matchedExistingPosition(server)?.cable_count }} 根线
              </el-tag>
              <el-tag v-if="serverIssueCount(server) > 0" type="danger" effect="dark">
                {{ serverIssueCount(server) }} 项问题
              </el-tag>
              <el-button
                link
                :icon="CopyDocument"
                :aria-label="`复制服务器 ${serverIndex + 1}`"
                @click="duplicateServer(server)"
              >
                复制服务器
              </el-button>
              <el-button
                type="danger"
                link
                :icon="Delete"
                :aria-label="`删除服务器 ${serverIndex + 1}`"
                @click="removeServer(server)"
              >
                删除服务器
              </el-button>
            </div>
          </header>

          <div class="connection-workspace">
            <div class="connection-columns-heading">
              <div class="endpoint-heading">
                <div>
                  <span>服务器侧</span>
                  <strong>服务器端口</strong>
                </div>
                <small>端口按目标交换机组编号与右侧配置对应</small>
              </div>
              <div class="connections-heading">
                <div>
                  <span>交换机侧</span>
                  <strong>目标交换机组</strong>
                </div>
                <el-button :icon="Plus" @click="addConnection(server)">添加目标交换机组</el-button>
              </div>
            </div>

            <div
              v-for="(connection, connectionIndex) in server.connections"
              :key="connection.localId"
              class="connection-pair-row"
            >
              <section class="server-port-group">
                <div class="port-group-heading">
                  <span class="connection-number">{{ String(connectionIndex + 1).padStart(2, '0') }}</span>
                  <strong>服务器端口</strong>
                  <small>对应右侧目标交换机组 {{ String(connectionIndex + 1).padStart(2, '0') }}</small>
                </div>
                <div class="port-grid">
                  <label v-for="(line, lineIndex) in connection.lines" :key="line.localId" class="port-field">
                    <span>线 {{ String(lineIndex + 1).padStart(2, '0') }}</span>
                    <el-input
                      v-model="line.serverPortName"
                      :aria-describedby="portNameIssue(server, line) ? `server-port-error-${line.localId}` : undefined"
                      :aria-invalid="Boolean(portNameIssue(server, line))"
                      maxlength="100"
                      :class="{ 'is-port-invalid': Boolean(portNameIssue(server, line)) }"
                      placeholder="例如：eth0"
                      @input="markTouched"
                      @blur="normalizePortName(line)"
                    />
                    <small
                      v-if="portNameIssue(server, line)"
                      :id="`server-port-error-${line.localId}`"
                      class="field-error"
                    >
                      {{ portNameIssue(server, line) }}
                    </small>
                  </label>
                </div>
              </section>

              <section class="connection-block">
                <div class="connection-primary">
                  <span class="connection-number">{{ String(connectionIndex + 1).padStart(2, '0') }}</span>
                  <label
                    class="field-block group-field"
                    :class="{ 'is-field-invalid': connectionIssues(server, connection).length > 0 }"
                  >
                    <span>交换机组</span>
                    <el-select
                      v-model="connection.switchGroupId"
                      :aria-describedby="connectionIssues(server, connection).length > 0 ? `connection-error-${connection.localId}` : undefined"
                      :aria-invalid="connectionIssues(server, connection).length > 0"
                      filterable
                      placeholder="请选择目标交换机组"
                      @change="handleGroupChange(connection)"
                    >
                      <el-option
                        v-for="group in groupOptions"
                        :key="group.id"
                        :label="groupOptionLabel(group)"
                        :value="group.id"
                        :disabled="isGroupOptionDisabled(server, connection, group)"
                      />
                    </el-select>
                    <div
                      v-if="connectionIssues(server, connection).length > 0"
                      :id="`connection-error-${connection.localId}`"
                      class="field-error-list"
                    >
                      <small
                        v-for="issue in connectionIssues(server, connection)"
                        :key="issue"
                        class="field-error"
                      >
                        {{ issue }}
                      </small>
                    </div>
                  </label>
                  <div class="group-members">
                    <span>成员交换机所在位置</span>
                    <div v-if="selectedGroupMembers(connection).length > 0" class="group-member-list">
                      <div
                        v-for="member in selectedGroupMembers(connection)"
                        :key="member.id"
                        class="group-member-row"
                      >
                        <strong>{{ memberRoleLabel(member) }}</strong>
                        <el-tooltip :content="memberPositionLabel(member)" placement="top" :show-after="400">
                          <small>{{ memberPositionLabel(member) }}</small>
                        </el-tooltip>
                      </div>
                    </div>
                    <strong v-else class="group-members-empty">
                      {{ selectedGroup(connection) ? '暂无成员' : '待选择' }}
                    </strong>
                  </div>
                  <el-button
                    type="danger"
                    link
                    :icon="Delete"
                    :aria-label="`删除服务器 ${serverIndex + 1} 的目标交换机组 ${connectionIndex + 1}`"
                    @click="removeConnection(server, connection)"
                  >
                    删除
                  </el-button>
                </div>

                <div class="connection-meta">
                  <div class="group-mode">
                    <span>交换机组模式</span>
                    <el-tag
                      v-if="selectedGroup(connection)"
                      :type="selectedGroup(connection)?.group_mode === 'pair' ? 'primary' : 'success'"
                      effect="plain"
                    >
                      {{ selectedGroup(connection)?.group_mode }}
                    </el-tag>
                    <strong v-else>待选择</strong>
                  </div>
                  <label class="field-block line-count-field">
                    <span>连线根数</span>
                    <el-input-number
                      :key="`line-count-${connection.localId}-${connection.lineCountInputVersion}`"
                      :model-value="connection.lines.length"
                      :min="selectedGroup(connection)?.group_mode === 'pair' ? 2 : 1"
                      :step="selectedGroup(connection)?.group_mode === 'pair' ? 2 : 1"
                      :precision="0"
                      controls-position="right"
                      @update:model-value="handleLineCountInput(connection, $event)"
                    />
                  </label>
                  <div class="distribution">
                    <span>分配方式</span>
                    <strong>{{ distributionText(connection) }}</strong>
                  </div>
                </div>
              </section>
            </div>

            <el-empty
              v-if="server.connections.length === 0"
              class="connection-empty"
              :image-size="44"
              description="还没有目标交换机组"
            >
              <el-button :icon="Plus" @click="addConnection(server)">添加目标交换机组</el-button>
            </el-empty>
          </div>
        </article>
      </section>

      <footer class="action-bar">
        <div>
          <strong>录入阶段不会占用交换机端口</strong>
          <span>交换机端口分配、线序号和线签将在布线预览阶段生成</span>
        </div>
        <div class="action-buttons">
          <el-button :icon="Refresh" @click="resetPlanning">重置</el-button>
          <el-button
            type="primary"
            :icon="CircleCheck"
            :loading="checking"
            :disabled="resourcesLoading"
            @click="checkRequirements"
          >
            检查需求
          </el-button>
        </div>
      </footer>
    </template>

    <el-dialog v-model="summaryVisible" title="布线需求检查通过" width="min(920px, 92vw)">
      <div class="summary-banner">
        <el-icon><CircleCheck /></el-icon>
        <div>
          <strong>{{ validatedRequest?.servers.length || 0 }} 台服务器，{{ totalLines }} 根计划线缆</strong>
          <span>下列内容仅为需求汇总，尚未分配交换机端口或写入数据库。</span>
        </div>
      </div>
      <el-table :data="summaryRows" border>
        <el-table-column prop="server" label="服务器位置" min-width="180" />
        <el-table-column prop="group" label="目标交换机组" min-width="190" />
        <el-table-column prop="mode" label="模式" width="90" />
        <el-table-column prop="ports" label="服务器端口" min-width="260" />
      </el-table>
      <template #footer>
        <el-button type="primary" @click="summaryVisible = false">返回继续编辑</el-button>
      </template>
    </el-dialog>

    <el-dialog
      :model-value="Boolean(pendingLineCountChange)"
      title="调整连线根数"
      width="min(440px, 92vw)"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <p class="confirm-description">减少根数会删除已填写的服务器端口，确定继续吗？</p>
      <template #footer>
        <el-button @click="cancelLineCountChange">取消</el-button>
        <el-button type="primary" @click="confirmLineCountChange">继续</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { fetchRackOccupancy, fetchRacks } from '@/api/racks'
import { fetchRegions } from '@/api/regions'
import { fetchSwitchGroups, fetchSwitches } from '@/api/switches'
import { useAppStore } from '@/stores/app'
import type {
  CablingPlanningInput,
  EntityId,
  NetworkSwitch,
  Rack,
  RackOccupancy,
  RackServerPosition,
  Region,
  SwitchGroup,
} from '@/types'
import { CircleCheck, CopyDocument, Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute } from 'vue-router'

interface ServerPortLineForm {
  localId: number
  serverPortName: string
}

interface SwitchGroupConnectionForm {
  localId: number
  switchGroupId: EntityId
  lineCountInputVersion: number
  lines: ServerPortLineForm[]
}

interface ServerCablingDemandForm {
  localId: number
  rackId: EntityId
  serverStartU: number
  serverHeightU: number
  serverStartInputVersion: number
  serverHeightInputVersion: number
  connections: SwitchGroupConnectionForm[]
}

interface SummaryRow {
  server: string
  group: string
  mode: string
  ports: string
}

interface PendingLineCountChange {
  connection: SwitchGroupConnectionForm
  value: number
}

interface ServerValidationState {
  positionIssues: string[]
  connectionIssues: Map<number, string[]>
  portIssues: Map<number, string>
  issueCount: number
}

const PORT_NAME_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
const PAGE_LIMIT = 500
const appStore = useAppStore()
const route = useRoute()
const loading = ref(false)
const resourcesLoading = ref(false)
const checking = ref(false)
const regions = ref<Region[]>([])
const selectedRegionId = ref<EntityId>('')
const activeRegionId = ref<EntityId>('')
const batchName = ref('')
const comment = ref('')
const rackOptions = ref<Rack[]>([])
const groupOptions = ref<SwitchGroup[]>([])
const switchOptions = ref<NetworkSwitch[]>([])
const servers = ref<ServerCablingDemandForm[]>([])
const planningTouched = ref(false)
const validationAttempted = ref(false)
const validationErrors = ref<string[]>([])
const validatedRequest = ref<CablingPlanningInput | null>(null)
const summaryVisible = ref(false)
const pendingLineCountChange = ref<PendingLineCountChange | null>(null)
const occupancyCache = reactive(new Map<EntityId, RackOccupancy>())
const occupancyLoading = reactive(new Set<EntityId>())
const occupancyErrors = reactive(new Map<EntityId, string>())
const occupancyRequests = new Map<EntityId, Promise<void>>()
let nextLocalId = 1
let resourceRequestVersion = 0

const manageableRegions = computed(() =>
  regions.value.filter((region) => appStore.canManageRegionBusiness(region.id))
)
const totalConnections = computed(() =>
  servers.value.reduce((total, server) => total + server.connections.length, 0)
)
const totalLines = computed(() =>
  servers.value.reduce(
    (serverTotal, server) =>
      serverTotal
      + server.connections.reduce((connectionTotal, connection) => connectionTotal + connection.lines.length, 0),
    0
  )
)
const batchInfoReady = computed(() => Boolean(selectedRegionId.value && batchName.value.trim()))
const batchNameIssue = computed(() => {
  if (!validationAttempted.value) return ''
  if (!batchName.value.trim()) return '请输入批次名称'
  if (batchName.value.trim().length > 150) return '批次名称不能超过 150 个字符'
  return ''
})
const switchMembersByGroup = computed(() => {
  const membersByGroup = new Map<EntityId, NetworkSwitch[]>()
  for (const item of switchOptions.value) {
    if (!item.switch_group_id) continue
    const members = membersByGroup.get(item.switch_group_id) || []
    members.push(item)
    membersByGroup.set(item.switch_group_id, members)
  }
  const roleOrder = { a: 0, b: 1, single: 2 }
  for (const members of membersByGroup.values()) {
    members.sort((left, right) =>
      (roleOrder[left.member_role || 'single'] - roleOrder[right.member_role || 'single'])
      || left.name.localeCompare(right.name, 'zh-CN')
    )
  }
  return membersByGroup
})
const readyGroupCount = computed(() => groupOptions.value.filter((group) => group.is_member_config_ready).length)
const summaryRows = computed<SummaryRow[]>(() =>
  servers.value.flatMap((server) =>
    server.connections.map((connection) => ({
      server: `${selectedRack(server)?.name || '未选择机柜'} · ${positionRange(server)}`,
      group: selectedGroup(connection)?.name || '未选择',
      mode: selectedGroup(connection)?.group_mode || '-',
      ports: connection.lines.map((line) => line.serverPortName.trim()).join('、'),
    }))
  )
)

function createLine(): ServerPortLineForm {
  return { localId: nextLocalId++, serverPortName: '' }
}

function createConnection(): SwitchGroupConnectionForm {
  return {
    localId: nextLocalId++,
    switchGroupId: '',
    lineCountInputVersion: 0,
    lines: [createLine()],
  }
}

function createServer(): ServerCablingDemandForm {
  return {
    localId: nextLocalId++,
    rackId: '',
    serverStartU: 1,
    serverHeightU: 2,
    serverStartInputVersion: 0,
    serverHeightInputVersion: 0,
    connections: [createConnection()],
  }
}

function markTouched() {
  planningTouched.value = true
  validationErrors.value = []
  validatedRequest.value = null
  summaryVisible.value = false
}

function addServer(mark = true) {
  servers.value.push(createServer())
  if (mark) markTouched()
}

/** 深复制服务器及全部连线输入，从最大结束 U 位后继续排列并追加到列表末尾。 */
function duplicateServer(source: ServerCablingDemandForm) {
  if (!servers.value.some((server) => server.localId === source.localId)) return
  const nextServerStartU = servers.value.reduce(
    (maxEndU, server) => Math.max(maxEndU, server.serverStartU + server.serverHeightU),
    1
  )

  const duplicate: ServerCablingDemandForm = {
    localId: nextLocalId++,
    rackId: source.rackId,
    serverStartU: nextServerStartU,
    serverHeightU: source.serverHeightU,
    serverStartInputVersion: 0,
    serverHeightInputVersion: 0,
    connections: source.connections.map((connection) => ({
      localId: nextLocalId++,
      switchGroupId: connection.switchGroupId,
      lineCountInputVersion: 0,
      lines: connection.lines.map((line) => ({
        localId: nextLocalId++,
        serverPortName: line.serverPortName,
      })),
    })),
  }
  servers.value.push(duplicate)
  markTouched()
}

function addConnection(server: ServerCablingDemandForm) {
  server.connections.push(createConnection())
  markTouched()
}

function serverHasInput(server: ServerCablingDemandForm) {
  return Boolean(
    server.rackId
    || server.connections.some(
      (connection) => connection.switchGroupId || connection.lines.some((line) => line.serverPortName.trim())
    )
  )
}

async function removeServer(server: ServerCablingDemandForm) {
  if (serverHasInput(server)) {
    try {
      await ElMessageBox.confirm('该服务器已录入位置或连线信息，确定删除吗？', '删除服务器', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  servers.value = servers.value.filter((item) => item.localId !== server.localId)
  markTouched()
}

async function removeConnection(server: ServerCablingDemandForm, connection: SwitchGroupConnectionForm) {
  const hasInput = Boolean(
    connection.switchGroupId || connection.lines.some((line) => line.serverPortName.trim())
  )
  if (hasInput) {
    try {
      await ElMessageBox.confirm('该目标交换机组已录入连线信息，确定删除吗？', '删除目标交换机组', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  server.connections = server.connections.filter((item) => item.localId !== connection.localId)
  markTouched()
}

/** 让端口明细数量始终与用户选择的连线根数一致。 */
function resizeLines(connection: SwitchGroupConnectionForm, count: number) {
  while (connection.lines.length < count) connection.lines.push(createLine())
  if (connection.lines.length > count) connection.lines.splice(count)
}

function handleLineCountInput(connection: SwitchGroupConnectionForm, value: number | undefined) {
  if (value === undefined || !Number.isInteger(value) || value < 1) {
    connection.lineCountInputVersion += 1
    markTouched()
    return
  }
  commitLineCount(connection, value)
}

/** 提交线数变化，并在减少已填写端口前等待用户确认。 */
function commitLineCount(connection: SwitchGroupConnectionForm, value: number) {
  if (pendingLineCountChange.value?.connection.localId === connection.localId) return
  const previousCount = connection.lines.length
  if (value === previousCount) return

  const removedLines = value < connection.lines.length ? connection.lines.slice(value) : []
  if (removedLines.some((line) => line.serverPortName.trim())) {
    connection.lineCountInputVersion += 1
    pendingLineCountChange.value = { connection, value }
    return
  }
  resizeLines(connection, value)
  connection.lineCountInputVersion += 1
  markTouched()
}

function cancelLineCountChange() {
  pendingLineCountChange.value = null
}

function confirmLineCountChange() {
  const pending = pendingLineCountChange.value
  if (pending) {
    resizeLines(pending.connection, pending.value)
    pending.connection.lineCountInputVersion += 1
    markTouched()
  }
  pendingLineCountChange.value = null
}

type ServerNumberField = 'serverStartU' | 'serverHeightU'

function handleServerNumberInput(
  server: ServerCablingDemandForm,
  field: ServerNumberField,
  value: number | undefined
) {
  if (value !== undefined && Number.isInteger(value) && value > 0) server[field] = value
  markTouched()
}

/** 离焦后重建当前数值组件，确保显示值与已经更新的业务模型一致。 */
function refreshServerNumberInput(server: ServerCablingDemandForm, field: ServerNumberField) {
  if (field === 'serverStartU') server.serverStartInputVersion += 1
  else server.serverHeightInputVersion += 1
}

/** pair 组不能保留奇数根；切换组模式时向上补一根，避免删除已填写端口。 */
function handleGroupChange(connection: SwitchGroupConnectionForm) {
  const group = selectedGroup(connection)
  const lineCount = connection.lines.length
  if (group?.group_mode === 'pair' && lineCount % 2 !== 0) {
    resizeLines(connection, lineCount + 1)
    connection.lineCountInputVersion += 1
  }
  markTouched()
}

function normalizePortName(line: ServerPortLineForm) {
  const normalized = line.serverPortName.trim()
  if (normalized !== line.serverPortName) {
    line.serverPortName = normalized
    markTouched()
  }
}

function selectedRack(server: ServerCablingDemandForm) {
  return rackOptions.value.find((rack) => rack.id === server.rackId)
}

function selectedGroup(connection: SwitchGroupConnectionForm) {
  return groupOptions.value.find((group) => group.id === connection.switchGroupId)
}

function selectedGroupMembers(connection: SwitchGroupConnectionForm) {
  return switchMembersByGroup.value.get(connection.switchGroupId) || []
}

function memberRoleLabel(member: NetworkSwitch) {
  if (member.member_role === 'a') return 'A成员'
  if (member.member_role === 'b') return 'B成员'
  return 'single 成员'
}

function memberPositionLabel(member: NetworkSwitch) {
  const endU = member.start_u + member.height_u - 1
  const uRange = member.start_u === endU ? `${member.start_u}U` : `${member.start_u}U-${endU}U`
  return `${member.rack_name} · ${uRange}`
}

function positionEnd(server: ServerCablingDemandForm) {
  return server.serverStartU + server.serverHeightU - 1
}

function positionRange(server: ServerCablingDemandForm) {
  const endU = positionEnd(server)
  return server.serverStartU === endU ? `${server.serverStartU}U` : `${server.serverStartU}U-${endU}U`
}

function rangesOverlap(startA: number, heightA: number, startB: number, heightB: number) {
  const endA = startA + heightA - 1
  const endB = startB + heightB - 1
  return startA <= endB && endA >= startB
}

function matchedExistingPosition(server: ServerCablingDemandForm): RackServerPosition | undefined {
  const occupancy = occupancyCache.get(server.rackId)
  return occupancy?.server_positions.find(
    (position) => position.start_u === server.serverStartU && position.height_u === server.serverHeightU
  )
}

function serverTitle(server: ServerCablingDemandForm, serverIndex: number) {
  const rack = selectedRack(server)
  return rack ? `${rack.name} · ${positionRange(server)}` : `服务器 ${serverIndex + 1}`
}

function serverSubtitle(server: ServerCablingDemandForm) {
  const lineCount = server.connections.reduce((total, connection) => total + connection.lines.length, 0)
  return `${server.connections.length} 个目标交换机组 · ${lineCount} 根计划线缆`
}

function groupOptionLabel(group: SwitchGroup) {
  const readiness = group.is_member_config_ready ? '成员完整' : '配置未完整'
  return `${group.name} · ${readiness}`
}

function isGroupOptionDisabled(
  server: ServerCablingDemandForm,
  connection: SwitchGroupConnectionForm,
  group: SwitchGroup
) {
  return !group.is_member_config_ready
    || server.connections.some(
      (item) => item.localId !== connection.localId && item.switchGroupId === group.id
    )
}

function distributionText(connection: SwitchGroupConnectionForm) {
  const group = selectedGroup(connection)
  if (!group) return '待选择'
  const lineCount = connection.lines.length
  if (group.group_mode === 'single') return `single 成员 ${lineCount} 根`
  if (lineCount % 2 !== 0) return '需调整为偶数'
  return `A成员 ${lineCount / 2} 根 / B成员 ${lineCount / 2} 根`
}

/** 综合当前输入、已有服务器位置和交换机上架范围校验服务器位置。 */
function calculatePositionIssues(server: ServerCablingDemandForm) {
  const issues: string[] = []
  const rack = selectedRack(server)
  if (!server.rackId) {
    if (validationAttempted.value) issues.push('请选择服务器侧机柜')
    return issues
  }
  if (!rack) {
    issues.push('所选机柜不属于当前 Region')
    return issues
  }
  if (!Number.isInteger(server.serverStartU) || server.serverStartU < 1) issues.push('起始 U 位必须是正整数')
  if (!Number.isInteger(server.serverHeightU) || server.serverHeightU < 1) issues.push('设备高度必须是正整数')
  if (issues.length > 0) return issues
  if (positionEnd(server) > rack.u_height) {
    issues.push(`服务器位置 ${positionRange(server)} 超出机柜 ${rack.name} 的 ${rack.u_height}U 范围`)
  }

  const duplicatedServer = servers.value.find(
    (item) => item.localId !== server.localId
      && item.rackId === server.rackId
      && item.serverStartU === server.serverStartU
  )
  if (duplicatedServer) {
    issues.push('同一机柜和起始 U 位只能录入一张服务器卡片')
  } else {
    const overlappingServer = servers.value.find(
      (item) => item.localId !== server.localId
        && item.rackId === server.rackId
        && rangesOverlap(server.serverStartU, server.serverHeightU, item.serverStartU, item.serverHeightU)
    )
    if (overlappingServer) {
      issues.push(`服务器位置 ${positionRange(server)} 与当前输入中的 ${positionRange(overlappingServer)} 重叠`)
    }
  }

  const occupancyError = occupancyErrors.get(server.rackId)
  if (occupancyError) issues.push(occupancyError)
  const occupancy = occupancyCache.get(server.rackId)
  if (!occupancy) return issues

  const sameStart = occupancy.server_positions.find((position) => position.start_u === server.serverStartU)
  if (sameStart && sameStart.height_u !== server.serverHeightU) {
    issues.push(`已有服务器位置从 ${server.serverStartU}U 开始且高度为 ${sameStart.height_u}U，不能改用 ${server.serverHeightU}U`)
  }
  const overlappingExistingServer = occupancy.server_positions.find(
    (position) => position.start_u !== server.serverStartU
      && rangesOverlap(server.serverStartU, server.serverHeightU, position.start_u, position.height_u)
  )
  if (overlappingExistingServer) {
    const existingEnd = overlappingExistingServer.start_u + overlappingExistingServer.height_u - 1
    issues.push(
      `服务器位置 ${positionRange(server)} 与已有服务器位置 `
      + `${overlappingExistingServer.start_u}U-${existingEnd}U 重叠`
    )
  }
  const overlappingSwitch = occupancy.switch_positions.find((item) =>
    rangesOverlap(server.serverStartU, server.serverHeightU, item.start_u, item.height_u)
  )
  if (overlappingSwitch) {
    const switchEnd = overlappingSwitch.start_u + overlappingSwitch.height_u - 1
    issues.push(
      `服务器位置 ${positionRange(server)} 与交换机 ${overlappingSwitch.switch_name} `
      + `的 ${overlappingSwitch.start_u}U-${switchEnd}U 重叠`
    )
  }
  return [...new Set(issues)]
}

/** 校验目标交换机组归属、成员完整性、组内唯一性和 single/pair 根数规则。 */
function calculateConnectionIssues(server: ServerCablingDemandForm, connection: SwitchGroupConnectionForm) {
  const issues: string[] = []
  const group = selectedGroup(connection)
  if (!connection.switchGroupId) {
    if (validationAttempted.value) issues.push('请选择目标交换机组')
    return issues
  }
  if (!group || group.region_id !== selectedRegionId.value) {
    issues.push('目标交换机组不属于当前 Region')
    return issues
  }
  if (!group.is_member_config_ready) {
    issues.push(group.readiness_issues.map((issue) => issue.message).join('；') || '目标交换机组成员配置未完整')
  }
  if (server.connections.some(
    (item) => item.localId !== connection.localId && item.switchGroupId === connection.switchGroupId
  )) {
    issues.push('同一服务器不能重复选择同一交换机组')
  }
  const lineCount = connection.lines.length
  if (lineCount < 1) {
    issues.push('连线根数必须是正整数')
  } else if (group.group_mode === 'pair' && lineCount % 2 !== 0) {
    issues.push('pair 组只允许正偶数根连线，并平均分配给 A、B 成员')
  }
  return issues
}

/** 校验端口名格式、当前服务器内唯一性以及已有线缆端点占用。 */
function calculatePortNameIssue(
  line: ServerPortLineForm,
  portNameCounts: Map<string, number>,
  existingPosition: RackServerPosition | undefined
) {
  const normalized = line.serverPortName.trim()
  if (!normalized) return validationAttempted.value ? '请输入服务器端口名' : ''
  if (normalized.length > 100) return '服务器端口名不能超过 100 个字符'
  if (!PORT_NAME_PATTERN.test(normalized)) return '只允许小写字母、数字和非连续中划线'
  if ((portNameCounts.get(normalized) || 0) > 1) {
    return '该服务器端口在当前需求中重复'
  }
  if (existingPosition?.server_port_names.some(
    (name) => name.trim().toLowerCase() === normalized
  )) {
    return '该服务器端口已有线缆占用'
  }
  return ''
}

/**
 * 为每台服务器一次性生成完整校验结果，供卡片渲染、问题计数和提交检查共同复用。
 * 端口名先构造计数表，避免逐行校验时反复扫描服务器的全部端口。
 */
const serverValidationStates = computed(() => {
  const states = new Map<number, ServerValidationState>()
  for (const server of servers.value) {
    const positionIssueList = calculatePositionIssues(server)
    const connectionIssueMap = new Map<number, string[]>()
    const portIssueMap = new Map<number, string>()
    const portNameCounts = new Map<string, number>()

    for (const connection of server.connections) {
      connectionIssueMap.set(connection.localId, calculateConnectionIssues(server, connection))
      for (const line of connection.lines) {
        const normalized = line.serverPortName.trim()
        portNameCounts.set(normalized, (portNameCounts.get(normalized) || 0) + 1)
      }
    }

    const existingPosition = matchedExistingPosition(server)
    for (const connection of server.connections) {
      for (const line of connection.lines) {
        portIssueMap.set(line.localId, calculatePortNameIssue(line, portNameCounts, existingPosition))
      }
    }

    const allIssues = [
      ...positionIssueList,
      ...Array.from(connectionIssueMap.values()).flat(),
      ...Array.from(portIssueMap.values()).filter(Boolean),
    ]
    states.set(server.localId, {
      positionIssues: positionIssueList,
      connectionIssues: connectionIssueMap,
      portIssues: portIssueMap,
      issueCount: allIssues.length,
    })
  }
  return states
})

function positionIssues(server: ServerCablingDemandForm) {
  return serverValidationStates.value.get(server.localId)?.positionIssues || []
}

function connectionIssues(server: ServerCablingDemandForm, connection: SwitchGroupConnectionForm) {
  return serverValidationStates.value.get(server.localId)?.connectionIssues.get(connection.localId) || []
}

function portNameIssue(server: ServerCablingDemandForm, line: ServerPortLineForm) {
  return serverValidationStates.value.get(server.localId)?.portIssues.get(line.localId) || ''
}

function serverIssueCount(server: ServerCablingDemandForm) {
  return serverValidationStates.value.get(server.localId)?.issueCount || 0
}

/** 将失败校验与第一个错误控件关联，避免用户从页面顶部逐项寻找。 */
async function focusFirstInvalidField() {
  await nextTick()
  const invalidField = document.querySelector<HTMLElement>('.planning-page [aria-invalid="true"]')
  if (!invalidField) return

  const focusTarget = invalidField.matches('input, textarea, button, [role="combobox"]')
    ? invalidField
    : invalidField.querySelector<HTMLElement>('input, textarea, button, [role="combobox"], [tabindex]:not([tabindex="-1"])')
  invalidField.scrollIntoView({ block: 'center' })
  focusTarget?.focus({ preventScroll: true })
}

/** 缓存机柜占用快照，并合并同一机柜的并发请求。 */
async function loadRackOccupancy(rackId: EntityId) {
  if (!rackId || occupancyCache.has(rackId)) return
  const pending = occupancyRequests.get(rackId)
  if (pending) return pending
  occupancyLoading.add(rackId)
  occupancyErrors.delete(rackId)
  const request = fetchRackOccupancy(selectedRegionId.value, rackId)
    .then((occupancy) => {
      if (occupancy.rack_id === rackId) occupancyCache.set(rackId, occupancy)
    })
    .catch(() => {
      occupancyErrors.set(rackId, '机柜占用信息加载失败，请重新选择机柜后再试')
    })
    .finally(() => {
      occupancyLoading.delete(rackId)
      occupancyRequests.delete(rackId)
    })
  occupancyRequests.set(rackId, request)
  return request
}

async function handleRackChange(server: ServerCablingDemandForm) {
  markTouched()
  if (server.rackId) await loadRackOccupancy(server.rackId)
}

async function fetchAllRacks(regionId: EntityId) {
  const items: Rack[] = []
  let skip = 0
  while (true) {
    const response = await fetchRacks(regionId, { skip, limit: PAGE_LIMIT })
    items.push(...response.items)
    skip += response.items.length
    if (skip >= response.total || response.items.length === 0) return items
  }
}

async function fetchAllGroups(regionId: EntityId) {
  const items: SwitchGroup[] = []
  let skip = 0
  while (true) {
    const response = await fetchSwitchGroups(regionId, { skip, limit: PAGE_LIMIT })
    items.push(...response.items)
    skip += response.items.length
    if (skip >= response.total || response.items.length === 0) return items
  }
}

async function fetchAllSwitches(regionId: EntityId) {
  const items: NetworkSwitch[] = []
  let skip = 0
  while (true) {
    const response = await fetchSwitches(regionId, { skip, limit: PAGE_LIMIT })
    items.push(...response.items)
    skip += response.items.length
    if (skip >= response.total || response.items.length === 0) return items
  }
}

async function loadRegionResources(regionId: EntityId) {
  const requestVersion = ++resourceRequestVersion
  resourcesLoading.value = true
  rackOptions.value = []
  groupOptions.value = []
  switchOptions.value = []
  try {
    const [racks, groups, switches] = await Promise.all([
      fetchAllRacks(regionId),
      fetchAllGroups(regionId),
      fetchAllSwitches(regionId),
    ])
    if (requestVersion !== resourceRequestVersion || selectedRegionId.value !== regionId) return
    rackOptions.value = racks
    groupOptions.value = groups
    switchOptions.value = switches
  } catch {
    if (requestVersion === resourceRequestVersion) {
      rackOptions.value = []
      groupOptions.value = []
      switchOptions.value = []
    }
  } finally {
    if (requestVersion === resourceRequestVersion) resourcesLoading.value = false
  }
}

function resetPlanningContent() {
  batchName.value = ''
  comment.value = ''
  servers.value = []
  occupancyCache.clear()
  occupancyErrors.clear()
  occupancyLoading.clear()
  validationAttempted.value = false
  validationErrors.value = []
  validatedRequest.value = null
  summaryVisible.value = false
  pendingLineCountChange.value = null
  addServer(false)
  planningTouched.value = false
}

async function handleRegionChange(value: EntityId) {
  if (planningTouched.value) {
    try {
      await ElMessageBox.confirm('切换 Region 会清空当前已录入的布线需求，确定继续吗？', '切换 Region', {
        type: 'warning',
        confirmButtonText: '继续',
        cancelButtonText: '取消',
      })
    } catch {
      selectedRegionId.value = activeRegionId.value
      return
    }
  }
  activeRegionId.value = value
  resetPlanningContent()
  await loadRegionResources(value)
}

async function resetPlanning() {
  if (planningTouched.value) {
    try {
      await ElMessageBox.confirm('确定清空当前所有布线需求吗？', '重置布线规划', {
        type: 'warning',
        confirmButtonText: '重置',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  resetPlanningContent()
}

/** 去除页面本地 ID 和输入首尾空格，构造后续预览接口可直接接收的需求。 */
function buildPlanningInput(): CablingPlanningInput {
  return {
    region_id: selectedRegionId.value,
    batch_name: batchName.value.trim(),
    comment: comment.value.trim(),
    servers: servers.value.map((server) => ({
      server_rack_id: server.rackId,
      server_start_u: server.serverStartU,
      server_height_u: server.serverHeightU,
      connections: server.connections.map((connection) => ({
        switch_group_id: connection.switchGroupId,
        lines: connection.lines.map((line) => ({ server_port_name: line.serverPortName.trim() })),
      })),
    })),
  }
}

/** 在不占用交换机端口的前提下，完成输入形状和已有机柜占用的统一校验。 */
async function checkRequirements() {
  checking.value = true
  validationAttempted.value = true
  try {
    await Promise.all([...new Set(servers.value.map((server) => server.rackId).filter(Boolean))].map(loadRackOccupancy))
    const errors: string[] = []
    if (!selectedRegionId.value || !appStore.canManageRegionBusiness(selectedRegionId.value)) {
      errors.push('请选择有业务管理权限的 Region')
    }
    if (!batchName.value.trim()) errors.push('请输入批次名称')
    if (batchName.value.trim().length > 150) errors.push('批次名称不能超过 150 个字符')
    if (servers.value.length === 0) errors.push('请至少添加一台服务器')

    servers.value.forEach((server, serverIndex) => {
      const prefix = `服务器 ${serverIndex + 1}`
      errors.push(...positionIssues(server).map((issue) => `${prefix}：${issue}`))
      if (server.connections.length === 0) errors.push(`${prefix}：请至少添加一个目标交换机组`)
      server.connections.forEach((connection, connectionIndex) => {
        const connectionPrefix = `${prefix} 的目标交换机组 ${connectionIndex + 1}`
        errors.push(...connectionIssues(server, connection).map((issue) => `${connectionPrefix}：${issue}`))
        connection.lines.forEach((line, lineIndex) => {
          const issue = portNameIssue(server, line)
          if (issue) errors.push(`${connectionPrefix} 线 ${lineIndex + 1}：${issue}`)
        })
      })
    })

    validationErrors.value = [...new Set(errors)]
    if (validationErrors.value.length > 0) {
      await focusFirstInvalidField()
      ElMessage.error(`布线需求还有 ${validationErrors.value.length} 项问题`)
      return
    }
    servers.value.forEach((server) =>
      server.connections.forEach((connection) =>
        connection.lines.forEach(normalizePortName)
      )
    )
    batchName.value = batchName.value.trim()
    comment.value = comment.value.trim()
    validatedRequest.value = buildPlanningInput()
    summaryVisible.value = true
    ElMessage.success('布线需求检查通过')
  } finally {
    checking.value = false
  }
}

async function initialize() {
  loading.value = true
  try {
    const response = await fetchRegions({ skip: 0, limit: PAGE_LIMIT })
    regions.value = response.items
    const requestedRegionId = typeof route.query.region_id === 'string' ? route.query.region_id : ''
    const preferredRegion = manageableRegions.value.find((region) => region.id === requestedRegionId)
      || manageableRegions.value[0]
    selectedRegionId.value = preferredRegion?.id || ''
    activeRegionId.value = selectedRegionId.value
    if (selectedRegionId.value) {
      await loadRegionResources(selectedRegionId.value)
      addServer(false)
    }
  } catch {
    regions.value = []
    selectedRegionId.value = ''
    activeRegionId.value = ''
  } finally {
    loading.value = false
  }
}

onBeforeRouteLeave(async () => {
  if (!planningTouched.value) return true
  try {
    await ElMessageBox.confirm('当前布线需求尚未生成预览，离开页面将丢失输入，确定离开吗？', '离开布线规划', {
      type: 'warning',
      confirmButtonText: '离开',
      cancelButtonText: '继续编辑',
    })
    return true
  } catch {
    return false
  }
})

onMounted(initialize)
</script>

<style scoped>
.planning-page { min-width: 0; }
.page-heading { margin-bottom: var(--spacing-lg); }
.page-title { margin: 0; color: var(--color-text-primary); font-size: var(--font-size-xl); font-weight: 700; }
.page-desc { margin: 4px 0 0; color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.workflow-stage { min-width: 0; }
.batch-stage { overflow: hidden; border: 1px solid #d8e3f2; border-radius: var(--radius-lg); background: #fff; box-shadow: 0 8px 24px rgba(40, 82, 130, .06); }
.stage-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 20px; }
.batch-stage > .stage-heading { border-bottom: 1px solid #e4ebf4; background: linear-gradient(110deg, #f3f8ff 0%, #fff 68%); }
.stage-title { display: flex; min-width: 0; align-items: center; gap: 14px; }
.stage-number { display: inline-flex; width: 48px; height: 48px; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: 50%; background: #175da8; color: #fff; font-size: 16px; font-weight: 800; font-variant-numeric: tabular-nums; box-shadow: 0 0 0 6px rgba(23, 93, 168, .09); }
.stage-order { display: block; margin-bottom: 2px; color: var(--color-primary-dark); font-size: 12px; font-weight: 700; }
.stage-title h2 { margin: 0; color: var(--color-text-primary); font-size: 18px; }
.stage-title p { margin: 4px 0 0; color: var(--color-text-secondary); font-size: 12px; line-height: 1.6; }
.stage-state { display: inline-flex; flex: 0 0 auto; align-items: center; gap: 6px; padding: 7px 11px; border: 1px solid #d8e1ed; border-radius: 999px; background: #fff; color: var(--color-text-secondary); font-size: 12px; font-weight: 700; }
.stage-state.is-ready { border-color: #b8dfc5; background: #f1faf4; color: var(--color-success); }
.context-panel { padding: 18px 20px 20px; }
.context-fields { display: grid; grid-template-columns: minmax(180px, .8fr) minmax(260px, 1.2fr) minmax(220px, 1fr); gap: 14px; }
.field-block { display: flex; min-width: 0; flex-direction: column; gap: 6px; }
.field-block > span, .group-mode > span, .distribution > span { color: var(--color-text-secondary); font-size: 12px; font-weight: 700; }
.stage-transition { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 14px; margin: 14px 20px; }
.stage-transition span { height: 1px; background: linear-gradient(90deg, transparent, #c9d8e9); }
.stage-transition span:last-child { background: linear-gradient(90deg, #c9d8e9, transparent); }
.stage-transition strong { color: var(--color-text-secondary); font-size: 12px; font-weight: 700; }
.demand-stage { padding-top: 2px; }
.demand-heading { padding: 14px 0 12px; }
.demand-heading .stage-number { background: #17375e; box-shadow: 0 0 0 6px rgba(23, 55, 94, .08); }
.demand-overview { display: flex; align-items: center; justify-content: space-between; gap: 22px; margin-bottom: 14px; padding: 12px 14px; border: 1px solid #dde6f0; border-radius: var(--radius-md); background: #f8fafc; }
.demand-overview > p { max-width: 680px; margin: 0; color: var(--color-text-secondary); font-size: 12px; line-height: 1.6; text-align: right; }
.planning-metrics { display: grid; flex: 0 0 auto; grid-template-columns: repeat(3, minmax(76px, 1fr)); overflow: hidden; border: 1px solid #d8e3f2; border-radius: var(--radius-md); background: #fff; }
.planning-metrics > div { display: flex; min-width: 78px; flex-direction: column; justify-content: center; padding: 10px 16px; border-left: 1px solid #e3eaf3; }
.planning-metrics > div:first-child { border-left: none; }
.planning-metrics span { color: var(--color-text-secondary); font-size: 12px; white-space: nowrap; }
.planning-metrics strong { color: var(--color-primary-dark); font-size: 22px; font-variant-numeric: tabular-nums; }
.validation-alert, .resource-alert { margin-bottom: 16px; }
.server-empty { padding: 36px 0; border: 1px dashed #c9d6e6; border-radius: var(--radius-lg); background: #fff; }
.server-card { container-type: inline-size; overflow: hidden; margin-bottom: 18px; border: 1px solid #d8e1ed; border-radius: 12px; background: #fff; box-shadow: 0 10px 26px rgba(31, 55, 84, .06); }
.server-card-header { display: grid; min-height: 76px; grid-template-columns: minmax(220px, .7fr) minmax(460px, 1.6fr) auto; align-items: start; gap: 16px; padding: 12px 14px; border-bottom: 1px solid #e5eaf1; background: linear-gradient(90deg, #f3f7fc 0%, #fff 58%); }
.server-heading { display: flex; min-width: 0; align-items: center; gap: 12px; }
.server-index { display: flex; width: 50px; height: 44px; flex: 0 0 auto; flex-direction: column; align-items: center; justify-content: center; border-radius: 8px; background: #17375e; color: #fff; }
.server-index span { font-size: 11px; font-weight: 700; opacity: .86; }
.server-index strong { font-size: 18px; line-height: 1.1; }
.server-identity { min-width: 0; }
.server-identity h3 { overflow: hidden; margin: 0; color: var(--color-text-primary); font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
.server-identity p { margin: 3px 0 0; color: var(--color-text-secondary); font-size: 12px; }
.header-position-fields { display: grid; min-width: 0; grid-template-columns: minmax(220px, 1fr) 108px 108px; gap: 10px; align-items: start; }
.server-status { display: flex; align-self: center; align-items: center; justify-content: flex-end; gap: 8px; }
.connection-workspace { min-width: 0; }
.connection-columns-heading, .connection-pair-row { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr); }
.connection-columns-heading { border-bottom: 1px solid #e2e8f0; }
.endpoint-heading, .connections-heading { display: flex; min-height: 52px; align-items: center; justify-content: space-between; gap: 12px; margin: 0; padding: 10px 16px; }
.endpoint-heading { border-right: 1px solid #e2e8f0; background: #f7faff; }
.endpoint-heading > div, .connections-heading > div { display: flex; min-width: 0; flex-direction: column; }
.endpoint-heading span, .connections-heading span { color: var(--color-primary-dark); font-size: 12px; font-weight: 700; }
.endpoint-heading strong, .connections-heading strong { color: var(--color-text-primary); font-size: var(--font-size-sm); }
.endpoint-heading small { color: var(--color-text-secondary); font-size: 12px; }
.number-field :deep(.el-input-number) { width: 100%; }
.is-field-invalid :deep(.el-select__wrapper), .is-field-invalid :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px var(--color-danger) inset; }
.connection-pair-row { border-bottom: 1px solid #e2e8f0; }
.connection-pair-row:last-of-type { border-bottom: none; }
.server-port-group, .connection-block { min-width: 0; padding: 12px 16px 14px; }
.server-port-group { border-right: 1px solid #e2e8f0; background: #fbfcfe; }
.port-group-heading { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.port-group-heading strong { color: var(--color-text-primary); font-size: var(--font-size-xs); }
.port-group-heading small { color: var(--color-text-secondary); font-size: 12px; }
.connection-block { background: #fff; }
.connection-empty { padding: 24px 0; }
.connection-primary { display: grid; grid-template-columns: 32px minmax(0, 1.3fr) minmax(0, .9fr) auto; gap: 10px; align-items: start; }
.connection-primary > .connection-number { margin-top: 22px; }
.connection-number { display: inline-flex; width: 32px; height: 32px; align-items: center; justify-content: center; border-radius: 6px; background: #dce9f8; color: #17375e; font-size: 12px; font-weight: 800; }
.group-members { display: flex; width: calc(100% - 12px); min-width: 0; justify-self: start; flex-direction: column; gap: 6px; }
.group-members > span { color: var(--color-text-secondary); font-size: 12px; font-weight: 700; }
.group-member-list { display: grid; gap: 4px; }
.group-member-row { display: grid; min-width: 0; grid-template-columns: auto minmax(0, 1fr); align-items: center; gap: 8px; padding: 5px 8px; border: 1px solid #e1e8f1; border-radius: 6px; background: #f8fafc; }
.group-member-row strong { color: var(--color-primary-dark); font-size: 12px; white-space: nowrap; }
.group-member-row small { display: block; overflow: hidden; color: var(--color-text-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.group-members-empty { display: flex; min-height: 32px; align-items: center; color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.connection-meta { display: grid; grid-template-columns: 78px 88px minmax(100px, 1fr); gap: 10px; margin: 10px 0 0 42px; align-items: end; }
.group-mode, .distribution { display: flex; min-height: 56px; flex-direction: column; justify-content: center; gap: 5px; }
.connection-meta .group-mode, .connection-meta .line-count-field { align-items: center; text-align: center; }
.group-mode strong, .distribution strong { color: var(--color-text-primary); font-size: 12px; }
.line-count-field :deep(.el-input-number) { width: 88px; }
.port-grid { display: grid; grid-template-columns: repeat(4, minmax(100px, 1fr)); gap: 8px; }
.port-field { display: flex; min-width: 0; flex-direction: column; gap: 4px; }
.port-field > span { color: var(--color-text-secondary); font-size: 12px; font-weight: 700; }
.field-error-list { display: flex; flex-direction: column; gap: 2px; }
.field-error { display: block; color: #c5221f; font-size: 12px; line-height: 1.4; }
.is-port-invalid :deep(.el-input__wrapper) { box-shadow: 0 0 0 1px var(--color-danger) inset; }
.action-bar { position: sticky; bottom: -1px; z-index: 4; display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 20px; padding: 14px 18px; border: 1px solid #d7e1ed; border-radius: 10px 10px 0 0; background: rgba(255, 255, 255, .96); box-shadow: 0 -8px 24px rgba(24, 47, 74, .08); backdrop-filter: blur(8px); }
.action-bar > div:first-child { display: flex; min-width: 0; flex-direction: column; }
.action-bar strong { color: var(--color-text-primary); font-size: var(--font-size-sm); }
.action-bar span { color: var(--color-text-secondary); font-size: 12px; }
.action-buttons { display: flex; flex: 0 0 auto; gap: 10px; }
.summary-banner { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding: 14px; border: 1px solid #bfe1ca; border-radius: 8px; background: #f0faf3; }
.summary-banner > .el-icon { color: var(--color-success); font-size: 28px; }
.summary-banner > div { display: flex; flex-direction: column; }
.summary-banner strong { color: var(--color-text-primary); }
.summary-banner span { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.confirm-description { margin: 0; color: var(--color-text-secondary); line-height: 1.7; }

@media (max-width: 1280px) {
  .planning-metrics { max-width: 420px; }
  .server-card-header { grid-template-columns: minmax(190px, .7fr) minmax(400px, 1.5fr) auto; gap: 12px; }
  .header-position-fields { grid-template-columns: minmax(180px, 1fr) 92px 92px; }
}

@container (max-width: 1050px) {
  .server-card-header { grid-template-columns: minmax(190px, .7fr) minmax(400px, 1.5fr); }
  .server-status { grid-column: 1 / -1; justify-content: flex-end; }
  .connection-columns-heading, .connection-pair-row { grid-template-columns: 1fr; }
  .endpoint-heading, .server-port-group { border-right: none; border-bottom: 1px solid #e2e8f0; }
}

@container (max-width: 720px) {
  .server-card-header { grid-template-columns: 1fr; }
  .header-position-fields { grid-template-columns: 1fr 1fr; }
  .header-position-fields .rack-select-field { grid-column: 1 / -1; }
  .server-status { grid-column: 1; justify-content: flex-start; flex-wrap: wrap; }
  .connection-primary { grid-template-columns: 32px minmax(0, 1.2fr) minmax(0, .8fr) auto; }
  .port-grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
}

@container (max-width: 480px) {
  .header-position-fields, .port-grid { grid-template-columns: 1fr; }
  .header-position-fields .number-field, .header-position-fields .rack-select-field { grid-column: 1; }
  .connection-primary { grid-template-columns: 32px minmax(0, 1fr); }
  .connection-primary > .group-members, .connection-primary > .el-button { grid-column: 2; justify-self: stretch; }
  .connection-primary > .group-members { width: 100%; }
  .connection-primary > .el-button { justify-self: start; }
  .connection-meta { grid-template-columns: 1fr 1fr; }
  .distribution { grid-column: 1 / -1; }
}

@media (max-width: 900px) {
  .stage-heading, .action-bar, .demand-overview { align-items: stretch; flex-direction: column; }
  .stage-state { align-self: flex-start; }
  .demand-overview > p { max-width: none; text-align: left; }
  .context-fields { grid-template-columns: 1fr 1fr; }
  .region-field, .batch-field, .comment-field, .rack-select-field { grid-column: 1 / -1; }
  .action-buttons { justify-content: flex-end; }
}

@media (max-width: 600px) {
  .context-fields, .planning-metrics { grid-template-columns: 1fr; }
  .stage-heading { padding: 16px; }
  .stage-title { align-items: flex-start; }
  .stage-number { width: 42px; height: 42px; }
  .context-panel { padding: 16px; }
  .stage-transition { margin-right: 8px; margin-left: 8px; }
  .stage-transition strong { text-align: center; }
  .planning-metrics > div { border-top: 1px solid #e3eaf3; border-left: none; }
  .planning-metrics > div:first-child { border-top: none; }
  .endpoint-heading { align-items: flex-start; flex-direction: column; }
  .connections-heading { align-items: stretch; flex-direction: column; }
  .action-bar { gap: 10px; padding: 10px 12px calc(10px + env(safe-area-inset-bottom)); }
  .action-bar > div:first-child { display: none; }
  .action-buttons { display: grid; width: 100%; grid-template-columns: 1fr 1fr; }
  .action-buttons :deep(.el-button) { min-height: 40px; }
  .planning-page :deep(.el-input__inner),
  .planning-page :deep(.el-select__selected-item),
  .planning-page :deep(.el-input-number .el-input__inner) { font-size: 16px; }
}
</style>
