<template>
  <main class="auth">
    <section class="auth__card">
      <header class="auth__header">
        <h1 class="auth__title">登录 OpenMIND</h1>
        <p class="auth__subtitle">使用个人账号进入你的会议工作区</p>
      </header>

      <p v-if="justRegistered" class="auth__notice" role="status">注册成功，请使用新账号登录。</p>

      <form class="auth__form" novalidate @submit.prevent="submit">
        <FormField
          id="login-name"
          v-model="form.name"
          label="用户名"
          autocomplete="username"
          required
          :error="errors.name"
        />
        <FormField
          id="login-password"
          v-model="form.password"
          label="密码"
          type="password"
          autocomplete="current-password"
          required
          :error="errors.password"
        />

        <p v-if="formError" class="auth__error" role="alert">{{ formError }}</p>

        <AppButton type="submit" block :loading="isSubmitting">登录</AppButton>
      </form>

      <p class="auth__footer">
        还没有账号？
        <RouterLink class="auth__link" :to="{ name: 'register' }">立即注册</RouterLink>
      </p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import FormField from '@/components/FormField.vue'
import { useAuthStore } from '@/stores/auth'
import { resolveErrorMessage } from '@/utils/errors'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = reactive({ name: '', password: '' })
const errors = reactive({ name: '', password: '' })
const formError = ref('')
const isSubmitting = ref(false)

const justRegistered = computed(() => route.query.registered === '1')

function validate(): boolean {
  errors.name = form.name.trim() ? '' : '请输入用户名'
  errors.password = form.password ? '' : '请输入密码'
  return !errors.name && !errors.password
}

async function submit(): Promise<void> {
  formError.value = ''
  if (!validate()) {
    return
  }
  isSubmitting.value = true
  try {
    await auth.login({ name: form.name.trim(), password: form.password })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    await router.push(redirect || { name: 'workspace' })
  } catch (error) {
    formError.value = resolveErrorMessage(error, '登录失败，请检查用户名和密码。')
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

.auth__notice {
  margin: 0 0 var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-primary-strong);
  font-size: 0.875rem;
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
