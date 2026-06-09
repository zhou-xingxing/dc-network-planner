<template>
  <div class="login-page">
    <section class="login-panel">
      <div class="brand">
        <div class="brand-mark">DC</div>
        <div>
          <h1>DC Network Planner</h1>
          <p>数据中心网络平面地址规划管理</p>
        </div>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" size="large" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" size="large" type="password" autocomplete="current-password" show-password />
        </el-form-item>
        <el-button type="primary" native-type="submit" size="large" class="login-button" :loading="loading">
          登录
        </el-button>
      </el-form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { login } from '@/api/auth'
import { useAppStore } from '@/stores/app'
import { ElMessage } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()
const appStore = useAppStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  if (loading.value) return
  loading.value = true
  try {
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid) return
    const result = await login(form.username, form.password)
    appStore.setSession(result.access_token, result.user)
    ElMessage.success('登录成功')
    const redirect = Array.isArray(route.query.redirect) ? route.query.redirect[0] : route.query.redirect
    router.push(redirect || '/dashboard')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #eef4f8;
}

.login-panel {
  width: min(420px, 100%);
  padding: 32px;
  background: #fff;
  border: 1px solid #dbe4ea;
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.12);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
}

.brand-mark {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #1a73e8;
  color: #fff;
  font-weight: 700;
}

h1 {
  margin: 0;
  font-size: 22px;
  color: #172033;
}

p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 13px;
}

.login-button {
  width: 100%;
  margin-top: 8px;
}
</style>
