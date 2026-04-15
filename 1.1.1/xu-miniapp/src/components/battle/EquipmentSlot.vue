<template>
  <view class="equipment-slot" :class="[`equipment-slot--${theme}`, { 'equipment-slot--minimal': minimal }]">
    <view class="equipment-slot__phase">
      <text>{{ phase }}</text>
    </view>
    <text class="equipment-slot__name">{{ name }}</text>

    <template v-if="!minimal">
      <text class="equipment-slot__skill">{{ skill }}</text>
      <text class="equipment-slot__tag">{{ tag }}</text>
    </template>
  </view>
</template>

<script setup lang="ts">
import type { EquipmentTheme } from "@/types/match";

withDefaults(
  defineProps<{
    name: string;
    phase: string;
    skill?: string;
    tag?: string;
    theme?: EquipmentTheme;
    minimal?: boolean;
  }>(),
  {
    skill: "",
    tag: "",
    theme: "solar",
    minimal: false,
  },
);
</script>

<style scoped lang="scss">
.equipment-slot {
  position: relative;
  overflow: hidden;
  min-height: 164rpx;
  padding: 18rpx;
  border-radius: 22rpx;
  border: 2rpx solid rgba(74, 54, 32, 0.75);
  box-shadow:
    inset 0 2rpx 0 rgba(255, 255, 255, 0.18),
    0 12rpx 24rpx rgba(0, 0, 0, 0.24);
}

.equipment-slot::before {
  content: "";
  position: absolute;
  inset: 8rpx;
  border-radius: 16rpx;
  border: 1rpx solid rgba(92, 60, 29, 0.24);
}

.equipment-slot--solar {
  background: linear-gradient(160deg, #f5ddb3 0%, #d6b17b 48%, #8a6030 100%);
}

.equipment-slot--frost {
  background: linear-gradient(160deg, #d3edf7 0%, #93bed2 48%, #446273 100%);
}

.equipment-slot--jade {
  background: linear-gradient(160deg, #d9edd2 0%, #8bb48d 48%, #3a5e4f 100%);
}

.equipment-slot--minimal {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 82rpx;
  min-width: 82rpx;
  height: 82rpx;
  min-height: 82rpx;
  padding: 8rpx;
  border-radius: 18rpx;
}

.equipment-slot--minimal::before {
  inset: 3rpx;
  border-radius: 14rpx;
}

.equipment-slot__phase {
  position: absolute;
  top: 10rpx;
  right: 10rpx;
  z-index: 1;
  min-width: 42rpx;
  padding: 6rpx 10rpx;
  border-radius: 999rpx;
  background: rgba(19, 14, 10, 0.72);
  color: #fff0d3;
  text-align: center;
  font-size: 20rpx;
  font-weight: 700;
}

.equipment-slot--minimal .equipment-slot__phase {
  top: 50%;
  right: auto;
  left: 50%;
  min-width: 0;
  padding: 0;
  background: transparent;
  transform: translate(-50%, -58%);
  font-size: 26rpx;
  line-height: 1;
  letter-spacing: 1rpx;
}

.equipment-slot__name,
.equipment-slot__skill,
.equipment-slot__tag {
  position: relative;
  z-index: 1;
  display: block;
}

.equipment-slot__name {
  margin-top: 20rpx;
  font-size: 30rpx;
  font-weight: 700;
  color: #33200f;
}

.equipment-slot--minimal .equipment-slot__name {
  position: absolute;
  right: 8rpx;
  bottom: 8rpx;
  left: 8rpx;
  margin-top: 0;
  font-size: 12rpx;
  line-height: 1.05;
  text-align: center;
}

.equipment-slot__skill {
  margin-top: 12rpx;
  font-size: 24rpx;
  font-weight: 600;
  color: rgba(38, 23, 12, 0.86);
}

.equipment-slot__tag {
  margin-top: 18rpx;
  font-size: 21rpx;
  color: rgba(38, 23, 12, 0.72);
}
</style>
