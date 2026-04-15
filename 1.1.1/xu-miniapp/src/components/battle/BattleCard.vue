<template>
  <view class="card" :class="[`card-${card.state}`, { 'card-compact': compact }]">
    <view class="card__glow" :style="{ background: card.accent }" />
    <view class="card__header">
      <text class="card__kind">{{ card.kind }}</text>
      <text class="card__cost">蓄 {{ card.cost }}</text>
    </view>

    <view class="card__body">
      <text class="card__name">{{ card.name }}</text>
      <text class="card__effect">{{ card.effect }}</text>
    </view>

    <view class="card__footer">
      <text class="card__value">攻 {{ card.attack ?? "-" }}</text>
      <text class="card__value">守 {{ card.defense ?? "-" }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { BattleCardPreview } from "@/types/battle";

withDefaults(
  defineProps<{
    card: BattleCardPreview;
    compact?: boolean;
  }>(),
  {
    compact: false,
  },
);
</script>

<style scoped lang="scss">
.card {
  position: relative;
  overflow: hidden;
  min-height: 220rpx;
  padding: 20rpx;
  border-radius: 24rpx;
  border: 1rpx solid rgba(214, 168, 92, 0.18);
  background: linear-gradient(180deg, rgba(16, 35, 49, 0.96), rgba(8, 20, 29, 0.96));
}

.card-compact {
  min-height: 180rpx;
}

.card__glow {
  position: absolute;
  inset: auto -10% -35% auto;
  width: 180rpx;
  height: 180rpx;
  border-radius: 999rpx;
  opacity: 0.16;
  filter: blur(24rpx);
}

.card__header,
.card__footer {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card__kind,
.card__cost,
.card__value {
  font-size: 22rpx;
  color: $uni-text-color-grey;
}

.card__body {
  position: relative;
  z-index: 1;
  margin: 26rpx 0 20rpx;
}

.card__name {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: $uni-color-title;
}

.card__effect {
  display: block;
  margin-top: 10rpx;
  font-size: 24rpx;
  line-height: 1.5;
  color: $uni-color-paragraph;
}

.card-charged {
  box-shadow: 0 0 24rpx rgba(214, 168, 92, 0.18);
}

.card-locked {
  opacity: 0.7;
}
</style>
