<template>
  <view class="battlefield-arena">
    <BattlefieldSlot
      class="battlefield-arena__slot battlefield-arena__slot--opponent"
      side="opponent"
      :card="opponentCard"
      :ready="opponentReady"
      :reveal="isRevealing"
    />

    <BattlefieldSlot
      class="battlefield-arena__slot battlefield-arena__slot--self"
      side="self"
      :card="playerCard"
      :ready="playerReady"
      :reveal="isRevealing"
    />
  </view>
</template>

<script setup lang="ts">
import BattlefieldSlot from "@/components/battle/BattlefieldSlot.vue";
import type { BattleCardModel } from "@/types/match";

const props = withDefaults(
  defineProps<{
    playerCard: BattleCardModel | null;
    opponentCard: BattleCardModel | null;
    playerReady?: boolean;
    opponentReady?: boolean;
    isRevealing?: boolean;
  }>(),
  {
    playerReady: false,
    opponentReady: false,
    isRevealing: false,
  },
);
</script>

<style scoped lang="scss">
.battlefield-arena {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 18rpx;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  backdrop-filter: none;
}

.battlefield-arena__slot {
  position: relative;
  flex: 0 0 auto;
}
</style>
