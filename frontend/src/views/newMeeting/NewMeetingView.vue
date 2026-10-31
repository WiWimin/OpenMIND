<template>
  <section class="new-meeting" aria-label="会议流程入口">
    <div class="new-meeting__grid">
      <RouterLink
        v-for="stage in stages"
        :key="stage.key"
        class="stage-card"
        :to="stage.to"
        :aria-label="`进入${stage.label}`"
      >
        <div class="stage-card__banner" :class="`stage-card__banner--${stage.tone}`" aria-hidden="true">
          <svg class="stage-card__wave" viewBox="0 0 320 100" preserveAspectRatio="none">
            <path
              d="M0 60C56 32 118 76 188 52 250 32 288 44 320 28L320 100 0 100Z"
              fill="rgba(255, 255, 255, 0.35)"
            />
            <path
              d="M0 78C68 54 132 92 202 68 258 50 294 62 320 52L320 100 0 100Z"
              fill="rgba(255, 255, 255, 0.5)"
            />
          </svg>
          <span class="stage-card__chip">
            <svg viewBox="0 0 24 24" width="24" height="24" fill="none">
              <path
                v-for="(path, pathIndex) in stage.iconPaths"
                :key="pathIndex"
                :d="path"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>
        </div>

        <div class="stage-card__body">
          <h2 class="stage-card__title">
            {{ stage.label }}
            <svg
              class="stage-card__title-arrow"
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M5 12h13M13 6.5l5.5 5.5L13 17.5"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </h2>
          <p class="stage-card__desc">{{ stage.description }}</p>

          <ul class="stage-card__features">
            <li v-for="feature in stage.features" :key="feature">
              <span class="stage-card__check" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" />
                  <path
                    d="m8.4 12.3 2.4 2.4 4.8-5"
                    stroke="currentColor"
                    stroke-width="1.7"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </span>
              <span>{{ feature }}</span>
            </li>
          </ul>
        </div>
      </RouterLink>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { ROUTE_NAMES } from '@/constants/routeNames'

interface StageCard {
  key: string
  label: string
  description: string
  features: string[]
  tone: 'blue' | 'teal' | 'amber'
  iconPaths: string[]
  to: { name: string; query?: Record<string, string> }
}

const route = useRoute()

const stages = computed<StageCard[]>(() => {
  const meetingId = typeof route.query.meetingId === 'string' ? route.query.meetingId : ''
  const query = meetingId ? { meetingId } : undefined
  return [
    {
      key: 'preprocess',
      label: '资料预处理',
      description: '会前智能解析，自动生成会议基础素材',
      features: ['上传会议资料', '提取关键议题', '生成会议议程'],
      tone: 'blue',
      iconPaths: [
        'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
        'M14 3.5V8h4.5M8.5 12h6M8.5 15.5h4',
      ],
      to: { name: ROUTE_NAMES.preprocess, query },
    },
    {
      key: 'asr',
      label: '实时录音转写',
      description: '会议过程中边录边转，沉淀重点内容',
      features: ['高清实时录音', '智能语音转写', '标记会议重点'],
      tone: 'teal',
      iconPaths: [
        'M12 3.5a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0v-5a3 3 0 0 0-3-3Z',
        'M6.5 11.5v.5a5.5 5.5 0 0 0 11 0v-.5M12 17.5V21M9 21h6',
      ],
      to: { name: ROUTE_NAMES.asr, query },
    },
    {
      key: 'minutes',
      label: '会后智能处理',
      description: '基于会议内容自动生成纪要与行动项',
      features: ['生成会议纪要', '生成会议摘要', '提取待办任务'],
      tone: 'amber',
      iconPaths: [
        'M6 3.5h12A1.5 1.5 0 0 1 19.5 5v14A1.5 1.5 0 0 1 18 20.5H6A1.5 1.5 0 0 1 4.5 19V5A1.5 1.5 0 0 1 6 3.5Z',
        'M8 8h8M8 11.5h8M8 15h5',
      ],
      to: { name: ROUTE_NAMES.minutesGenerate, query },
    },
  ]
})
</script>

<style scoped>
.new-meeting {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.new-meeting__grid {
  display: grid;
  flex: 1;
  grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr));
  gap: var(--space-4);
  /* 填满视口剩余高度（上限 62rem，1080p 及以下正好占满） */
  min-height: min(calc(100vh - 7.5rem), 62rem);
  gap: var(--space-5);
}

/* 卡片（整卡可点击） */
.stage-card {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  color: inherit;
  text-decoration: none;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition:
    transform var(--transition),
    box-shadow var(--transition),
    border-color var(--transition);
}

.stage-card:hover {
  transform: translateY(-3px);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-md);
}

.stage-card:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

/* 渐变插画头 */
.stage-card__banner {
  position: relative;
  height: 11rem;
  overflow: hidden;
}

.stage-card__banner--blue {
  background: linear-gradient(118deg, #e3edff 0%, #c9dcff 48%, #9cc1ff 100%);
}

.stage-card__banner--teal {
  background: linear-gradient(118deg, #d9f4e6 0%, #b5ecd2 45%, #fde7ac 100%);
}

.stage-card__banner--amber {
  background: linear-gradient(118deg, #e3edff 0%, #d8defc 48%, #fde7ac 100%);
}

.stage-card__wave {
  position: absolute;
  inset: auto 0 0;
  width: 100%;
  height: 70%;
}

.stage-card__chip {
  position: absolute;
  top: 50%;
  right: 1.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 3.8rem;
  height: 3.8rem;
  color: var(--color-primary-strong);
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  box-shadow: 0 10px 22px rgba(21, 94, 239, 0.18);
  transform: translateY(-50%);
}

/* 内容区 */
.stage-card__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-6);
}

.stage-card__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-foreground);
}

.stage-card__title-arrow {
  color: var(--color-primary);
  opacity: 0.55;
  transition:
    opacity var(--transition-fast),
    transform var(--transition-fast);
}

.stage-card:hover .stage-card__title-arrow {
  opacity: 1;
  transform: translateX(3px);
}

.stage-card__desc {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.9375rem;
  line-height: 1.7;
}

.stage-card__features {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: center;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.stage-card__features li {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--color-foreground);
  font-size: 1rem;
  font-weight: 550;
}

.stage-card__check {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.6rem;
  height: 1.6rem;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-radius: 50%;
}

@media (max-width: 720px) {
  .stage-card__body {
    padding: var(--space-4);
  }

  .stage-card__banner {
    height: 7.5rem;
  }

  .stage-card__features {
    flex: 0 0 auto;
  }
}
</style>
