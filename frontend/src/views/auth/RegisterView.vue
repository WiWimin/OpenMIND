<template>
  <main class="auth">
    <section class="auth__panel">
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
          <RouterLink class="auth__link" :to="{ name: ROUTE_NAMES.login }">去登录</RouterLink>
        </p>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import FormField from '@/components/FormField.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'
import { resolveErrorMessage } from '@/utils/errors'

const MIN_PASSWORD_LENGTH = 6
const MAX_NAME_LENGTH = 100

const auth = useAuthStore()
const router = useRouter()

const form = reactive({ name: '', password: '', confirmPassword: '' })
const errors = reactive({ name: '', password: '', confirmPassword: '' })
const formError = ref('')
const isSubmitting = ref(false)

function validate(): boolean {
  const name = form.name.trim()
  if (!name) {
    errors.name = '请输入用户名'
  } else if (name.length > MAX_NAME_LENGTH) {
    errors.name = `用户名不能超过 ${MAX_NAME_LENGTH} 个字符`
  } else {
    errors.name = ''
  }
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
    await router.push({ name: ROUTE_NAMES.dashboard })
  } catch (error) {
    formError.value = resolveErrorMessage(error, '注册失败，请稍后重试。')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.auth {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  min-height: 100vh;
  /* 品牌背景图：左侧为品牌视觉，右侧留白放置表单 */
  background:
    url('@/assets/registerbg.jpeg') left center / cover no-repeat,
    #eef2f8;
}

/* 右侧表单区 */
.auth__panel {
  grid-column: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5) var(--space-4);
}

.auth__card {
  width: 100%;
  max-width: 26rem;
  padding: var(--space-5);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.auth__header {
  margin-bottom: var(--space-4);
}

.auth__title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.auth__subtitle {
  margin: var(--space-1) 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.9375rem;
}

.auth__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.auth__error {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: rgba(225, 29, 72, 0.06);
  border: 1px solid rgba(225, 29, 72, 0.22);
  border-radius: var(--radius-md);
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
  font-weight: 600;
}

@media (max-width: 900px) {
  .auth {
    grid-template-columns: 1fr;
  }

  .auth__panel {
    grid-column: 1;
  }
}
</style>
