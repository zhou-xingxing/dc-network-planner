<template>
  <div class="profile-page" v-loading="loading">
    <!-- 顶部 Hero 卡片 -->
    <section class="profile-hero">
      <div class="hero-decor decor-1"></div>
      <div class="hero-decor decor-2"></div>
      <div class="hero-decor decor-3"></div>

      <div class="hero-main">
        <div class="profile-avatar">
          <span class="avatar-text">{{ avatarText }}</span>
          <span class="avatar-dot" :class="{ 'is-admin': isAdministrator }"></span>
        </div>
        <div class="profile-title">
          <p class="eyebrow">
            <el-icon><User /></el-icon>
            <span>个人主页</span>
          </p>
          <h2>{{ user?.username || '-' }}</h2>
          <div class="profile-meta">
            <el-tag :type="isAdministrator ? 'warning' : ''" effect="dark" round size="small">
              {{ roleLabel }}
            </el-tag>
            <span class="meta-divider"></span>
            <span class="meta-text">
              <el-icon><Location /></el-icon>
              可管理 {{ regionSummary }} Region
            </span>
          </div>
        </div>
      </div>

      <el-button
        class="hero-action"
        type="primary"
        plain
        :icon="Edit"
        @click="openPasswordDialog"
      >
        修改密码
      </el-button>
    </section>

    <!-- 指标卡 -->
    <div class="stat-row">
      <div class="stat-card">
        <div class="stat-icon stat-icon-primary">
          <el-icon><Avatar /></el-icon>
        </div>
        <div class="stat-content">
          <p class="stat-label">账号角色</p>
          <p class="stat-value">{{ isAdministrator ? '管理员' : '普通用户' }}</p>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon-success">
          <el-icon><Connection /></el-icon>
        </div>
        <div class="stat-content">
          <p class="stat-label">可管理 Region</p>
          <p class="stat-value">{{ regionSummary }}</p>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon-warning">
          <el-icon><CircleCheckFilled /></el-icon>
        </div>
        <div class="stat-content">
          <p class="stat-label">账号状态</p>
          <p class="stat-value">正常</p>
        </div>
      </div>
    </div>

    <!-- 详情卡片 -->
    <div class="profile-grid">
      <el-card shadow="never" class="profile-card region-card">
        <template #header>
          <div class="card-header">
            <div class="card-header-title">
              <span class="title-bar"></span>
              <span class="card-title">Region 授权</span>
            </div>
            <span class="region-count">共 {{ regionSummary }}</span>
          </div>
        </template>

        <div v-if="isAdministrator" class="admin-region">
          <div class="admin-region-badge">
            <el-icon><StarFilled /></el-icon>
            <span>全部 Region</span>
          </div>
          <p>administrator 具备全局管理权限，可访问所有 Region 及其网络平面。</p>
        </div>
        <div v-else-if="permittedRegions.length" class="region-list">
          <span
            v-for="region in permittedRegions"
            :key="region.id"
            class="region-chip"
          >
            <el-icon><Location /></el-icon>
            {{ region.name }}
          </span>
        </div>
        <el-empty v-else description="暂无已授权 Region" :image-size="96" />
      </el-card>
    </div>

    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="420px" :close-on-click-modal="false">
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-width="90px">
        <el-form-item label="原密码" prop="current_password">
          <el-input v-model="passwordForm.current_password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordSubmitting" @click="handleChangePassword">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import {
  User,
  Location,
  Edit,
  Avatar,
  Connection,
  CircleCheckFilled,
  StarFilled,
} from '@element-plus/icons-vue'
import { changeMyPassword, fetchCurrentUser } from '@/api/auth'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
const loading = ref(false)
const passwordDialogVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordFormRef = ref<FormInstance>()
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const user = computed(() => appStore.currentUser)
const isAdministrator = computed(() => user.value?.role === 'administrator')
const permittedRegions = computed(() => user.value?.permitted_regions || [])
const avatarText = computed(() => (user.value?.username || '-').slice(0, 1).toUpperCase())
const roleLabel = computed(() => (isAdministrator.value ? 'administrator（管理员）' : 'user（普通用户）'))
const regionSummary = computed(() => {
  if (isAdministrator.value) return '全部'
  return `${permittedRegions.value.length} 个`
})
const passwordRules = {
  current_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string, callback: (error?: Error) => void) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的新密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

function resetPasswordForm() {
  Object.assign(passwordForm, {
    current_password: '',
    new_password: '',
    confirm_password: '',
  })
  passwordFormRef.value?.clearValidate()
}

function openPasswordDialog() {
  resetPasswordForm()
  passwordDialogVisible.value = true
}

