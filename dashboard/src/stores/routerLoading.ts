import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useRouterLoadingStore = defineStore('routerLoading', () => {
    const isLoading = ref(false);
    const progress = ref(0);
    let progressInterval: ReturnType<typeof setInterval> | null = null;
    let hideTimer: ReturnType<typeof setTimeout> | null = null;

    function start() {
        if (hideTimer) {
            clearTimeout(hideTimer);
            hideTimer = null;
        }
        isLoading.value = true;
        progress.value = 12;

        if (progressInterval) {
            clearInterval(progressInterval);
        }

        let currentProgress = 12;
        progressInterval = setInterval(() => {
            if (currentProgress < 80) {
                // 快速阶段：0-80%
                currentProgress += Math.random() * 20 + 10;
                if (currentProgress > 80) {
                    currentProgress = 80;
                }
            } else if (currentProgress < 90) {
                // 缓慢阶段：80-90%
                currentProgress += Math.random() * 3 + 1;
                if (currentProgress > 90) {
                    currentProgress = 90;
                }
            }
            progress.value = Math.min(currentProgress, 90);
        }, 50);
    }

    function finish() {
        // 清理interval
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }

        // 快速完成到100%
        progress.value = 100;

        // Keep the completion flash brief so fast navigations still feel instant.
        hideTimer = setTimeout(() => {
            isLoading.value = false;
            progress.value = 0;
            hideTimer = null;
        }, 120);
    }

    return {
        isLoading,
        progress,
        start,
        finish
    };
});

