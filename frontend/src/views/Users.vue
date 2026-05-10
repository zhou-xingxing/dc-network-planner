<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2>用户管理</h2>
        <p>管理本地账号、角色和 Region 授权</p>
      </div>
      <el-button type="primary" @click="openCreate">新增用户</el-button>
    </div>

    <el-card>
      <el-table :data="users" border v-loading="loading" style="width: 100%">
        <el-table-column prop="username" label="用户名" min-width="130" />
        <el-table-column prop="display_name" label="显示名" min-width="130" />
        <el-table-column prop="role" label="角色" width="150">
          <template #default="{ row }">
            <el-tag :type="row.role === 'administrator' ? 'warning' : 'success'">{{ row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Region 授权" min-width="220">
          <template #default="{ row }">
            <span v-if="row.role === 'administrator'" class="muted">全局管理账号</span>
            <el-tag v-for="region in row.permitted_regions" v-else :key="region.id" size="small" class="region-tag">
              {{ region.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="openReset(row)">重置密码</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑用户' : '新增用户'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="用户名" prop="username" v-if="!editingId">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="!editingId">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="角色">
          <el-segmented v-model="form.role" :options="roleOptions" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="Region" v-if="form.role === 'user'">
          <el-select
            v-model="form.permitted_region_ids"
            multiple
            filterable
            placeholder="选择可管理 Region"
            style="width: 100%"
          >
            <el-option v-for="region in regions" :key="region.id" :label="region.name" :value="region.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetVisible" title="重置密码" width="420px">
      <el-form :model="resetForm" label-width="90px">
        <el-form-item label="新密码">
          <el-input v-model="resetForm.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!resetForm.password" @click="handleReset">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchRegions } from '@/api/regions'
import { createUser, deleteUser, fetchUsers, resetUserPassword, updateUser } from '@/api/users'

const users = ref([])
const regions = ref([])
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const resetVisible = ref(false)
const editingId = ref('')
const formRef = ref()
const form = reactive({
  username: '',
  password: '',
  role: 'user',
  display_name: '',
  is_active: true,
  permitted_region_ids: [],
})
const resetForm = reactive({ id: '', password: '' })
const roleOptions = [
  { label: 'user', value: 'user' },
  { label: 'administrator', value: 'administrator' },
]
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadRegions()])
})

async function loadUsers() {
  loading.value = true
  try {
    const data = await fetchUsers({ limit: 500 })
    users.value = data.items
  } finally {
    loading.value = false
  }
}

async function loadRegions() {
  const data = await fetchRegions({ limit: 500 })
  regions.value = data.items
}

function openCreate() {
  editingId.value = ''
  Object.assign(form, {
    username: '',
    password: '',
    role: 'user',
    display_name: '',
    is_active: true,
    permitted_region_ids: [],
  })
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    password: '',
    role: row.role,
    display_name: row.display_name,
    is_active: row.is_active,
    permitted_region_ids: row.permitted_regions.map((region) => region.id),
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload = {
      role: form.role,
      display_name: form.display_name,
      is_active: form.is_active,
      permitted_region_ids: form.role === 'user' ? form.permitted_region_ids : [],
    }
    if (editingId.value) {
      await updateUser(editingId.value, payload)
    } else {
      await createUser({ ...payload, username: form.username, password: form.password })
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadUsers()
  } finally {
    submitting.value = false
  }
}

function openReset(row) {
  resetForm.id = row.id
  resetForm.password = ''
  resetVisible.value = true
}

async function handleReset() {
  await resetUserPassword(resetForm.id, resetForm.password)
  ElMessage.success('密码已重置')
  resetVisible.value = false
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除用户 ${row.username}？`, '确认删除', { type: 'warning' })
  await deleteUser(row.id)
  ElMessage.success('删除成功')
  await loadUsers()
}
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-header h2 {
  margin: 0;
}

.page-header p {
  margin: 6px 0 0;
  color: var(--color-text-secondary);
}

.region-tag {
  margin-right: 6px;
}

.muted {
  color: var(--color-text-secondary);
}
</style>
