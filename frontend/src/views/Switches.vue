<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">交换机管理</h2>
        <p class="page-desc">维护交换机组、上架位置和物理端口，为布线规划建立可用资源台账</p>
      </div>
      <el-button v-if="showPrimaryAction" type="primary" :icon="Plus" @click="handlePrimaryAction">
        {{ primaryActionLabel }}
      </el-button>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <div v-if="activeTab !== 'types'" class="filter-field region-filter">
          <span class="filter-label">Region</span>
          <el-select v-model="selectedRegionId" filterable placeholder="请选择 Region" @change="handleRegionChange">
            <el-option v-for="region in regions" :key="region.id" :label="region.name" :value="region.id" />
          </el-select>
        </div>
        <div v-else class="global-scope">
          <span>全局配置</span>
          <strong>交换机业务类型</strong>
        </div>
        <div v-if="activeTab !== 'types'" class="filter-field search-filter">
          <span class="filter-label">{{ searchLabel }}</span>
          <el-input
            v-model="search"
            clearable
            :placeholder="searchPlaceholder"
            :prefix-icon="Search"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
        </div>
        <div v-if="activeTab === 'switches'" class="filter-field compact-filter">
          <span class="filter-label">机柜</span>
          <el-select v-model="rackFilter" clearable placeholder="全部机柜" @change="handleSearch">
            <el-option v-for="rack in rackOptions" :key="rack.id" :label="rack.name" :value="rack.id" />
          </el-select>
        </div>
        <div v-if="activeTab === 'switches'" class="filter-field compact-filter">
          <span class="filter-label">交换机组</span>
          <el-select v-model="groupFilter" clearable placeholder="全部交换机组" @change="handleSearch">
            <el-option v-for="group in groupOptions" :key="group.id" :label="group.name" :value="group.id" />
          </el-select>
        </div>
        <div v-if="activeTab === 'groups'" class="filter-field compact-filter">
          <span class="filter-label">业务类型</span>
          <el-select v-model="businessTypeFilter" clearable placeholder="全部类型" @change="handleSearch">
            <el-option v-for="item in businessTypeOptions" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </div>
        <el-button v-if="activeTab !== 'types'" @click="handleSearch">查询</el-button>
      </div>
    </el-card>

    <el-alert
      v-if="readOnlyMessage"
      class="permission-alert"
      type="info"
      :closable="false"
      show-icon
      :title="readOnlyMessage"
    />

    <el-card shadow="never" class="workspace-card">
      <el-tabs v-model="activeTab" class="resource-tabs" @tab-change="handleTabChange">
        <el-tab-pane name="switches">
          <template #label><span class="tab-label"><el-icon><Operation /></el-icon>交换机</span></template>
          <el-table :data="switchRows" stripe border v-loading="loading" empty-text="暂无交换机">
            <el-table-column prop="name" label="交换机名称" min-width="180">
              <template #default="{ row }"><strong class="device-name">{{ row.name }}</strong></template>
            </el-table-column>
            <el-table-column label="上架位置" min-width="170">
              <template #default="{ row }">
                <div class="stacked-cell"><strong>{{ row.rack_name }}</strong><span>{{ formatURange(row.start_u, row.height_u) }}</span></div>
              </template>
            </el-table-column>
            <el-table-column label="交换机组" min-width="190">
              <template #default="{ row }">
                <div v-if="row.switch_group_name" class="stacked-cell">
                  <strong>{{ row.switch_group_name }}</strong>
                  <span>{{ row.business_type_name }} · {{ memberRoleLabel(row.member_role) }}</span>
                </div>
                <el-tag v-else size="small" type="info" effect="plain">未分组</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="端口速率" width="120" align="center">
              <template #default="{ row }">{{ formatPortSpeed(row.port_speed_mbps) }}</template>
            </el-table-column>
            <el-table-column label="端口使用" width="140" align="center">
              <template #default="{ row }">
                <button class="port-meter" type="button" @click="openPortDrawer(row)">
                  <span>{{ row.used_port_count }}/{{ row.port_count }}</span>
                  <i><b :style="{ width: portUsagePercent(row) }" /></i>
                </button>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="openPortDrawer(row)">端口</el-button>
                <template v-if="canManageSelectedRegion">
                  <el-button size="small" type="warning" link @click="openSwitchDialog(row)">编辑</el-button>
                  <el-button size="small" type="danger" link @click="handleDeleteSwitch(row)">删除</el-button>
                </template>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane name="groups">
          <template #label><span class="tab-label"><el-icon><Grid /></el-icon>交换机组</span></template>
          <el-table :data="groupRows" stripe border v-loading="loading" empty-text="暂无交换机组">
            <el-table-column prop="name" label="交换机组名称" min-width="210">
              <template #default="{ row }"><strong class="device-name">{{ row.name }}</strong></template>
            </el-table-column>
            <el-table-column prop="business_type_name" label="业务类型" min-width="150">
              <template #default="{ row }"><el-tag effect="plain">{{ row.business_type_name }}</el-tag></template>
            </el-table-column>
            <el-table-column label="组模式" width="120" align="center">
              <template #default="{ row }">{{ groupModeLabel(row.group_mode) }}</template>
            </el-table-column>
            <el-table-column label="成员" width="110" align="center">
              <template #default="{ row }">{{ row.member_count }}/{{ expectedMemberCount(row.group_mode) }}</template>
            </el-table-column>
            <el-table-column label="成员配置" width="140" align="center">
              <template #header>
                <span class="column-title-with-tip">
                  成员配置
                  <el-tooltip
                    content="表示成员配置是否完整：A/B 双机组需包含端口速率一致的 A、B 两台成员，单交换机组需包含一台成员；不表示端口存在、空闲或已经布线。"
                    placement="top"
                  >
                    <el-icon class="column-tip-icon" tabindex="0" aria-label="查看成员配置说明">
                      <InfoFilled />
                    </el-icon>
                  </el-tooltip>
                </span>
              </template>
              <template #default="{ row }">
                <span class="group-status-cell">
                  <el-tag :type="row.is_member_config_ready ? 'success' : 'warning'" effect="light">
                    {{ row.is_member_config_ready ? '成员配置完整' : '配置未完整' }}
                  </el-tag>
                  <el-tooltip v-if="!row.is_member_config_ready" placement="top">
                    <template #content>
                      <div v-for="issue in row.readiness_issues" :key="issue.code">
                        {{ issue.message }}
                      </div>
                    </template>
                    <el-icon class="status-tip-icon" tabindex="0" aria-label="查看配置未完整原因">
                      <InfoFilled />
                    </el-icon>
                  </el-tooltip>
                </span>
              </template>
            </el-table-column>
            <el-table-column v-if="canManageSelectedRegion" label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="warning" link @click="openGroupDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" link @click="handleDeleteGroup(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane name="types">
          <template #label><span class="tab-label"><el-icon><CollectionTag /></el-icon>业务类型</span></template>
          <el-table :data="businessTypeRows" stripe border v-loading="loading" empty-text="暂无业务类型">
            <el-table-column prop="name" label="显示名称" min-width="200">
              <template #default="{ row }"><strong class="device-name">{{ row.name }}</strong></template>
            </el-table-column>
            <el-table-column prop="code" label="技术标识" min-width="180">
              <template #default="{ row }"><code class="code-badge">{{ row.code }}</code></template>
            </el-table-column>
            <el-table-column prop="updated_at" label="更新时间" width="175">
              <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
            </el-table-column>
            <el-table-column v-if="appStore.isAdministrator" label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="warning" link @click="openBusinessTypeDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" link @click="handleDeleteBusinessType(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        class="table-pagination"
        @current-change="fetchActiveData"
      />
    </el-card>

    <el-dialog
      v-model="createGroupDialogVisible"
      title="添加交换机组"
      width="920px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="createGroupFormRef" :model="createGroupForm" :rules="createGroupRules" label-position="top">
        <section class="create-section member-section">
          <div class="section-heading">
            <span>01</span>
            <div><strong>成员交换机</strong><small>填写交换机信息</small></div>
          </div>
          <div class="member-settings">
            <el-form-item label="组模式" prop="group_mode">
              <el-radio-group v-model="createGroupForm.group_mode" @change="handleCreateGroupModeChange">
                <el-radio-button value="pair">A/B 双机</el-radio-button>
                <el-radio-button value="single">单交换机</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="端口速率" prop="port_speed_mbps">
              <el-select v-model="createGroupForm.port_speed_mbps">
                <el-option v-for="speed in portSpeeds" :key="speed" :label="formatPortSpeed(speed)" :value="speed" />
              </el-select>
            </el-form-item>
            <el-form-item label="板卡号" required>
              <el-input-number
                v-model="createGroupForm.port_range.card_number"
                :min="0"
                controls-position="right"
              />
            </el-form-item>
            <el-form-item label="子板卡号" required>
              <el-input-number
                v-model="createGroupForm.port_range.subcard_number"
                :min="0"
                controls-position="right"
              />
            </el-form-item>
            <el-form-item label="端口编号范围" required>
              <div class="create-port-range">
                <el-input-number
                  v-model="createGroupForm.port_range.start_port_number"
                  :min="1"
                  controls-position="right"
                />
                <span>至</span>
                <el-input-number
                  v-model="createGroupForm.port_range.end_port_number"
                  :min="1"
                  controls-position="right"
                />
              </div>
            </el-form-item>
          </div>
          <div class="member-cards" :class="{ 'is-single': createGroupForm.group_mode === 'single' }">
            <article v-for="(member, index) in createGroupForm.members" :key="member.member_role" class="member-card">
              <header>
                <span class="member-role">{{ memberRoleLabel(member.member_role) }}</span>
                <small>{{ member.member_role === 'single' ? '单机成员' : `${member.member_role.toUpperCase()} 角色` }}</small>
              </header>
              <div class="member-form-grid">
                <el-form-item
                  label="交换机名称"
                  :prop="`members.${index}.name`"
                  :rules="[{ required: true, message: '请输入交换机名称', trigger: 'blur' }]"
                  class="member-full-row"
                >
                  <el-input
                    v-model="member.name"
                    maxlength="100"
                    :placeholder="`例如：业务交换机-01-${member.member_role.toUpperCase()}`"
                    @input="refreshDefaultGroupName"
                  />
                </el-form-item>
                <el-form-item
                  label="上架机柜"
                  :prop="`members.${index}.rack_id`"
                  :rules="[{ required: true, message: '请选择上架机柜', trigger: 'change' }]"
                  class="member-full-row"
                >
                  <el-select v-model="member.rack_id" filterable placeholder="选择机柜">
                    <el-option v-for="rack in rackOptions" :key="rack.id" :label="rack.name" :value="rack.id" />
                  </el-select>
                </el-form-item>
                <el-form-item
                  label="起始 U 位"
                  :prop="`members.${index}.start_u`"
                  :rules="[{ required: true, message: '请输入起始 U 位', trigger: 'change' }]"
                >
                  <el-input-number v-model="member.start_u" :min="1" controls-position="right" />
                </el-form-item>
                <el-form-item
                  label="占用 U 数"
                  :prop="`members.${index}.height_u`"
                  :rules="[{ required: true, message: '请输入占用 U 数', trigger: 'change' }]"
                >
                  <el-input-number v-model="member.height_u" :min="1" controls-position="right" />
                </el-form-item>
              </div>
            </article>
          </div>
        </section>

        <section class="create-section">
          <div class="section-heading">
            <span>02</span>
            <div><strong>交换机组信息</strong><small>确认交换机组名称和业务归属</small></div>
          </div>
          <div class="group-create-grid">
            <el-form-item label="交换机组名称" prop="name">
              <el-input
                v-model="createGroupForm.name"
                maxlength="100"
                placeholder="根据成员交换机名称自动生成"
                @input="handleGroupNameInput"
              />
            </el-form-item>
            <el-form-item label="业务类型" prop="business_type_id">
              <el-select v-model="createGroupForm.business_type_id" filterable placeholder="选择业务类型">
                <el-option v-for="item in businessTypeOptions" :key="item.id" :label="item.name" :value="item.id" />
              </el-select>
            </el-form-item>
          </div>
        </section>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="createGroupDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreateGroup">创建交换机组</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="switchDialogVisible" title="编辑交换机" width="640px" :close-on-click-modal="false">
      <el-form ref="switchFormRef" :model="switchForm" :rules="switchRules" label-width="110px">
        <div class="form-grid">
          <el-form-item label="交换机名称" prop="name" class="full-row">
            <el-input v-model="switchForm.name" maxlength="100" placeholder="例如：BJ-A01-BIZ-SW-A" />
          </el-form-item>
          <el-form-item label="上架机柜" prop="rack_id">
            <el-select v-model="switchForm.rack_id" filterable placeholder="选择机柜">
              <el-option v-for="rack in rackOptions" :key="rack.id" :label="rack.name" :value="rack.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="端口速率" prop="port_speed_mbps">
            <el-select v-model="switchForm.port_speed_mbps">
              <el-option v-for="speed in portSpeeds" :key="speed" :label="formatPortSpeed(speed)" :value="speed" />
            </el-select>
          </el-form-item>
          <el-form-item label="起始 U 位" prop="start_u">
            <el-input-number v-model="switchForm.start_u" :min="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="占用 U 数" prop="height_u">
            <el-input-number v-model="switchForm.height_u" :min="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="交换机组" prop="switch_group_id">
            <el-select v-model="switchForm.switch_group_id" clearable placeholder="可暂不分组" @change="handleSwitchGroupChange">
              <el-option v-for="group in groupOptions" :key="group.id" :label="group.name" :value="group.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="组内角色" prop="member_role">
            <el-select v-model="switchForm.member_role" clearable :disabled="!switchForm.switch_group_id" placeholder="选择角色">
              <el-option v-for="role in availableMemberRoles" :key="role.value" :label="role.label" :value="role.value" />
            </el-select>
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="switchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitSwitch">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="groupDialogVisible" title="编辑交换机组" width="540px" :close-on-click-modal="false">
      <el-form ref="groupFormRef" :model="groupForm" :rules="groupRules" label-width="110px">
        <el-form-item label="交换机组名称" prop="name">
          <el-input v-model="groupForm.name" maxlength="100" placeholder="例如：业务交换机对-01" />
        </el-form-item>
        <el-form-item label="业务类型" prop="business_type_id">
          <el-select v-model="groupForm.business_type_id" filterable placeholder="选择业务类型">
            <el-option v-for="item in businessTypeOptions" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="组模式" prop="group_mode">
          <el-radio-group v-model="groupForm.group_mode" :disabled="Boolean(editingGroup?.member_count)">
            <el-radio-button value="pair">A/B 双机</el-radio-button>
            <el-radio-button value="single">单交换机</el-radio-button>
          </el-radio-group>
          <div v-if="editingGroup?.member_count" class="form-tip">已有成员时不能修改组模式</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="groupDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitGroup">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="businessTypeDialogVisible" :title="editingBusinessType ? '编辑业务类型' : '添加业务类型'" width="520px" :close-on-click-modal="false">
      <el-form ref="businessTypeFormRef" :model="businessTypeForm" :rules="businessTypeRules" label-width="100px">
        <el-form-item label="显示名称" prop="name">
          <el-input v-model="businessTypeForm.name" maxlength="100" placeholder="例如：高性能计算" />
        </el-form-item>
        <el-form-item label="技术标识" prop="code">
          <el-input v-model="businessTypeForm.code" maxlength="50" placeholder="例如：hpc" />
          <div class="form-tip">用于接口和导入导出，建议使用稳定的英文标识</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="businessTypeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitBusinessType">确定</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="portDrawerVisible" size="560px" destroy-on-close>
      <template #header>
        <div class="drawer-heading">
          <span class="drawer-kicker">物理端口</span>
          <strong>{{ selectedSwitch?.name || '-' }}</strong>
          <small>{{ selectedSwitch?.rack_name }} · {{ selectedSwitch ? formatPortSpeed(selectedSwitch.port_speed_mbps) : '' }}</small>
        </div>
      </template>

      <div v-if="canManageSelectedRegion" class="port-create-panel">
        <div>
          <strong>批量生成端口</strong>
          <span>连续编号原子创建，遇到重复编号时整批取消</span>
        </div>
        <div class="port-range">
          <label class="port-field">
            <span>板卡号</span>
            <el-input-number
              v-model="portForm.card_number"
              :min="0"
              controls-position="right"
              @change="refreshPortRangeSuggestion"
            />
          </label>
          <label class="port-field">
            <span>子板卡号</span>
            <el-input-number
              v-model="portForm.subcard_number"
              :min="0"
              controls-position="right"
              @change="refreshPortRangeSuggestion"
            />
          </label>
          <label class="port-field">
            <span>起始端口</span>
            <el-input-number v-model="portForm.start_port_number" :min="1" controls-position="right" />
          </label>
          <label class="port-field">
            <span>结束端口</span>
            <el-input-number v-model="portForm.end_port_number" :min="1" controls-position="right" />
          </label>
          <el-button type="primary" :loading="portSubmitting" @click="submitPorts">生成</el-button>
        </div>
      </div>

      <el-table :data="ports" stripe border v-loading="portLoading" empty-text="暂无端口">
        <el-table-column label="接口名称" min-width="180">
          <template #default="{ row }"><code class="port-code">{{ formatPhysicalPortName(row) }}</code></template>
        </el-table-column>
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_occupied ? 'danger' : 'success'" effect="light">
              {{ row.is_occupied ? '已占用' : '空闲' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="canManageSelectedRegion" label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button size="small" type="danger" link :disabled="row.is_occupied" @click="handleDeletePort(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="portTotal > 0"
        v-model:current-page="portPage"
        :page-size="portPageSize"
        :total="portTotal"
        layout="total, prev, pager, next"
        class="table-pagination"
        @current-change="fetchPorts"
      />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { fetchRacks } from '@/api/racks'
import { fetchRegions } from '@/api/regions'
import {
  createSwitchBusinessType,
  createSwitchGroupWithMembers,
  createSwitchPortsBulk,
  deleteSwitch,
  deleteSwitchBusinessType,
  deleteSwitchGroup,
  deleteSwitchPort,
  fetchSwitchBusinessTypes,
  fetchSwitchGroups,
  fetchSwitchPorts,
  fetchSwitches,
  updateSwitch,
  updateSwitchBusinessType,
  updateSwitchGroup,
} from '@/api/switches'
import { useAppStore } from '@/stores/app'
import type {
  EntityId,
  NetworkSwitch,
  Rack,
  Region,
  SwitchBusinessType,
  SwitchBusinessTypeCreatePayload,
  SwitchFormData,
  SwitchGroup,
  SwitchGroupCreatePayload,
  SwitchGroupMemberCreatePayload,
  SwitchGroupMode,
  SwitchMemberRole,
  SwitchPort,
  SwitchPortBulkCreatePayload,
} from '@/types'
import { formatDateTime } from '@/utils/time'
import { CollectionTag, Grid, InfoFilled, Operation, Plus, Search } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

type ResourceTab = 'switches' | 'groups' | 'types'

interface SwitchGroupEditForm {
  business_type_id: EntityId
  name: string
  group_mode: SwitchGroupMode
}

type SwitchGroupMemberCreateForm = Omit<SwitchGroupMemberCreatePayload, 'port_speed_mbps'>

interface SwitchGroupCreateForm extends Omit<SwitchGroupCreatePayload, 'members'> {
  port_speed_mbps: number
  members: SwitchGroupMemberCreateForm[]
}

const appStore = useAppStore()
const activeTab = ref<ResourceTab>('switches')
const regions = ref<Region[]>([])
const selectedRegionId = ref<EntityId>('')
const search = ref('')
const rackFilter = ref<EntityId>('')
const groupFilter = ref<EntityId>('')
const businessTypeFilter = ref<EntityId>('')
const rackOptions = ref<Rack[]>([])
const groupOptions = ref<SwitchGroup[]>([])
const businessTypeOptions = ref<SwitchBusinessType[]>([])
const switchRows = ref<NetworkSwitch[]>([])
const groupRows = ref<SwitchGroup[]>([])
const businessTypeRows = ref<SwitchBusinessType[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const submitting = ref(false)

const createGroupDialogVisible = ref(false)
const createGroupFormRef = ref<FormInstance>()
const createGroupForm = ref<SwitchGroupCreateForm>(blankCreateGroupForm())
const groupNameManuallyEdited = ref(false)
const switchDialogVisible = ref(false)
const editingSwitch = ref<NetworkSwitch | null>(null)
const switchFormRef = ref<FormInstance>()
const switchForm = ref<SwitchFormData>(blankSwitchForm())
const groupDialogVisible = ref(false)
const editingGroup = ref<SwitchGroup | null>(null)
const groupFormRef = ref<FormInstance>()
const groupForm = ref<SwitchGroupEditForm>(blankGroupEditForm())
const businessTypeDialogVisible = ref(false)
const editingBusinessType = ref<SwitchBusinessType | null>(null)
const businessTypeFormRef = ref<FormInstance>()
const businessTypeForm = ref<SwitchBusinessTypeCreatePayload>({ code: '', name: '' })

const portDrawerVisible = ref(false)
const selectedSwitch = ref<NetworkSwitch | null>(null)
const ports = ref<SwitchPort[]>([])
const portLoading = ref(false)
const portSubmitting = ref(false)
const portTotal = ref(0)
const portPage = ref(1)
const portPageSize = 100
const portForm = ref<SwitchPortBulkCreatePayload>({
  card_number: 1,
  subcard_number: 0,
  start_port_number: 1,
  end_port_number: 48,
})
const portSpeeds = [1000, 10000, 25000, 40000, 100000]
// 与后端校验保持一致，用于在提交前提示端口范围超限。
const MAX_SWITCH_PORT_BATCH_SIZE = 128
let portSuggestionRequestVersion = 0

const canManageSelectedRegion = computed(
  () => Boolean(selectedRegionId.value) && appStore.canManageRegionBusiness(selectedRegionId.value)
)
const showPrimaryAction = computed(() =>
  activeTab.value === 'types' ? appStore.isAdministrator : canManageSelectedRegion.value
)
const primaryActionLabel = computed(() => activeTab.value === 'types' ? '添加业务类型' : '添加交换机组')
const searchLabel = computed(() => activeTab.value === 'switches' ? '交换机名称' : '交换机组名称')
const searchPlaceholder = computed(() => `输入${searchLabel.value}搜索`)
const readOnlyMessage = computed(() => {
  if (activeTab.value === 'types') {
    return appStore.isAdministrator ? '' : '交换机业务类型为全局配置，当前账号只能查看。'
  }
  if (!selectedRegionId.value || canManageSelectedRegion.value) return ''
  return '当前 Region 为只读模式；只有获得该 Region 授权的普通用户可修改交换机资源。'
})
const selectedFormGroup = computed(() =>
  groupOptions.value.find((group) => group.id === switchForm.value.switch_group_id)
)
const availableMemberRoles = computed<{ label: string; value: SwitchMemberRole }[]>(() => {
  if (selectedFormGroup.value?.group_mode === 'single') return [{ label: '单机', value: 'single' }]
  if (selectedFormGroup.value?.group_mode === 'pair') return [{ label: 'A 机', value: 'a' }, { label: 'B 机', value: 'b' }]
  return []
})

const switchRules: FormRules<SwitchFormData> = {
  name: [{ required: true, message: '请输入交换机名称', trigger: 'blur' }],
  rack_id: [{ required: true, message: '请选择上架机柜', trigger: 'change' }],
  port_speed_mbps: [{ required: true, message: '请选择端口速率', trigger: 'change' }],
  start_u: [{ required: true, message: '请输入起始 U 位', trigger: 'change' }],
  height_u: [{ required: true, message: '请输入占用 U 数', trigger: 'change' }],
}
const groupRules: FormRules<SwitchGroupEditForm> = {
  name: [{ required: true, message: '请输入交换机组名称', trigger: 'blur' }],
  business_type_id: [{ required: true, message: '请选择业务类型', trigger: 'change' }],
  group_mode: [{ required: true, message: '请选择组模式', trigger: 'change' }],
}
const createGroupRules: FormRules<SwitchGroupCreateForm> = {
  name: [
    { required: true, message: '请输入交换机组名称', trigger: 'blur' },
    { max: 100, message: '交换机组名称不能超过 100 个字符', trigger: 'change' },
  ],
  business_type_id: [{ required: true, message: '请选择业务类型', trigger: 'change' }],
  group_mode: [{ required: true, message: '请选择组模式', trigger: 'change' }],
  port_speed_mbps: [{ required: true, message: '请选择端口速率', trigger: 'change' }],
}
const businessTypeRules: FormRules<SwitchBusinessTypeCreatePayload> = {
  name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入技术标识', trigger: 'blur' }],
}

async function initialize() {
  const [regionResponse, typeResponse] = await Promise.all([
    fetchRegions({ skip: 0, limit: 500 }),
    fetchSwitchBusinessTypes({ skip: 0, limit: 500 }),
  ])
  regions.value = regionResponse.items
  businessTypeOptions.value = typeResponse.items
  const preferredRegion = regions.value.find((region) => appStore.canManageRegionBusiness(region.id)) || regions.value[0]
  selectedRegionId.value = preferredRegion?.id || ''
  await refreshRegionOptions()
  await fetchActiveData()
}

async function refreshRegionOptions() {
  if (!selectedRegionId.value) {
    rackOptions.value = []
    groupOptions.value = []
    return
  }
  const [rackResponse, groupResponse] = await Promise.all([
    fetchRacks(selectedRegionId.value, { skip: 0, limit: 500 }),
    fetchSwitchGroups(selectedRegionId.value, { skip: 0, limit: 500 }),
  ])
  rackOptions.value = rackResponse.items
  groupOptions.value = groupResponse.items
}

async function refreshBusinessTypeOptions() {
  const response = await fetchSwitchBusinessTypes({ skip: 0, limit: 500 })
  businessTypeOptions.value = response.items
}

async function fetchActiveData() {
  loading.value = true
  try {
    const pagination = { skip: (page.value - 1) * pageSize.value, limit: pageSize.value }
    if (activeTab.value === 'types') {
      const response = await fetchSwitchBusinessTypes(pagination)
      businessTypeRows.value = response.items
      total.value = response.total
      return
    }
    const common = { ...pagination, search: search.value.trim() || undefined }
    if (!selectedRegionId.value) {
      total.value = 0
      switchRows.value = []
      groupRows.value = []
      return
    }
    if (activeTab.value === 'groups') {
      const response = await fetchSwitchGroups(selectedRegionId.value, {
        ...common,
        business_type_id: businessTypeFilter.value || undefined,
      })
      groupRows.value = response.items
      total.value = response.total
      return
    }
    const response = await fetchSwitches(selectedRegionId.value, {
      ...common,
      rack_id: rackFilter.value || undefined,
      switch_group_id: groupFilter.value || undefined,
    })
    switchRows.value = response.items
    total.value = response.total
  } finally {
    loading.value = false
  }
}

async function handleRegionChange() {
  page.value = 1
  rackFilter.value = ''
  groupFilter.value = ''
  await refreshRegionOptions()
  await fetchActiveData()
}

function handleSearch() {
  page.value = 1
  fetchActiveData()
}

function handleTabChange() {
  page.value = 1
  search.value = ''
  total.value = 0
  fetchActiveData()
}

function handlePrimaryAction() {
  if (activeTab.value === 'types') openBusinessTypeDialog()
  else openCreateGroupDialog()
}

function openCreateGroupDialog() {
  createGroupForm.value = blankCreateGroupForm()
  groupNameManuallyEdited.value = false
  createGroupDialogVisible.value = true
}

function handleCreateGroupModeChange(mode: SwitchGroupMode) {
  createGroupForm.value.members = mode === 'pair'
    ? [blankCreateMember('a'), blankCreateMember('b')]
    : [blankCreateMember('single')]
  refreshDefaultGroupName()
  createGroupFormRef.value?.clearValidate('members')
}

function handleGroupNameInput() {
  groupNameManuallyEdited.value = true
}

function refreshDefaultGroupName() {
  if (groupNameManuallyEdited.value) return
  const names = createGroupForm.value.members.map((member) => member.name.trim())
  createGroupForm.value.name = createGroupForm.value.group_mode === 'pair'
    ? (names[0] && names[1] ? `${names[0]}/${names[1]}` : '')
    : (names[0] || '')
  createGroupFormRef.value?.clearValidate('name')
}

async function submitCreateGroup() {
  const valid = await createGroupFormRef.value?.validate().catch(() => false)
  if (!valid || !selectedRegionId.value) return
  const portRange = createGroupForm.value.port_range
  if (portRange.end_port_number < portRange.start_port_number) {
    ElMessage.warning('端口结束编号不能小于起始编号')
    return
  }
  if (portRange.end_port_number - portRange.start_port_number + 1 > MAX_SWITCH_PORT_BATCH_SIZE) {
    ElMessage.warning(`一次最多生成 ${MAX_SWITCH_PORT_BATCH_SIZE} 个端口`)
    return
  }
  submitting.value = true
  try {
    const form = createGroupForm.value
    const payload: SwitchGroupCreatePayload = {
      business_type_id: form.business_type_id,
      name: form.name,
      group_mode: form.group_mode,
      members: form.members.map((member) => ({ ...member, port_speed_mbps: form.port_speed_mbps })),
      port_range: { ...form.port_range },
    }
    const result = await createSwitchGroupWithMembers(selectedRegionId.value, payload)
    ElMessage.success(`已创建交换机组及 ${result.members.length} 台交换机`)
    createGroupDialogVisible.value = false
    await Promise.all([refreshRegionOptions(), fetchActiveData()])
  } finally {
    submitting.value = false
  }
}

function openSwitchDialog(item: NetworkSwitch) {
  editingSwitch.value = item
  switchForm.value = {
    rack_id: item.rack_id,
    switch_group_id: item.switch_group_id || null,
    member_role: item.member_role || null,
    name: item.name,
    port_speed_mbps: item.port_speed_mbps,
    start_u: item.start_u,
    height_u: item.height_u,
  }
  switchDialogVisible.value = true
}

function handleSwitchGroupChange(groupId?: EntityId) {
  const group = groupOptions.value.find((item) => item.id === groupId)
  if (!group) switchForm.value.member_role = null
  else switchForm.value.member_role = group.group_mode === 'single' ? 'single' : 'a'
}

async function submitSwitch() {
  const valid = await switchFormRef.value?.validate().catch(() => false)
  if (!valid || !selectedRegionId.value) return
  if (switchForm.value.switch_group_id && !switchForm.value.member_role) {
    ElMessage.warning('请选择交换机组内角色')
    return
  }
  submitting.value = true
  try {
    if (!editingSwitch.value) return
    await updateSwitch(selectedRegionId.value, editingSwitch.value.id, switchForm.value)
    ElMessage.success('交换机已更新')
    switchDialogVisible.value = false
    await Promise.all([fetchActiveData(), refreshRegionOptions()])
  } finally {
    submitting.value = false
  }
}

function openGroupDialog(item: SwitchGroup) {
  editingGroup.value = item
  groupForm.value = { business_type_id: item.business_type_id, name: item.name, group_mode: item.group_mode }
  groupDialogVisible.value = true
}

async function submitGroup() {
  const valid = await groupFormRef.value?.validate().catch(() => false)
  if (!valid || !selectedRegionId.value) return
  submitting.value = true
  try {
    if (!editingGroup.value) return
    await updateSwitchGroup(selectedRegionId.value, editingGroup.value.id, groupForm.value)
    ElMessage.success('交换机组已更新')
    groupDialogVisible.value = false
    await Promise.all([refreshRegionOptions(), fetchActiveData()])
  } finally {
    submitting.value = false
  }
}

function openBusinessTypeDialog(item?: SwitchBusinessType) {
  editingBusinessType.value = item || null
  businessTypeForm.value = item ? { code: item.code, name: item.name } : { code: '', name: '' }
  businessTypeDialogVisible.value = true
}

async function submitBusinessType() {
  const valid = await businessTypeFormRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (editingBusinessType.value) {
      await updateSwitchBusinessType(editingBusinessType.value.id, businessTypeForm.value)
      ElMessage.success('业务类型已更新')
    } else {
      await createSwitchBusinessType(businessTypeForm.value)
      ElMessage.success('业务类型已创建')
    }
    businessTypeDialogVisible.value = false
    await Promise.all([refreshBusinessTypeOptions(), fetchActiveData()])
  } finally {
    submitting.value = false
  }
}

async function handleDeleteSwitch(item: NetworkSwitch) {
  if (item.used_port_count) {
    ElMessage.warning(`交换机 ${item.name} 仍有 ${item.used_port_count} 个端口已被线缆占用`)
    return
  }
  const confirmed = await confirmDelete(`确定删除交换机“${item.name}”及其 ${item.port_count} 个未占用端口吗？`, '删除交换机')
  if (!confirmed) return
  await deleteSwitch(selectedRegionId.value, item.id)
  ElMessage.success('交换机已删除')
  await Promise.all([fetchActiveData(), refreshRegionOptions()])
}

async function handleDeleteGroup(item: SwitchGroup) {
  if (item.member_count) {
    ElMessage.warning(`交换机组 ${item.name} 仍有 ${item.member_count} 台交换机，不能删除`)
    return
  }
  const confirmed = await confirmDelete(`确定删除交换机组“${item.name}”吗？`, '删除交换机组')
  if (!confirmed) return
  await deleteSwitchGroup(selectedRegionId.value, item.id)
  ElMessage.success('交换机组已删除')
  await Promise.all([refreshRegionOptions(), fetchActiveData()])
}

async function handleDeleteBusinessType(item: SwitchBusinessType) {
  const confirmed = await confirmDelete(`确定删除业务类型“${item.name}”吗？`, '删除业务类型')
  if (!confirmed) return
  await deleteSwitchBusinessType(item.id)
  ElMessage.success('业务类型已删除')
  await Promise.all([refreshBusinessTypeOptions(), fetchActiveData()])
}

async function openPortDrawer(item: NetworkSwitch) {
  selectedSwitch.value = item
  portPage.value = 1
  portForm.value = { card_number: 1, subcard_number: 0, start_port_number: 1, end_port_number: 48 }
  portDrawerVisible.value = true
  await Promise.all([fetchPorts(), refreshPortRangeSuggestion()])
}

async function fetchPorts() {
  if (!selectedSwitch.value || !selectedRegionId.value) return
  portLoading.value = true
  try {
    const response = await fetchSwitchPorts(selectedRegionId.value, selectedSwitch.value.id, {
      skip: (portPage.value - 1) * portPageSize,
      limit: portPageSize,
    })
    ports.value = response.items
    portTotal.value = response.total
  } finally {
    portLoading.value = false
  }
}

async function submitPorts() {
  if (!selectedSwitch.value) return
  if (portForm.value.end_port_number < portForm.value.start_port_number) {
    ElMessage.warning('端口结束编号不能小于起始编号')
    return
  }
  if (portForm.value.end_port_number - portForm.value.start_port_number + 1 > MAX_SWITCH_PORT_BATCH_SIZE) {
    ElMessage.warning(`一次最多生成 ${MAX_SWITCH_PORT_BATCH_SIZE} 个端口`)
    return
  }
  portSubmitting.value = true
  try {
    await createSwitchPortsBulk(selectedRegionId.value, selectedSwitch.value.id, portForm.value)
    ElMessage.success('交换机端口已生成')
    await Promise.all([fetchPorts(), fetchActiveData(), refreshPortRangeSuggestion()])
  } finally {
    portSubmitting.value = false
  }
}

async function refreshPortRangeSuggestion() {
  if (!selectedSwitch.value || !selectedRegionId.value) return
  const requestVersion = ++portSuggestionRequestVersion
  const regionId = selectedRegionId.value
  const switchId = selectedSwitch.value.id
  const cardNumber = portForm.value.card_number
  const subcardNumber = portForm.value.subcard_number
  const firstPage = await fetchSwitchPorts(regionId, switchId, {
    skip: 0,
    limit: 1,
    card_number: cardNumber,
    subcard_number: subcardNumber,
  })
  let lastPort = firstPage.items[0]
  if (firstPage.total > 1) {
    const lastPage = await fetchSwitchPorts(regionId, switchId, {
      skip: firstPage.total - 1,
      limit: 1,
      card_number: cardNumber,
      subcard_number: subcardNumber,
    })
    lastPort = lastPage.items[0]
  }
  if (
    requestVersion !== portSuggestionRequestVersion
    || selectedSwitch.value?.id !== switchId
    || portForm.value.card_number !== cardNumber
    || portForm.value.subcard_number !== subcardNumber
  ) return
  const nextPortNumber = (lastPort?.port_number || 0) + 1
  portForm.value.start_port_number = nextPortNumber
  portForm.value.end_port_number = nextPortNumber + 47
}

async function handleDeletePort(item: SwitchPort) {
  if (!selectedSwitch.value || item.is_occupied) return
  const confirmed = await confirmDelete(`确定删除端口 ${formatPhysicalPortName(item)} 吗？`, '删除端口')
  if (!confirmed) return
  await deleteSwitchPort(selectedRegionId.value, selectedSwitch.value.id, item.id)
  ElMessage.success('端口已删除')
  if (ports.value.length === 1 && portPage.value > 1) portPage.value -= 1
  await Promise.all([fetchPorts(), fetchActiveData(), refreshPortRangeSuggestion()])
}

async function confirmDelete(message: string, title: string) {
  try {
    await ElMessageBox.confirm(message, title, { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
    return true
  } catch {
    return false
  }
}

function blankSwitchForm(): SwitchFormData {
  return { rack_id: '', switch_group_id: null, member_role: null, name: '', port_speed_mbps: 25000, start_u: 42, height_u: 1 }
}

function blankGroupEditForm(): SwitchGroupEditForm {
  return { business_type_id: businessTypeOptions.value[0]?.id || '', name: '', group_mode: 'pair' }
}

function blankCreateGroupForm(): SwitchGroupCreateForm {
  return {
    ...blankGroupEditForm(),
    port_speed_mbps: 25000,
    port_range: { card_number: 1, subcard_number: 0, start_port_number: 1, end_port_number: 48 },
    members: [blankCreateMember('a'), blankCreateMember('b')],
  }
}

function blankCreateMember(memberRole: SwitchMemberRole): SwitchGroupMemberCreateForm {
  return {
    rack_id: '',
    member_role: memberRole,
    name: '',
    start_u: 42,
    height_u: 1,
  }
}

function groupModeLabel(mode: SwitchGroup['group_mode']) {
  return mode === 'pair' ? 'A/B 双机' : '单交换机'
}

function expectedMemberCount(mode: SwitchGroup['group_mode']) {
  return mode === 'pair' ? 2 : 1
}

function memberRoleLabel(role?: SwitchMemberRole | null) {
  return ({ a: 'A 机', b: 'B 机', single: '单机' } as const)[role || 'single']
}

function formatPortSpeed(speed: number) {
  if (speed >= 1000 && speed % 1000 === 0) return `${speed / 1000}GE`
  return `${speed} Mbps`
}

function formatPhysicalPortName(port: SwitchPort) {
  const speed = selectedSwitch.value ? formatPortSpeed(selectedSwitch.value.port_speed_mbps) : ''
  return `${speed}${port.card_number}/${port.subcard_number}/${port.port_number}`
}

function formatURange(startU: number, heightU: number) {
  const endU = startU + heightU - 1
  return startU === endU ? `${startU}U` : `${startU}U-${endU}U`
}

function portUsagePercent(item: NetworkSwitch) {
  if (!item.port_count) return '0%'
  return `${Math.min(100, Math.round((item.used_port_count / item.port_count) * 100))}%`
}

onMounted(initialize)
</script>

<style scoped>
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: var(--spacing-lg); }
.page-title { margin: 0; color: var(--color-text-primary); font-size: var(--font-size-xl); font-weight: 700; }
.page-desc { margin-top: 4px; color: var(--color-text-tertiary); font-size: var(--font-size-sm); }
.filter-card, .permission-alert { margin-bottom: var(--spacing-md); }
.filter-row { display: flex; align-items: flex-end; gap: 12px; flex-wrap: wrap; }
.filter-field { display: flex; flex-direction: column; gap: 6px; }
.filter-label { color: var(--color-text-secondary); font-size: var(--font-size-xs); font-weight: 600; }
.region-filter { width: 240px; }
.search-filter { width: 250px; }
.compact-filter { width: 190px; }
.global-scope { display: flex; width: 240px; min-height: 54px; flex-direction: column; justify-content: center; padding: 6px 12px; border-left: 3px solid var(--color-primary); background: #f7faff; }
.global-scope span { color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.global-scope strong { color: var(--color-text-primary); font-size: var(--font-size-sm); }
.workspace-card :deep(.el-card__body) { padding-top: 10px; }
.resource-tabs :deep(.el-tabs__header) { margin-bottom: 18px; }
.tab-label { display: inline-flex; align-items: center; gap: 6px; padding: 0 4px; }
.device-name { color: var(--color-text-primary); font-weight: 600; }
.stacked-cell { display: flex; flex-direction: column; line-height: 1.45; }
.stacked-cell strong { font-weight: 600; }
.stacked-cell span { color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.port-meter { display: inline-flex; min-width: 86px; flex-direction: column; gap: 4px; padding: 0; border: 0; background: transparent; color: var(--color-primary); cursor: pointer; font: inherit; font-weight: 600; }
.port-meter i { display: block; width: 100%; height: 4px; overflow: hidden; border-radius: 2px; background: #e7edf5; }
.port-meter b { display: block; height: 100%; border-radius: inherit; background: var(--color-primary); }
.code-badge, .port-code { padding: 3px 7px; border: 1px solid #dce5ef; border-radius: 5px; background: #f6f8fb; color: #334155; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
.column-title-with-tip { display: inline-flex; align-items: center; gap: 4px; }
.column-tip-icon { color: var(--color-text-tertiary); cursor: help; font-size: 14px; outline: none; }
.column-tip-icon:hover, .column-tip-icon:focus-visible { color: var(--color-primary); }
.group-status-cell { display: inline-flex; align-items: center; gap: 6px; }
.status-tip-icon { color: var(--el-color-warning); cursor: help; font-size: 15px; outline: none; }
.status-tip-icon:hover, .status-tip-icon:focus-visible { color: var(--el-color-warning-dark-2); }
.table-pagination { margin-top: 16px; justify-content: flex-end; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 14px; }
.full-row { grid-column: 1 / -1; }
.form-grid :deep(.el-select), .form-grid :deep(.el-input-number) { width: 100%; }
.form-tip { margin-top: 5px; color: var(--color-text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.create-section { padding: 18px; border: 1px solid var(--color-border); border-radius: var(--radius-lg); background: #fbfcfe; }
.create-section + .create-section { margin-top: 16px; }
.section-heading { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.section-heading > span { display: inline-flex; width: 28px; height: 28px; flex: 0 0 auto; align-items: center; justify-content: center; border-radius: 8px; background: var(--color-primary-lighter); color: var(--color-primary); font-size: 11px; font-weight: 800; }
.section-heading > div { display: flex; flex-direction: column; gap: 2px; }
.section-heading strong { color: var(--color-text-primary); font-size: var(--font-size-sm); }
.section-heading small { color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.group-create-grid { display: grid; grid-template-columns: minmax(260px, 1.4fr) minmax(220px, 1fr); gap: 0 14px; }
.group-create-grid :deep(.el-select) { width: 100%; }
.member-section { background: #f7faff; }
.member-settings { display: grid; grid-template-columns: minmax(185px, 1fr) minmax(130px, .7fr) minmax(105px, .55fr) minmax(115px, .6fr) minmax(220px, 1.15fr); gap: 0 12px; margin-bottom: 2px; }
.member-settings :deep(.el-select), .member-settings :deep(.el-input-number) { width: 100%; }
.create-port-range { display: flex; width: 100%; align-items: center; gap: 8px; }
.create-port-range span { flex: 0 0 auto; color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.create-port-range :deep(.el-input-number) { width: 100%; }
.member-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.member-cards.is-single { grid-template-columns: minmax(0, 1fr); }
.member-card { padding: 16px; border: 1px solid #d9e5f4; border-radius: var(--radius-md); background: #fff; }
.member-card > header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.member-card > header small { color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.member-role { display: inline-flex; align-items: center; padding: 4px 9px; border-radius: 6px; background: #eaf2fd; color: var(--color-primary-dark); font-size: var(--font-size-xs); font-weight: 700; }
.member-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px; }
.member-full-row { grid-column: 1 / -1; }
.member-form-grid :deep(.el-select), .member-form-grid :deep(.el-input-number) { width: 100%; }
.drawer-heading { display: flex; min-width: 0; flex-direction: column; }
.drawer-heading strong { color: var(--color-text-primary); font-size: 18px; }
.drawer-heading small { color: var(--color-text-tertiary); }
.drawer-kicker { color: var(--color-primary); font-size: 10px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; }
.port-create-panel { margin-bottom: 18px; padding: 15px; border: 1px solid #dce7f5; border-radius: var(--radius-lg); background: linear-gradient(135deg, #f7faff, #fbfdff); }
.port-create-panel > div:first-child { display: flex; flex-direction: column; margin-bottom: 12px; }
.port-create-panel strong { color: var(--color-text-primary); }
.port-create-panel span { color: var(--color-text-tertiary); font-size: var(--font-size-xs); }
.port-range { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)) auto; align-items: end; gap: 8px; }
.port-field { display: flex; min-width: 0; flex-direction: column; gap: 6px; }
.port-field > span { color: var(--color-text-secondary); font-size: var(--font-size-xs); }
.port-range :deep(.el-input-number) { width: 100%; }
@media (max-width: 900px) {
  .filter-field, .region-filter, .search-filter, .compact-filter, .global-scope { width: calc(50% - 6px); }
  .form-grid, .group-create-grid, .member-settings, .member-cards { grid-template-columns: 1fr; }
  .full-row { grid-column: auto; }
}
</style>
