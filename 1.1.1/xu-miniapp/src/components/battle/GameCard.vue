<template>
  <view
    class="game-card"
    :class="[
      `game-card--${theme}`,
      {
        'game-card--compact': compact,
        'game-card--interactive': interactive,
        'game-card--disabled': disabled,
        'game-card--crushed': crushed,
        'game-card--face-down': faceDown,
      },
    ]"
    @tap="handleTap"
  >
    <template v-if="faceDown">
      <view class="game-card__back-foil" />
      <view class="game-card__back-frame">
        <view class="game-card__back-orbit game-card__back-orbit--one" />
        <view class="game-card__back-orbit game-card__back-orbit--two" />
        <view class="game-card__back-core">
          <text class="game-card__back-glyph">蓄</text>
        </view>
        <text class="game-card__back-title">{{ backLabel }}</text>
      </view>
    </template>

    <template v-else>
      <view class="game-card__foil" />
      <view class="game-card__frame">
        <view class="game-card__topline">
          <text class="game-card__kind">{{ kind }}</text>
          <text class="game-card__cost">蓄 {{ costLabel }}</text>
        </view>

        <view class="game-card__title">
          <text class="game-card__name">{{ name }}</text>
          <text v-if="subtitle" class="game-card__subtitle">{{ subtitle }}</text>
        </view>

        <view class="game-card__stats">
          <view class="game-card__stat">
            <text class="game-card__stat-label">攻</text>
            <text class="game-card__stat-value">{{ attackLabel }}</text>
          </view>
          <view class="game-card__stat">
            <text class="game-card__stat-label">防</text>
            <text class="game-card__stat-value">{{ defenseLabel }}</text>
          </view>
        </view>

        <view v-if="keywords.length" class="game-card__keywords">
          <text
            v-for="keyword in keywords"
            :key="`${name}-${keyword}`"
            class="game-card__keyword"
          >
            {{ keyword }}
          </text>
        </view>

        <text class="game-card__special">{{ specialText }}</text>
      </view>
    </template>

    <view v-if="disabled && disabledLabel" class="game-card__disabled-badge">
      <text>{{ disabledLabel }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { CardKind, CardTheme } from "@/types/match";

const props = withDefaults(
  defineProps<{
    name: string;
    kind: CardKind;
    subtitle?: string;
    costLabel: string;
    attackLabel: string;
    defenseLabel: string;
    specialText: string;
    keywords?: string[];
    theme?: CardTheme;
    compact?: boolean;
    interactive?: boolean;
    disabled?: boolean;
    disabledLabel?: string;
    crushed?: boolean;
    faceDown?: boolean;
    backLabel?: string;
  }>(),
  {
    subtitle: "",
    keywords: () => [],
    theme: "paper",
    compact: false,
    interactive: false,
    disabled: false,
    disabledLabel: "",
    crushed: false,
    faceDown: false,
    backLabel: "已出牌",
  },
);

const emit = defineEmits<{
  (e: "select"): void;
}>();

function handleTap() {
  if (!props.interactive || props.faceDown) {
    return;
  }

  emit("select");
}
</script>

<style scoped lang="scss">
.game-card {
  position: relative;
  overflow: hidden;
  width: 196rpx;
  min-height: 276rpx;
  border-radius: 24rpx;
  border: 3rpx solid #4b3119;
  box-shadow:
    0 18rpx 34rpx rgba(0, 0, 0, 0.42),
    inset 0 2rpx 0 rgba(255, 255, 255, 0.2);
}

.game-card--compact {
  width: 100%;
  min-height: 224rpx;
}

.game-card--paper {
  background: linear-gradient(165deg, #f3e8cc 0%, #ddc89d 52%, #b28f5f 100%);
}

.game-card--azure {
  background: linear-gradient(165deg, #dce8ef 0%, #9fc0cf 52%, #58768a 100%);
}

.game-card--storm {
  background: linear-gradient(165deg, #e0ddf0 0%, #9d95c7 52%, #564f86 100%);
}

.game-card--crimson {
  background: linear-gradient(165deg, #f0d5cf 0%, #d59a8e 52%, #8d4a43 100%);
}

.game-card--gold {
  background: linear-gradient(165deg, #f6ebc4 0%, #e0bb67 52%, #a56b24 100%);
}

.game-card--base {
  background: linear-gradient(165deg, #f4ecd2 0%, #decba4 52%, #b18e5e 100%);
}

.game-card--pegasus {
  background: linear-gradient(165deg, #edf4ff 0%, #a6c6f3 48%, #5a82bb 100%);
}

.game-card--frost {
  background: linear-gradient(165deg, #edf9ff 0%, #9fd4ea 48%, #4d7d95 100%);
}

.game-card--dragon {
  background: linear-gradient(165deg, #efe9ff 0%, #b6a8eb 48%, #6654a8 100%);
}

.game-card--immune {
  background: linear-gradient(165deg, #ecf8dd 0%, #b6d98c 48%, #628347 100%);
}

.game-card--justice {
  background: linear-gradient(165deg, #f5f7fb 0%, #c8d2e0 48%, #738194 100%);
}

.game-card--guardian {
  background: linear-gradient(165deg, #f5e7d2 0%, #d2ae7b 48%, #8f6338 100%);
}

.game-card--wolf {
  background: linear-gradient(165deg, #fde9dd 0%, #e2a17f 48%, #984c3f 100%);
}

.game-card--super {
  background: linear-gradient(165deg, #f7f0ff 0%, #ccb6f2 48%, #6d58ab 100%);
}

.game-card--interactive {
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.game-card--disabled {
  opacity: 0.82;
}

.game-card--crushed {
  filter: brightness(0.5) saturate(0.7);
  animation: game-card-shake 0.42s infinite;
}

.game-card--face-down {
  border-color: rgba(210, 177, 108, 0.52);
  background:
    radial-gradient(circle at 50% 18%, rgba(255, 244, 211, 0.18), transparent 30%),
    linear-gradient(155deg, #082036 0%, #113a57 46%, #221009 100%);
}

.game-card__foil {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background:
    linear-gradient(130deg, rgba(255, 255, 255, 0.36), transparent 28%),
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.28), transparent 34%);
  pointer-events: none;
}

.game-card__frame {
  position: absolute;
  inset: 10rpx;
  display: flex;
  flex-direction: column;
  border-radius: 18rpx;
  padding: 16rpx 14rpx 14rpx;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.18), transparent 12%),
    linear-gradient(180deg, rgba(252, 245, 228, 0.96), rgba(239, 228, 194, 0.96) 42%, rgba(222, 206, 159, 0.96) 100%);
  border: 2rpx solid rgba(93, 60, 30, 0.26);
}

.game-card__topline,
.game-card__stats {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.game-card__kind {
  flex-shrink: 0;
  padding: 6rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(63, 40, 19, 0.12);
  font-size: 20rpx;
  font-weight: 700;
  color: #513219;
}

.game-card__cost {
  margin-left: 8rpx;
  white-space: nowrap;
  flex-shrink: 0;
  text-align: right;
  font-size: 22rpx;
  font-weight: 700;
  color: #734a1d;
}

.game-card__title {
  margin-top: 14rpx;
}

.game-card__name {
  display: block;
  font-size: 32rpx;
  font-weight: 800;
  color: #2f1e11;
}

.game-card__subtitle {
  display: block;
  margin-top: 6rpx;
  font-size: 20rpx;
  color: rgba(60, 39, 20, 0.7);
}

.game-card__stats {
  gap: 8rpx;
  margin-top: 16rpx;
}

.game-card__stat {
  flex: 1;
  padding: 10rpx 8rpx;
  border-radius: 16rpx;
  background: rgba(79, 48, 16, 0.08);
  text-align: center;
}

.game-card__stat-label {
  display: block;
  font-size: 18rpx;
  color: rgba(72, 46, 25, 0.64);
}

.game-card__stat-value {
  display: block;
  margin-top: 4rpx;
  font-size: 28rpx;
  font-weight: 800;
  color: #422814;
}

.game-card__keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  margin-top: 14rpx;
}

.game-card__keyword {
  padding: 6rpx 10rpx;
  border-radius: 999rpx;
  background: rgba(80, 51, 21, 0.09);
  font-size: 18rpx;
  color: #5a3a1d;
}

.game-card__special {
  display: block;
  margin-top: 14rpx;
  font-size: 20rpx;
  line-height: 1.5;
  color: rgba(53, 35, 18, 0.82);
}

.game-card__disabled-badge {
  position: absolute;
  top: 12rpx;
  right: 12rpx;
  z-index: 2;
  padding: 6rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(35, 24, 14, 0.78);
  color: #ffdfa7;
  font-size: 18rpx;
  font-weight: 700;
}

.game-card__back-foil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.12), transparent 30%),
    radial-gradient(circle at 50% 20%, rgba(246, 210, 136, 0.22), transparent 36%);
}

.game-card__back-frame {
  position: absolute;
  inset: 10rpx;
  border-radius: 18rpx;
  border: 2rpx solid rgba(235, 201, 133, 0.36);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), transparent 18%),
    linear-gradient(180deg, rgba(10, 29, 47, 0.94), rgba(8, 20, 35, 0.98));
}

.game-card__back-orbit {
  position: absolute;
  inset: 24rpx;
  border-radius: 50%;
  border: 2rpx solid rgba(243, 210, 146, 0.16);
}

.game-card__back-orbit--two {
  inset: 44rpx 28rpx;
  transform: rotate(42deg);
}

.game-card__back-core {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 84rpx;
  height: 84rpx;
  margin-top: -52rpx;
  margin-left: -42rpx;
  border-radius: 24rpx;
  border: 2rpx solid rgba(244, 210, 145, 0.36);
  background: linear-gradient(180deg, rgba(159, 113, 42, 0.92), rgba(88, 50, 13, 0.98));
  box-shadow: 0 0 22rpx rgba(241, 196, 104, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
}

.game-card__back-glyph {
  font-size: 40rpx;
  font-weight: 800;
  color: #fff0cc;
}

.game-card__back-title {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 24rpx;
  text-align: center;
  font-size: 22rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
  color: rgba(247, 231, 197, 0.92);
}

@keyframes game-card-shake {
  0%,
  100% {
    transform: translateX(0);
  }

  20% {
    transform: translateX(-5rpx);
  }

  40% {
    transform: translateX(5rpx);
  }

  60% {
    transform: translateX(-4rpx);
  }

  80% {
    transform: translateX(4rpx);
  }
}
</style>
