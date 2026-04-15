<template>
  <view class="start-page">
    <view class="start-page__grain" />
    <view class="start-page__halo start-page__halo--top" />
    <view class="start-page__halo start-page__halo--bottom" />

    <view class="start-shell">
      <view class="hero">
        <view class="hero__copy">
          <text class="brand__title">别笑你也蓄不过 AI</text>
          <text class="meta__desc">
            用蓄能、装备与翻牌时机，在短回合里完成一场紧张干净的对局。
          </text>
          <text class="meta__version">Beta 1.1.1</text>
        </view>

        <view class="hero__crest">
          <view class="hero__crest-glow" />
          <image class="hero__icon" src="/static/icon.png" mode="aspectFill" />
        </view>
      </view>

      <view class="actions">
        <view class="action action--primary" @tap="handleStartBattle">
          <text class="action__title">开始对局</text>
        </view>

        <view class="action action--accent" @tap="handleOpenOnlineLobby">
          <text class="action__title">联机大厅</text>
        </view>

        <view class="action action--secondary" @tap="handlePlaceholder('规则说明')">
          <text class="action__title">规则说明</text>
        </view>

        <view class="action action--secondary" @tap="handlePlaceholder('更多内容')">
          <text class="action__title">更多内容</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
function handleStartBattle() {
  uni.navigateTo({
    url: "/pages/battle/BattlePage",
  });
}

function handleOpenOnlineLobby() {
  uni.navigateTo({
    url: "/pages/online/lobby/index",
  });
}

function handlePlaceholder(label: string) {
  uni.showToast({
    title: `${label}后续开发`,
    icon: "none",
  });
}
</script>

<style scoped lang="scss">
.start-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 0%, rgba(244, 198, 97, 0.16), transparent 28%),
    radial-gradient(circle at 100% 14%, rgba(42, 111, 146, 0.18), transparent 24%),
    linear-gradient(180deg, #08131a 0%, #0d1e29 48%, #091119 100%);
}

.start-page__grain {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%) 0 0 / 22rpx 22rpx,
    linear-gradient(225deg, rgba(255, 255, 255, 0.012) 25%, transparent 25%) 0 0 / 28rpx 28rpx;
  opacity: 0.45;
  pointer-events: none;
}

.start-page__halo {
  position: absolute;
  border-radius: 999rpx;
  filter: blur(42rpx);
  pointer-events: none;
}

.start-page__halo--top {
  top: 120rpx;
  left: -80rpx;
  width: 260rpx;
  height: 260rpx;
  background: rgba(39, 122, 192, 0.16);
}

.start-page__halo--bottom {
  right: -60rpx;
  bottom: 180rpx;
  width: 280rpx;
  height: 280rpx;
  background: rgba(214, 168, 92, 0.12);
}

.start-shell {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: calc(12rpx + env(safe-area-inset-top)) 34rpx calc(28rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.brand__title {
  font-size: 44rpx;
  line-height: 1.18;
  font-weight: 900;
  color: #fff2d2;
  text-shadow: 0 0 22rpx rgba(233, 196, 106, 0.18);
  text-align: center;
}

.meta__desc {
  font-size: 22rpx;
  line-height: 1.6;
  color: #9aaeb9;
  text-align: center;
}

.meta__version {
  font-size: 20rpx;
  font-weight: 700;
  color: rgba(255, 223, 170, 0.88);
}

.hero {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10rpx 0 0;
}

.hero__copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
  width: 100%;
  padding: 0 8rpx;
}

.hero__crest {
  position: relative;
  width: 430rpx;
  height: 430rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 18rpx;
}

.hero__crest::before {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 35%, rgba(255, 255, 255, 0.05), transparent 54%),
    linear-gradient(180deg, rgba(12, 31, 49, 0.6), rgba(6, 15, 23, 0.12));
  opacity: 0.9;
}

.hero__crest-glow {
  position: absolute;
  inset: 34rpx;
  border-radius: 50%;
  background: radial-gradient(circle at center, rgba(62, 134, 208, 0.26), rgba(8, 18, 27, 0) 70%);
  filter: blur(18rpx);
}

.hero__icon {
  position: relative;
  z-index: 1;
  width: 340rpx;
  height: 340rpx;
  border-radius: 50%;
  box-shadow: 0 18rpx 40rpx rgba(0, 0, 0, 0.28);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.action {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 108rpx;
  padding: 0 28rpx;
  border-radius: 999rpx;
  box-shadow: 0 14rpx 28rpx rgba(0, 0, 0, 0.22);
}

.action--primary {
  background:
    linear-gradient(180deg, rgba(159, 113, 42, 0.96), rgba(88, 55, 16, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent);
}

.action--accent {
  background:
    linear-gradient(180deg, rgba(30, 90, 104, 0.96), rgba(10, 41, 50, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent);
}

.action--secondary {
  background:
    linear-gradient(180deg, rgba(24, 42, 58, 0.96), rgba(12, 24, 35, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent);
}

.action__title {
  font-size: 34rpx;
  font-weight: 800;
  color: #f6efe0;
}
</style>
