<template>
  <view
    class="battlefield-slot"
    :class="[
      `battlefield-slot--${side}`,
      {
        'battlefield-slot--ready': ready,
        'battlefield-slot--revealing': reveal && !!card,
        'battlefield-slot--filled': !!card,
      },
    ]"
  >
    <view class="battlefield-slot__head" :class="{ 'battlefield-slot__head--ready': ready }">
      <text class="battlefield-slot__head-text">{{ slotStatusLabel }}</text>
    </view>

    <view class="battlefield-slot__surface">
      <view v-if="card" class="battlefield-slot__card-shell">
        <view class="battlefield-slot__card-stage" :class="{ 'battlefield-slot__card-stage--flipping': isFlipping }">
          <view
            class="battlefield-slot__card-face battlefield-slot__card-face--back slot-card-back"
            :class="{ 'battlefield-slot__card-face--hidden': isFrontVisible }"
          >
            <view class="slot-card-back__foil" />
            <view class="slot-card-back__frame">
              <view class="slot-card-back__ring slot-card-back__ring--one" />
              <view class="slot-card-back__ring slot-card-back__ring--two" />
              <view class="slot-card-back__core">
                <text class="slot-card-back__glyph">蓄</text>
              </view>
            </view>
          </view>

          <view
            class="battlefield-slot__card-face battlefield-slot__card-face--front slot-card-front"
            :class="[
              `slot-card-front--${card.theme}`,
              {
                'battlefield-slot__card-face--visible': isFrontVisible,
                'slot-card-front--crushed': card.isCrushed,
              },
            ]"
          >
            <view class="slot-card-front__foil" />
            <view class="slot-card-front__frame">
              <view class="slot-card-front__topline">
                <text class="slot-card-front__kind">{{ card.kind }}</text>
                <text class="slot-card-front__cost">{{ card.costLabel }}</text>
              </view>

              <view class="slot-card-front__title">
                <text class="slot-card-front__name">{{ card.name }}</text>
                <text class="slot-card-front__subtitle">{{ card.subtitle }}</text>
              </view>

              <view v-if="primaryKeyword" class="slot-card-front__keyword">
                <text>{{ primaryKeyword }}</text>
              </view>

              <view class="slot-card-front__stats">
                <view class="slot-card-front__stat">
                  <text class="slot-card-front__stat-label">攻</text>
                  <text class="slot-card-front__stat-value">{{ card.attackLabel }}</text>
                </view>
                <view class="slot-card-front__stat">
                  <text class="slot-card-front__stat-label">防</text>
                  <text class="slot-card-front__stat-value">{{ card.defenseLabel }}</text>
                </view>
              </view>
            </view>
          </view>
        </view>
        <view class="battlefield-slot__glow" />
      </view>

      <view v-else class="battlefield-slot__placeholder">
        <view class="battlefield-slot__placeholder-frame" />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import type { BattleCardModel } from "@/types/match";

const props = withDefaults(
  defineProps<{
    side: "opponent" | "self";
    card: BattleCardModel | null;
    ready?: boolean;
    reveal?: boolean;
  }>(),
  {
    ready: false,
    reveal: false,
  },
);

const slotStatusLabel = computed(() =>
  `${props.side === "opponent" ? "对方出牌" : "我方出牌"}${props.ready ? "已锁定" : "未锁定"}`,
);

const primaryKeyword = computed(() => props.card?.keywords?.[0] ?? "");

const isFrontVisible = ref(false);
const isFlipping = ref(false);

let flipMidTimer: ReturnType<typeof setTimeout> | null = null;
let flipEndTimer: ReturnType<typeof setTimeout> | null = null;

function clearFlipTimers() {
  if (flipMidTimer) {
    clearTimeout(flipMidTimer);
    flipMidTimer = null;
  }
  if (flipEndTimer) {
    clearTimeout(flipEndTimer);
    flipEndTimer = null;
  }
}

watch(
  () => [props.reveal, props.card?.id] as const,
  ([reveal]) => {
    clearFlipTimers();

    if (!props.card) {
      isFrontVisible.value = false;
      isFlipping.value = false;
      return;
    }

    if (!reveal) {
      isFrontVisible.value = false;
      isFlipping.value = false;
      return;
    }

    isFrontVisible.value = false;
    isFlipping.value = true;

    flipMidTimer = setTimeout(() => {
      isFrontVisible.value = true;
    }, 210);

    flipEndTimer = setTimeout(() => {
      isFlipping.value = false;
    }, 520);
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  clearFlipTimers();
});
</script>

<style scoped lang="scss">
.battlefield-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8rpx;
  min-height: 0;
}

.battlefield-slot__head {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 116rpx;
  min-height: 24rpx;
  padding: 0 10rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(154, 170, 182, 0.2);
  background: rgba(69, 84, 95, 0.28);
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.04);
}

