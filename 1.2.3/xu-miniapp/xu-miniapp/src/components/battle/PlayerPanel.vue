<template>
  <view class="panel" :class="{ 'panel-self': isSelf }">
    <view class="panel__header">
      <view>
        <text class="panel__name">{{ player.name }}</text>
        <text class="panel__status">{{ player.statusLabel }}</text>
      </view>
      <view class="panel__tag" :class="{ 'panel__tag-active': player.rateUnlocked }">
        <text>{{ player.rateUnlocked ? "超率已解锁" : "蓄能中" }}</text>
      </view>
    </view>

    <view class="panel__meter">
      <view class="meter-label">
        <text>生命</text>
        <text>{{ player.hp }}/{{ player.maxHp }}</text>
      </view>
      <view class="meter-track">
        <view class="meter-fill meter-fill-hp" :style="{ width: hpWidth }" />
      </view>
    </view>

    <view class="panel__meter">
      <view class="meter-label">
        <text>蓄能</text>
        <text>{{ player.energy }}/{{ player.maxEnergy }}</text>
      </view>
      <view class="energy-row">
        <view
          v-for="index in player.maxEnergy"
          :key="index"
          class="energy-dot"
          :class="{ 'energy-dot-on': index <= player.energy }"
        />
      </view>
    </view>

    <view class="panel__footer">
      <text>牌库 {{ player.deckCount }}</text>
      <text>{{ isSelf ? "我方" : "对手" }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { BattlePlayerPreview } from "@/types/battle";

const props = withDefaults(
  defineProps<{
    player: BattlePlayerPreview;
    isSelf?: boolean;
  }>(),
  {
    isSelf: false,
  },
);

const hpWidth = computed(() => `${(props.player.hp / props.player.maxHp) * 100}%`);
</script>

<style scoped lang="scss">
.panel {
  padding: 24rpx;
  border: 1rpx solid rgba(214, 168, 92, 0.16);
  border-radius: 28rpx;
  background: linear-gradient(180deg, rgba(18, 39, 53, 0.92), rgba(10, 23, 33, 0.92));
  box-shadow: 0 18rpx 36rpx rgba(3, 9, 14, 0.24);
}

.panel-self {
  background: linear-gradient(180deg, rgba(28, 51, 61, 0.95), rgba(10, 24, 33, 0.95));
}

.panel__header,
.panel__footer,
.meter-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel__name {
  display: block;
  font-size: 32rpx;
  font-weight: 600;
  color: $uni-color-title;
}

.panel__status {
  display: block;
  margin-top: 6rpx;
  font-size: 22rpx;
  color: $uni-text-color-grey;
}

.panel__tag {
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.06);
  font-size: 20rpx;
  color: $uni-text-color-grey;
}

.panel__tag-active {
  color: #ffe3a8;
  background: rgba(214, 168, 92, 0.18);
  box-shadow: 0 0 18rpx rgba(214, 168, 92, 0.22);
}

.panel__meter {
  margin-top: 18rpx;
}

.meter-label {
  margin-bottom: 10rpx;
  font-size: 22rpx;
  color: $uni-text-color-grey;
}

.meter-track {
  overflow: hidden;
  height: 14rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.08);
}

.meter-fill {
  height: 100%;
  border-radius: inherit;
}

.meter-fill-hp {
  background: linear-gradient(90deg, #ed766e, #f0c36f);
}

.energy-row {
  display: flex;
  gap: 10rpx;
}

.energy-dot {
  width: 22rpx;
  height: 22rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.12);
  border: 1rpx solid rgba(214, 168, 92, 0.16);
}

.energy-dot-on {
  background: radial-gradient(circle, #ffe4a1 0%, #d6a85c 70%);
  box-shadow: 0 0 18rpx rgba(214, 168, 92, 0.3);
}

.panel__footer {
  margin-top: 18rpx;
  font-size: 22rpx;
  color: $uni-text-color-grey;
}
</style>
