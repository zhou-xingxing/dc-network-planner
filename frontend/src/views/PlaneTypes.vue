<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">网络平面类型</h2>
        <p class="page-desc">全局网络平面类型字典，所有 Region 共享此配置</p>
      </div>
      <el-button v-if="appStore.isAdministrator" type="primary" @click="showCreateDialog" :icon="Plus">添加类型</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="items" stripe v-loading="loading" empty-text="暂无网络平面类型">
        <el-table-column prop="name" label="类型名称" min-width="160">
          <template #default="{ row }">
            <el-tag type="primary" effect="plain" size="large">{{ row.name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="parent_name" label="父级平面" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.parent_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="is_private" label="是否私网" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_private ? 'success' : 'info'" size="small" effect="plain">
              {{ row.is_private ? '私网' : '公网' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="vrf" label="所属 VRF" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.vrf || '-' }}</template>
        </el-table-column>
        <el-table-column prop="usage_count" label="使用次数" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.usage_count > 0 ? 'success' : 'info'" size="small" effect="plain">{{ row.usage_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column v-if="appStore.isAdministrator" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="warning" link @click="showEditDialog(row)">
              <el-icon style="margin-right: 3px"><Edit /></el-icon>编辑
            </el-button>
            <el-popconfirm title="确定删除？如果该网络平面类型已被使用则无法删除" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link :disabled="row.usage_count > 0">
                  <el-icon style="margin-right: 3px"><Delete /></el-icon>删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="fetchData"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑类型' : '添加类型'" width="500px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="类型名称" prop="name">
          <el-input v-model="form.name" placeholder="例如: 管理平面" maxlength="100" />
        </el-form-item>
        <el-form-item label="父级平面" prop="parent_id">
          <el-select v-model="form.parent_id" placeholder="无父级" clearable style="width: 100%">
            <el-option
              v-for="pt in parentOptions"
              :key="pt.id"
              :label="pt.name"
              :value="pt.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选描述信息" />
        </el-form-item>
        <el-form-item label="是否私网" prop="is_private">
          <el-switch v-model="form.is_private" active-text="私网" inactive-text="公网" />
        </el-form-item>
        <el-form-item label="所属 VRF" prop="vrf">
          <el-input v-model="form.vrf" placeholder="可为空，例如: vrf-mgmt" maxlength="100" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { createPlaneType, deletePlaneType, fetchPlaneTypes, updatePlaneType } from '@/api/networkPlaneTypes'
import { useAppStore } from '@/stores/app'
import { formatDateTime } from '@/utils/time'
import { Delete, Edit, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const loading = ref(false)
const appStore = useAppStore()
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const editId = ref(null)
const formRef = ref(null)
const form = ref({ name: '', parent_id: '', description: '', is_private: false, vrf: '' })

const parentOptions = computed(() => {
  if (!isEdit.value || !editId.value) return items.value
  const blocked = new Set([editId.value, ...collectDescendantIds(editId.value)])
  return items.value.filter(item => !blocked.has(item.id))
})

const rules = {
  name: [{ required: true, message: '请输入类型名称', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await fetchPlaneTypes({ skip: (page.value - 1) * pageSize.value, limit: pageSize.value })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  isEdit.value = false
  editId.value = null
  form.value = { name: '', parent_id: '', description: '', is_private: false, vrf: '' }
  dialogVisible.value = true
}

function showEditDialog(row) {
  isEdit.value = true
  editId.value = row.id
  form.value = {
    name: row.name,
    parent_id: row.parent_id || '',
    description: row.description || '',
    is_private: Boolean(row.is_private),
    vrf: row.vrf || '',
  }
  dialogVisible.value = true
}

function collectDescendantIds(parentId) {
  const result = []
  for (const item of items.value) {
    if (item.parent_id === parentId) {
      result.push(item.id, ...collectDescendantIds(item.id))
    }
  }
  return result
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const payload = { ...form.value, parent_id: form.value.parent_id || null }
    if (isEdit.value) {
      await updatePlaneType(editId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createPlaneType(payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchData()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await deletePlaneType(id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (e) {
    // Error handled by Axios interceptor
  }
}

onMounted(fetchData)
</script>

<style scoped>
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: var(--spacing-lg); }
.page-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 0; }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin-top: 4px; }
</style>
