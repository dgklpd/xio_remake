<template>
  <view class="action-bar">
    <button
      v-for="action in actions"
      :key="action.key"
      class="action-bar__button"
      :class="{ 'action-bar__button-highlight': action.highlight, 'action-bar__button-disabled': action.disabled }"
      :disabled="action.disabled"
    >
      <text>{{ action.label }}</text>
      <text v-if="action.cost !== undefined">· {{ action.cost }} 蓄</text>
    </button>
  </view>
</template>

<script setup lang="ts">
import type { ActionButtonPreview } from "@/types/battle";

defineProps<{
  actions: ActionButtonPreview[];
}>();
</script>

<style scoped lang="scss">
.action-bar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18rpx;
}

.action-bar__button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  height: 86rpx;
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.08);
  border: 1rpx solid rgba(214, 168, 92, 0.18);
  color: $uni-color-title;
  font-size: 26rpx;
  font-weight: 600;
}

.action-bar__button-highlight {
  background: linear-gradient(90deg, rgba(214, 168, 92, 0.9), rgba(240, 195, 111, 0.9));
  color: #30210b;
}

.action-bar__button-disabled {
  opacity: 0.55;
}
</style>