async function handleChangePassword() {
  const valid = await passwordFormRef.value?.validate().catch(() => false)
  if (!valid) return
  passwordSubmitting.value = true
  try {
    await changeMyPassword(passwordForm.current_password, passwordForm.new_password)
    ElMessage.success('密码已修改')
    passwordDialogVisible.value = false
    resetPasswordForm()
  } finally {
    passwordSubmitting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const currentUser = await fetchCurrentUser()
    appStore.setCurrentUser(currentUser)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.profile-page {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

/* ---------- Hero ---------- */
.profile-hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-lg);
  min-height: 168px;
  overflow: hidden;
  padding: 32px 36px;
  color: #ffffff;
  background:
    radial-gradient(circle at 88% 18%, rgba(74, 144, 217, 0.55), transparent 55%),
    radial-gradient(circle at 12% 90%, rgba(26, 115, 232, 0.45), transparent 60%),
    linear-gradient(135deg, #0f172a 0%, #1e293b 45%, #1557b0 100%);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.hero-decor {
  position: absolute;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.16);
  pointer-events: none;
}
.decor-1 {
  right: -60px;
  top: -80px;
  width: 240px;
  height: 240px;
  border-color: rgba(255, 255, 255, 0.22);
}
.decor-2 {
  right: 80px;
  bottom: -100px;
  width: 180px;
  height: 180px;
  border-color: rgba(255, 255, 255, 0.14);
}
.decor-3 {
  right: -20px;
  top: 20px;
  width: 8px;
  height: 8px;
  background: rgba(255, 255, 255, 0.6);
  border: none;
  box-shadow: 0 0 18px rgba(255, 255, 255, 0.6);
}

.hero-main {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  min-width: 0;
}

.profile-avatar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 76px;
  height: 76px;
  flex-shrink: 0;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.24), rgba(255, 255, 255, 0.08));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 8px 24px rgba(0, 0, 0, 0.25);
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.avatar-text {
  background: linear-gradient(135deg, #ffffff, #cfe1ff);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.avatar-dot {
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--color-success);
  border: 2px solid #1e293b;
  box-shadow: 0 0 0 2px rgba(52, 168, 83, 0.25);
}
.avatar-dot.is-admin {
  background: var(--color-warning);
  box-shadow: 0 0 0 2px rgba(251, 188, 4, 0.3);
}

.profile-title {
  min-width: 0;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding: 3px 10px;
  color: rgba(255, 255, 255, 0.88);
  font-size: var(--font-size-xs);
  font-weight: 600;
  letter-spacing: 0.6px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  backdrop-filter: blur(4px);
}

.profile-title h2 {
  margin-bottom: 10px;
  font-size: 30px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.5px;
}

.profile-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.8);
  font-size: var(--font-size-sm);
}

.meta-divider {
  width: 1px;
  height: 14px;
  background: rgba(255, 255, 255, 0.25);
}

.meta-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* ---------- 指标卡 ---------- */
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-lg);
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 22px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition-base), box-shadow var(--transition-base);
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 14px;
  font-size: 24px;
}
.stat-icon-primary {
  color: var(--color-primary);
  background: var(--color-primary-lighter);
}
.stat-icon-success {
  color: var(--color-success);
  background: rgba(52, 168, 83, 0.12);
}
.stat-icon-warning {
  color: var(--color-warning);
  background: rgba(251, 188, 4, 0.14);
}

.stat-content {
  min-width: 0;
}

.stat-label {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
  margin-bottom: 4px;
}

.stat-value {
  color: var(--color-text-primary);
  font-size: var(--font-size-xl);
  font-weight: 700;
  line-height: 1.2;
}

/* ---------- 详情卡片 ---------- */
.profile-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--spacing-lg);
}

.profile-card {
  min-height: 260px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-bar {
  display: inline-block;
  width: 4px;
  height: 16px;
  border-radius: 2px;
  background: linear-gradient(180deg, var(--color-primary), var(--color-primary-light));
}

.card-title {
  color: var(--color-text-primary);
  font-size: var(--font-size-lg);
  font-weight: 700;
}

.region-count {
  padding: 2px 10px;
  color: var(--color-primary);
  background: var(--color-primary-lighter);
  border-radius: 999px;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

/* ---- 信息列表 ---- */
.info-list {
  list-style: none;
  display: flex;
  flex-direction: column;
}

.info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  padding: 14px 4px;
  border-bottom: 1px dashed var(--color-border);
}
.info-item:last-child {
  border-bottom: none;
}

.info-label {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
}

.info-value {
  color: var(--color-text-primary);
  font-weight: 600;
}

.info-value-muted {
  color: var(--color-text-secondary);
  letter-spacing: 2px;
  font-weight: 500;
}

/* ---- Region 列表 ---- */
.region-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.region-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  color: var(--color-primary-dark);
  background: var(--color-primary-lighter);
  border: 1px solid rgba(26, 115, 232, 0.18);
  border-radius: 999px;
  font-size: var(--font-size-sm);
  font-weight: 500;
  transition: all var(--transition-fast);
}
.region-chip:hover {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.25);
}

.admin-region {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.admin-region-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  padding: 8px 16px;
  color: #b15c00;
  background: linear-gradient(135deg, rgba(251, 188, 4, 0.18), rgba(251, 188, 4, 0.08));
  border: 1px solid rgba(251, 188, 4, 0.35);
  border-radius: 999px;
  font-weight: 600;
}

.admin-region p {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.6;
}

.hero-action {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  color: #ffffff;
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.35);
}
.hero-action:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.22);
  border-color: rgba(255, 255, 255, 0.55);
}

/* ---------- 响应式 ---------- */
@media (max-width: 1024px) {
  .stat-row {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 900px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
  .stat-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .profile-hero {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-md);
    padding: 24px;
  }
  .hero-action {
    align-self: flex-start;
  }
  .profile-title h2 {
    font-size: 24px;
  }
}
</style>