.battlefield-slot__head--ready {
  border-color: rgba(85, 204, 128, 0.3);
  background: rgba(40, 117, 58, 0.42);
  box-shadow:
    inset 0 1rpx 0 rgba(255, 255, 255, 0.08),
    0 0 16rpx rgba(67, 188, 109, 0.16);
}

.battlefield-slot__head-text {
  font-size: 10rpx;
  font-weight: 700;
  line-height: 1;
  color: #8f9faa;
  white-space: nowrap;
}

.battlefield-slot__head--ready .battlefield-slot__head-text {
  color: #8ef0ab;
}

.battlefield-slot__surface {
  position: relative;
  width: 58rpx;
  height: 82rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.battlefield-slot__placeholder,
.battlefield-slot__card-shell {
  position: relative;
  width: 58rpx;
  height: 82rpx;
}

.battlefield-slot__placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
}

.battlefield-slot__placeholder-frame {
  width: 100%;
  height: 100%;
  border-radius: 14rpx;
  border: 2rpx dashed rgba(122, 153, 176, 0.22);
  background:
    radial-gradient(circle at center, rgba(107, 182, 255, 0.06), transparent 55%),
    rgba(9, 20, 31, 0.42);
}

.battlefield-slot__card-shell {
  overflow: visible;
}

.battlefield-slot__card-stage {
  position: relative;
  width: 58rpx;
  height: 82rpx;
  transform-origin: center center;
}

.battlefield-slot__card-stage--flipping {
  animation: battlefield-slot-flip 0.52s cubic-bezier(0.2, 0.8, 0.2, 1);
}

.battlefield-slot__card-face {
  position: absolute;
  inset: 0;
  border-radius: 14rpx;
  overflow: hidden;
  transition:
    opacity 0.1s linear,
    filter 0.22s ease;
}

.battlefield-slot__card-face--back {
  opacity: 1;
}

.battlefield-slot__card-face--front {
  opacity: 0;
}

.battlefield-slot__card-face--hidden {
  opacity: 0;
}

.battlefield-slot__card-face--visible {
  opacity: 1;
  filter: drop-shadow(0 0 10rpx rgba(255, 227, 168, 0.14));
}

.slot-card-back {
  border: 2rpx solid rgba(205, 174, 114, 0.46);
  background:
    radial-gradient(circle at 50% 18%, rgba(255, 244, 211, 0.18), transparent 32%),
    linear-gradient(160deg, rgba(8, 30, 49, 0.98), rgba(15, 50, 76, 0.96) 54%, rgba(33, 15, 9, 0.98));
  box-shadow:
    0 4rpx 10rpx rgba(0, 0, 0, 0.24),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.08);
}

.slot-card-back__foil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.1), transparent 30%),
    radial-gradient(circle at 50% 20%, rgba(246, 210, 136, 0.16), transparent 36%);
}

.slot-card-back__frame {
  position: absolute;
  inset: 4rpx;
  border-radius: 10rpx;
  border: 1rpx solid rgba(235, 201, 133, 0.34);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), transparent 18%),
    linear-gradient(180deg, rgba(9, 24, 37, 0.9), rgba(7, 17, 24, 0.94));
}

.slot-card-back__ring {
  position: absolute;
  border-radius: 50%;
  border: 1rpx solid rgba(243, 210, 146, 0.14);
}

.slot-card-back__ring--one {
  inset: 8rpx;
}

.slot-card-back__ring--two {
  inset: 14rpx 10rpx;
  transform: rotate(40deg);
}

