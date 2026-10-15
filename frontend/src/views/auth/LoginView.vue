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
        <h2 class="auth__pitch-title">把每一场会议<br />变成可执行的任务</h2>
        <ul class="auth__points">
          <li>导入材料，快速完成会前准备</li>
          <li>会中记录，并基于资料进行问答</li>
          <li>一键生成纪要并提取行动项</li>
        </ul>
      </div>

      <p class="auth__aside-foot">AI 会议个人助理 · MVP</p>
    </aside>

    <section class="auth__panel">
      <section class="auth__card">
        <header class="auth__header">
          <h1 class="auth__title">登录 OpenMIND</h1>
          <p class="auth__subtitle">使用个人账号进入你的会议工作区</p>
        </header>

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
          <RouterLink class="auth__link" :to="{ name: ROUTE_NAMES.register }">立即注册</RouterLink>
        </p>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import FormField from '@/components/FormField.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'
import { resolveErrorMessage } from '@/utils/errors'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = reactive({ name: '', password: '' })
const errors = reactive({ name: '', password: '' })
const formError = ref('')
const isSubmitting = ref(false)

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
    await router.push(redirect || { name: ROUTE_NAMES.dashboard })
  } catch (error) {
    formError.value = resolveErrorMessage(error, '登录失败，请检查用户名和密码。')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.auth {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  min-height: 100vh;
  background: var(--color-background);
}

/* 左侧深色品牌区 */
.auth__aside {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-5);
  padding: var(--space-6) var(--space-5);
  color: #e2e8f0;
  background:
    radial-gradient(120% 80% at 0% 0%, rgba(99, 102, 241, 0.35), transparent 55%),
    radial-gradient(90% 60% at 100% 100%, rgba(139, 92, 246, 0.3), transparent 60%),
    linear-gradient(160deg, #111a2e 0%, #0a1120 100%);
}

.auth__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: #ffffff;
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
  border-radius: 10px;
  box-shadow: 0 8px 20px rgba(79, 70, 229, 0.45);
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
  color: #ffffff;
}

.auth__points {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: var(--space-4) 0 0;
  padding: 0;
  list-style: none;
  color: rgba(203, 213, 225, 0.92);
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
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.18);
}

.auth__aside-foot {
  margin: 0;
  color: rgba(148, 163, 184, 0.7);
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
