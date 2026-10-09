<template>
  <main class="auth">
    <section class="auth__card">
      <header class="auth__header">
        <h1 class="auth__title">注册 OpenMIND</h1>
        <p class="auth__subtitle">创建一个个人账号，开始管理你的会议</p>
      </header>

      <form class="auth__form" novalidate @submit.prevent="submit">
        <FormField
          id="register-name"
          v-model="form.name"
          label="用户名"
          autocomplete="username"
          required
          :error="errors.name"
        />
        <FormField
          id="register-password"
          v-model="form.password"
          label="密码"
          type="password"
          autocomplete="new-password"
          required
          :error="errors.password"
        />
        <FormField
          id="register-confirm"
          v-model="form.confirmPassword"
          label="确认密码"
          type="password"
          autocomplete="new-password"
          required
          :error="errors.confirmPassword"
        />

        <p v-if="formError" class="auth__error" role="alert">{{ formError }}</p>

        <AppButton type="submit" block :loading="isSubmitting">注册</AppButton>
      </form>

      <p class="auth__footer">
        已有账号？
        <RouterLink class="auth__link" :to="{ name: 'login' }">返回登录</RouterLink>
      </p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import FormField from '@/components/FormField.vue'
import { useAuthStore } from '@/stores/auth'
import { resolveErrorMessage } from '@/utils/errors'

const MIN_PASSWORD_LENGTH = 6

const auth = useAuthStore()
const router = useRouter()

const form = reactive({ name: '', password: '', confirmPassword: '' })
const errors = reactive({ name: '', password: '', confirmPassword: '' })
const formError = ref('')
const isSubmitting = ref(false)

function validate(): boolean {
  errors.name = form.name.trim() ? '' : '请输入用户名'
  if (!form.password) {
    errors.password = '请输入密码'
  } else if (form.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `密码至少需要 ${MIN_PASSWORD_LENGTH} 位`
  } else {
    errors.password = ''
  }
  if (!form.confirmPassword) {
    errors.confirmPassword = '请再次输入密码'
  } else if (form.confirmPassword !== form.password) {
    errors.confirmPassword = '两次输入的密码不一致'
  } else {
    errors.confirmPassword = ''
  }
  return !errors.name && !errors.password && !errors.confirmPassword
}

async function submit(): Promise<void> {
  formError.value = ''
  if (!validate()) {
    return
  }
  isSubmitting.value = true
  try {
    await auth.register({ name: form.name.trim(), password: form.password })
    await router.push({ name: 'login', query: { registered: '1' } })
  } catch (error) {
    formError.value = resolveErrorMessage(error, '注册失败，请稍后重试。')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.auth {
  display: flex;
  justify-content: center;
  padding: var(--space-5) var(--space-4);
}

.auth__card {
  width: 100%;
  max-width: 24rem;
  margin-top: var(--space-5);
  padding: var(--space-5) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.auth__header {
  margin-bottom: var(--space-4);
}

.auth__title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.auth__subtitle {
  margin: var(--space-1) 0 0;
  color: var(--color-muted-foreground);
}

.auth__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.auth__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.875rem;
}

.auth__footer {
  margin: var(--space-4) 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
  text-align: center;
}

.auth__link {
  color: var(--color-primary-strong);
  font-weight: 500;
}
</style>