.slot-card-back__core {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 20rpx;
  height: 20rpx;
  border-radius: 50%;
  border: 1rpx solid rgba(236, 203, 137, 0.3);
  background: rgba(15, 36, 52, 0.8);
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.slot-card-back__glyph {
  font-size: 10rpx;
  font-weight: 800;
  color: rgba(255, 239, 196, 0.92);
}

.slot-card-front {
  border: 2rpx solid #6f4a22;
  box-shadow:
    0 5rpx 10rpx rgba(0, 0, 0, 0.22),
    inset 0 1rpx 0 rgba(255, 255, 255, 0.16);
}

.slot-card-front--paper {
  background: linear-gradient(165deg, #f3e8cc 0%, #ddc89d 52%, #b28f5f 100%);
}

.slot-card-front--azure {
  background: linear-gradient(165deg, #dce8ef 0%, #9fc0cf 52%, #58768a 100%);
}

.slot-card-front--storm {
  background: linear-gradient(165deg, #e0ddf0 0%, #9d95c7 52%, #564f86 100%);
}

.slot-card-front--crimson {
  background: linear-gradient(165deg, #f0d5cf 0%, #d59a8e 52%, #8d4a43 100%);
}

.slot-card-front--gold,
.slot-card-front--base,
.slot-card-front--super {
  background: linear-gradient(165deg, #f6ebc4 0%, #e0bb67 52%, #a56b24 100%);
}

.slot-card-front--pegasus {
  background: linear-gradient(165deg, #edf4ff 0%, #a6c6f3 48%, #5a82bb 100%);
}

.slot-card-front--frost {
  background: linear-gradient(165deg, #edf9ff 0%, #9fd4ea 48%, #4d7d95 100%);
}

.slot-card-front--dragon {
  background: linear-gradient(165deg, #efe9ff 0%, #b6a8eb 48%, #6654a8 100%);
}

.slot-card-front--immune {
  background: linear-gradient(165deg, #ecf8dd 0%, #b6d98c 48%, #628347 100%);
}

.slot-card-front--justice {
  background: linear-gradient(165deg, #f5f7fb 0%, #c8d2e0 48%, #738194 100%);
}

.slot-card-front--guardian {
  background: linear-gradient(165deg, #f5e7d2 0%, #d2ae7b 48%, #8f6338 100%);
}

.slot-card-front--wolf {
  background: linear-gradient(165deg, #fde9dd 0%, #e2a17f 48%, #984c3f 100%);
}

.slot-card-front--crushed {
  filter: saturate(0.72) brightness(0.72);
}

.slot-card-front__foil {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(130deg, rgba(255, 255, 255, 0.28), transparent 28%),
    radial-gradient(circle at top right, rgba(255, 255, 255, 0.16), transparent 36%);
}

.slot-card-front__frame {
  position: absolute;
  inset: 3rpx;
  display: flex;
  flex-direction: column;
  padding: 4rpx;
  border-radius: 10rpx;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.16), transparent 12%),
    linear-gradient(180deg, rgba(252, 245, 228, 0.95), rgba(239, 228, 194, 0.94) 42%, rgba(222, 206, 159, 0.95) 100%);
  border: 1rpx solid rgba(93, 60, 30, 0.22);
}

.slot-card-front__topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 3rpx;
}

.slot-card-front__kind,
.slot-card-front__cost {
  flex-shrink: 0;
  font-weight: 800;
  color: #5e3d1f;
}

.slot-card-front__kind {
  padding: 2rpx 5rpx;
  border-radius: 999rpx;
  background: rgba(63, 40, 19, 0.08);
  font-size: 6rpx;
}

.slot-card-front__cost {
  font-size: 7rpx;
}

.slot-card-front__title {
  margin-top: 5rpx;
}

.slot-card-front__name {
  display: block;
  font-size: 12rpx;
  line-height: 1.05;
  font-weight: 900;
  color: #2f1e11;
  word-break: break-all;
}

.slot-card-front__subtitle {
  display: block;
  margin-top: 2rpx;
  font-size: 6rpx;
  color: rgba(60, 39, 20, 0.72);
  line-height: 1.1;
}

.slot-card-front__keyword {
  align-self: flex-start;
  margin-top: 4rpx;
  padding: 2rpx 5rpx;
  border-radius: 999rpx;
  background: rgba(80, 51, 21, 0.08);
  color: #6d4823;
  font-size: 6rpx;
  line-height: 1;
}

.slot-card-front__stats {
  margin-top: auto;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 3rpx;
}

.slot-card-front__stat {
  min-width: 0;
  padding: 3rpx 2rpx;
  border-radius: 8rpx;
  background: rgba(79, 48, 16, 0.07);
  text-align: center;
}

.slot-card-front__stat-label {
  display: block;
  font-size: 5rpx;
  color: rgba(72, 46, 25, 0.66);
  line-height: 1;
}

.slot-card-front__stat-value {
  display: block;
  margin-top: 2rpx;
  font-size: 10rpx;
  line-height: 1;
  font-weight: 900;
  color: #422814;
}

.battlefield-slot__glow {
  position: absolute;
  inset: -6rpx;
  border-radius: 16rpx;
  background: radial-gradient(circle at center, rgba(89, 237, 157, 0.16), transparent 68%);
  opacity: 0;
  pointer-events: none;
}

.battlefield-slot--ready .battlefield-slot__glow {
  opacity: 1;
}

.battlefield-slot--revealing .battlefield-slot__glow {
  opacity: 1;
  background: radial-gradient(circle at center, rgba(255, 224, 145, 0.26), transparent 68%);
}

@keyframes battlefield-slot-flip {
  0% {
    transform: scaleX(1);
  }

  45% {
    transform: scaleX(0.06);
  }

  55% {
    transform: scaleX(0.06);
  }

  100% {
    transform: scaleX(1);
  }
}
</style>
