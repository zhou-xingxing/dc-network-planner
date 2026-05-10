<template>
  <div>
    <div class="page-heading">
      <div>
        <h2 class="page-title">Region 管理</h2>
        <p class="page-desc">管理所有数据中心 Region，查看和配置各 Region 的网络平面</p>
      </div>
      <el-button v-if="appStore.isAdministrator" type="primary" @click="showCreateDialog" :icon="Plus">添加 Region</el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="regions" stripe border v-loading="loading" empty-text="暂无 Region">
        <el-table-column prop="name" label="Region 名称" min-width="160">
          <template #default="{ row }">
            <span class="link-text" @click="viewRegion(row)">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="plane_count" label="网络平面数" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :type="row.plane_count > 0 ? 'primary' : 'info'">
              {{ row.plane_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewRegion(row)">详情</el-button>
            <el-button v-if="appStore.isAdministrator" size="small" type="warning" link @click="showEditDialog(row)">
              <el-icon style="margin-right: 3px"><Edit /></el-icon>编辑
            </el-button>
            <el-popconfirm v-if="appStore.isAdministrator" title="确定删除该 Region？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" type="danger" link>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑 Region' : '添加 Region'" width="500px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="Region 名称" prop="name">
          <el-input v-model="form.name" placeholder="例如: 北京数据中心" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选描述信息" />
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchRegions, createRegion, updateRegion, deleteRegion } from '@/api/regions'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/time'

const router = useRouter()
const appStore = useAppStore()
const loading = ref(false)
const regions = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const editId = ref(null)
const formRef = ref(null)
const form = ref({ name: '', description: '' })

const rules = {
  name: [{ required: true, message: '请输入 Region 名称', trigger: 'blur' }],
}

async function fetchData() {
  loading.value = true
  try {
    const res = await fetchRegions({ skip: (page.value - 1) * pageSize.value, limit: pageSize.value })
    regions.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function showCreateDialog() {
  isEdit.value = false
  editId.value = null
  form.value = { name: '', description: '' }
  dialogVisible.value = true
}

function showEditDialog(row) {
  isEdit.value = true
  editId.value = row.id
  form.value = { name: row.name, description: row.description || '' }
  dialogVisible.value = true
}

function viewRegion(row) {
  router.push(`/regions/${row.id}`)
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateRegion(editId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createRegion(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchData()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  await deleteRegion(id)
  ElMessage.success('删除成功')
  await fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: var(--spacing-lg); }
.page-title { font-size: var(--font-size-xl); font-weight: 700; color: var(--color-text-primary); margin: 0; }
.page-desc { font-size: var(--font-size-sm); color: var(--color-text-tertiary); margin-top: 4px; }
.link-text { color: var(--color-primary); cursor: pointer; font-weight: 500; }
.link-text:hover { text-decoration: underline; }
</style>
