<template>
  <RouterView></RouterView>
  <WaitingForRestart v-if="hasDesktopRestartBridge" ref="globalWaitingRef" />
  <UpgradeRecoveryDialog v-if="shouldMountRecoveryDialog" />

  <!-- 全局唯一 snackbar -->
  <v-snackbar v-if="toastStore.current" v-model="snackbarShow" :color="toastStore.current.color"
    :timeout="toastStore.current.timeout" :multi-line="toastStore.current.multiLine"
    :location="toastStore.current.location" close-on-back>
    <div class="app-snackbar-message">
      <v-icon v-if="toastIcon" :icon="toastIcon" size="24" />
      <span>{{ toastStore.current.message }}</span>
    </div>
    <template #actions v-if="toastStore.current.closable">
      <v-btn icon="mdi-close" variant="text" size="small" aria-label="Close notification" @click="snackbarShow = false" />
    </template>
  </v-snackbar>
</template>

<script setup>
import { RouterView } from 'vue-router';
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { useToastStore } from '@/stores/toast'

const WaitingForRestart = defineAsyncComponent(
  () => import('@/components/shared/WaitingForRestart.vue')
)
const UpgradeRecoveryDialog = defineAsyncComponent(
  () => import('@/components/shared/UpgradeRecoveryDialog.vue')
)

const toastStore = useToastStore()
const globalWaitingRef = ref(null)
const desktopBridge = window.astrbotDesktop
const hasDesktopRestartBridge = Boolean(desktopBridge?.onTrayRestartBackend)
const shouldMountRecoveryDialog = ref(window.location.hash.startsWith('#/auth/'))
let disposeTrayRestartListener = null
let recoveryIdleHandle = null
let recoveryTimer = null

const snackbarShow = computed({
  get: () => !!toastStore.current,
  set: (val) => {
    if (!val) toastStore.shift()
  }
})

const toastIcon = computed(() => ({
  success: 'mdi-check-circle-outline',
  error: 'mdi-alert-circle-outline',
  warning: 'mdi-alert-outline',
  info: 'mdi-information-outline',
  primary: 'mdi-information-outline'
})[toastStore.current?.color] || '')

onMounted(() => {
  if (!shouldMountRecoveryDialog.value) {
    const mountRecoveryDialog = () => {
      shouldMountRecoveryDialog.value = true
      recoveryIdleHandle = null
      recoveryTimer = null
    }
    if (typeof window.requestIdleCallback === 'function') {
      recoveryIdleHandle = window.requestIdleCallback(mountRecoveryDialog, { timeout: 1200 })
    } else {
      recoveryTimer = window.setTimeout(mountRecoveryDialog, 400)
    }
  }

  if (!hasDesktopRestartBridge) return

  disposeTrayRestartListener = desktopBridge.onTrayRestartBackend(async () => {
    try {
      await globalWaitingRef.value?.check?.()
    } catch (error) {
      globalWaitingRef.value?.stop?.()
      console.error('Tray restart backend failed:', error)
    }
  })
})

onBeforeUnmount(() => {
  if (recoveryIdleHandle !== null && typeof window.cancelIdleCallback === 'function') {
    window.cancelIdleCallback(recoveryIdleHandle)
  }
  if (recoveryTimer !== null) {
    window.clearTimeout(recoveryTimer)
  }
  if (disposeTrayRestartListener) {
    disposeTrayRestartListener()
    disposeTrayRestartListener = null
  }
})
</script>
