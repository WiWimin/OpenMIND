<template>
  <main class="auth">
    <aside class="auth__aside">
      <RouterLink class="auth__brand" :to="{ name: ROUTE_NAMES.login }">
        <span class="auth__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
            <path
              d="M4 7.5A2.5 2.5 0 0 1 6.5 5h6.2c.4 0 .79.1 1.13.28l4.9 2.6c.78.42 1.27 1.24 1.27 2.13v6.49A2.5 2.5 0 0 1 17.5 19H6.5A2.5 2.5 0 0 1 4 16.5v-9Z"
              stroke="currentColor"
              stroke-width="1.6"
            />
            <path d="m13 9 4.5-2.4v7L13 11.2V9Z" fill="currentColor" opacity="0.9" />
          </svg>
        </span>
        <span class="auth__wordmark">OpenMIND</span>
      </RouterLink>

      <div class="auth__pitch">
        <h2 class="auth__pitch-title">从会议记录<br />到个人任务闭环</h2>
        <ul class="auth__points">
          <li>资料导入与解析，自动建立检索索引</li>
          <li>纪要与行动项以候选形式生成，由你确认</li>
          <li>行动项一键转个人任务并跟踪状态</li>
        </ul>
      </div>

      <p class="auth__aside-foot">AI 会议个人助理 · MVP</p>
    </aside>

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
  background:
    radial-gradient(80% 60% at 12% 14%, rgba(59, 111, 212, 0.1), transparent 55%),
    radial-gradient(60% 45% at 88% 90%, rgba(20, 184, 166, 0.06), transparent 55%),
    linear-gradient(160deg, #eef2f8 0%, #e8edf5 48%, #eef2f8 100%);
}

/* 全页网格纹理 */
.auth::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(59, 111, 212, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(59, 111, 212, 0.055) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: radial-gradient(130% 110% at 30% 25%, #000 30%, transparent 92%);
  pointer-events: none;
}

/* 左侧品牌区 */
.auth__aside {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-5);
  padding: var(--space-6) var(--space-5);
  color: var(--color-foreground);
}

.auth__brand,
.auth__pitch,
.auth__aside-foot {
  position: relative;
  z-index: 1;
}

.auth__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-foreground);
  text-decoration: none;
}

.auth__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  border-radius: var(--radius-md);
  box-shadow: 0 8px 20px rgba(59, 111, 212, 0.35);
}

.auth__wordmark {
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.auth__pitch-title {
  margin: 0;
  font-size: 2rem;
  font-weight: 700;
  line-height: 1.32;
  color: var(--color-foreground);
}

.auth__points {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: var(--space-4) 0 0;
  padding: 0;
  list-style: none;
  color: var(--color-muted-foreground);
}

.auth__points li {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: 0.9375rem;
}

.auth__points li::before {
  content: '';
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  margin-top: 0.55rem;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  box-shadow: 0 0 0 4px rgba(59, 111, 212, 0.14);
}

.auth__aside-foot {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  letter-spacing: 0.04em;
}

/* 右侧表单区 */
.auth__panel {
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

  .auth__aside {
    display: none;
  }
}
</style>
