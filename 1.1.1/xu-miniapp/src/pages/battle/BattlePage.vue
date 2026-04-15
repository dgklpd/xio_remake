<template>
  <view class="battle-page" :style="hudStyleVars">
    <view class="battle-page__grain" />

    <view v-if="!gameStarted" class="start-overlay">
      <view class="start-overlay__backdrop" />
      <view class="start-modal">
        <view class="start-modal__emblem">蓄</view>
        <text class="start-modal__title">人机对战</text>
        <text class="start-modal__desc">目前人机版本Beta1.1</text>
        <view class="start-modal__btn start-modal__btn--primary" @tap="handleGameStart">
          <text>开始对局</text>
        </view>
        <view class="start-modal__btn start-modal__btn--ghost" @tap="handleGameExit">
          <text>返回</text>
        </view>
      </view>
    </view>

    <view class="battle-shell battle-shell--arena">
      <view class="battle-overlay-controls hud-panel" :style="overlayControlsStyle">
        <view class="battle-overlay-controls__score">
          <text>AI {{ enemyScore }}</text>
          <text class="battle-overlay-controls__divider">:</text>
          <text>{{ displayName }} {{ selfScore }}</text>
        </view>
        <view class="battle-overlay-controls__tools">
          <view class="battle-overlay-controls__timer">
            <text class="battle-overlay-controls__timer-value">{{ remainingSeconds }}s</text>
            <text class="battle-overlay-controls__timer-label">{{ phaseLabel }}</text>
          </view>
          <view class="battle-overlay-controls__start" @tap="handleStartBattle">
            <text>{{ connectionActionLabel }}</text>
          </view>
        </view>
      </view>

      <view class="battle-layout battle-layout--free" :style="freeLayoutStyle" @tap="handleOutsidePlayConfirm">
        <view
          class="player-hud player-hud--corner player-hud--enemy-corner hud-panel"
          :class="{ 'player-hud--dead': opponentPlayer.isDead }"
          :style="enemyHudStyle"
          @tap.stop
        >
          <view class="player-hud__head">
            <view class="player-hud__identity">
              <view class="player-hud__avatar player-hud__avatar--enemy"><text>AI</text></view>
              <view>
                <text class="player-hud__name">人机</text>
              </view>
            </view>
            <view class="player-hud__badges">
              <view
                class="player-hud__equip-anchor"
                @mouseenter="showEquipmentPopover('enemy')"
                @mouseleave="hideEquipmentPopover('enemy')"
                @tap.stop="toggleEquipmentPopover('enemy')"
              >
                <text class="pill">装备 {{ opponentPlayer.equipments.length }}</text>
                <view
                  v-if="equipmentGainToast.visible && equipmentGainToast.side === 'enemy'"
                  class="equip-gain-toast"
                >
                  <text>+1</text>
                </view>
                <view v-if="equipmentPopoverSide === 'enemy'" class="equipment-popover equipment-popover--enemy">
                  <text class="equipment-popover__title">对手装备</text>
                  <scroll-view scroll-y class="equipment-popover__scroll" show-scrollbar="false">
                    <view class="equipment-popover__list">
                      <EquipmentSlot
                        v-for="equip in opponentPlayer.equipments"
                        :key="`enemy-popover-${equip.id}`"
                        :name="equip.name"
                        :phase="equip.phase"
                        :theme="equip.theme"
                        minimal
                      />
                      <view v-if="!opponentPlayer.equipments.length" class="equipment-popover__empty">
                        <text>暂无装备</text>
                      </view>
                    </view>
                  </scroll-view>
                </view>
              </view>
            </view>
          </view>

          <view class="energy-box">
            <view class="energy-box__meta">
              <text>当前蓄能</text>
              <text class="energy-box__value">{{ opponentEnergyLabel }}</text>
            </view>
            <view class="energy-box__cells">
              <view
                v-for="(slot, index) in opponentEnergySlots"
                :key="`opp-energy-${index}`"
                class="energy-box__cell"
                :class="{ 'energy-box__cell--active': slot }"
              />
            </view>
          </view>

          <!--
          <scroll-view scroll-x class="equip-strip" show-scrollbar="false">
            <view class="equip-strip__track">
              <EquipmentSlot
                v-for="equip in opponentPlayer.equipments"
                :key="equip.id"
                :name="equip.name"
                :phase="equip.phase"
                :theme="equip.theme"
                minimal
              />
              <view v-if="!opponentPlayer.equipments.length" class="equip-strip__empty">
                <text>暂无装备</text>
              </view>
            </view>
          </scroll-view>
          -->
        </view>

        <view class="enemy-hand-fan" :style="enemyHandFanStyle">
          <view class="enemy-hand-fan__head">
            <text class="enemy-hand-fan__label">对手手牌</text>
            <text class="enemy-hand-fan__status" :class="{ 'enemy-hand-fan__status--ready': enemyReady }">
              {{ enemyReady ? "已出牌" : "待出牌" }}
            </text>
          </view>
          <view class="enemy-hand-fan__deck">
            <view
              v-for="(cardIndex, index) in enemyBackCards"
              :key="`enemy-back-${cardIndex}`"
              class="enemy-hand-fan__card"
              :style="getEnemyBackCardStyle(index, enemyBackCards.length)"
            >
              <view class="enemy-hand-fan__back">
                <view class="enemy-hand-fan__back-frame">
                  <view class="enemy-hand-fan__back-core">
                    <text class="enemy-hand-fan__back-glyph">蓄</text>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>

        <BattlefieldArena
          class="battlefield-arena--floating"
          :style="battlefieldArenaStyle"
          :player-card="selfPlayer.fieldCard"
          :opponent-card="opponentPlayer.fieldCard"
          :player-ready="myReady"
          :opponent-ready="enemyReady"
          :is-revealing="revealCards"
          :phase-label="phaseLabel"
          :battle-log="battleLog"
          :remaining-seconds="remainingSeconds"
        />

        <view
          class="command-panel player-hud player-hud--corner player-hud--self-corner hud-panel"
          :class="{ 'player-hud--dead': selfPlayer.isDead }"
          :style="selfHudStyle"
          @tap.stop
        >
          <view class="player-hud__head">
            <view class="player-hud__identity">
              <view class="player-hud__avatar">
                <image v-if="profile.avatarUrl" class="player-hud__avatar-image" :src="profile.avatarUrl" mode="aspectFill" />
                <text v-else>{{ avatarFallback }}</text>
              </view>
              <view>
                <text class="player-hud__name">{{ displayName }}</text>
              </view>
            </view>
            <view class="player-hud__badges">
              <view
                class="player-hud__equip-anchor"
                @mouseenter="showEquipmentPopover('self')"
                @mouseleave="hideEquipmentPopover('self')"
                @tap.stop="toggleEquipmentPopover('self')"
              >
                <text class="pill">装备 {{ selfPlayer.equipments.length }}</text>
                <view
                  v-if="equipmentGainToast.visible && equipmentGainToast.side === 'self'"
                  class="equip-gain-toast"
                >
                  <text>+1</text>
                </view>
                <view v-if="equipmentPopoverSide === 'self'" class="equipment-popover equipment-popover--self">
                  <text class="equipment-popover__title">我方装备</text>
                  <scroll-view scroll-y class="equipment-popover__scroll" show-scrollbar="false">
                    <view class="equipment-popover__list">
                      <EquipmentSlot
                        v-for="equip in selfPlayer.equipments"
                        :key="`self-popover-${equip.id}`"
                        :name="equip.name"
                        :phase="equip.phase"
                        :theme="equip.theme"
                        minimal
                      />
                      <view v-if="!selfPlayer.equipments.length" class="equipment-popover__empty">
                        <text>暂无装备</text>
                      </view>
                    </view>
                  </scroll-view>
                </view>
              </view>
            </view>
          </view>

          <view class="energy-box">
            <view class="energy-box__meta">
              <text>当前蓄能</text>
              <text class="energy-box__value">{{ selfEnergyLabel }}</text>
            </view>
            <view class="energy-box__cells">
              <view
                v-for="(slot, index) in selfEnergySlots"
                :key="`self-energy-${index}`"
                class="energy-box__cell"
                :class="{ 'energy-box__cell--active energy-box__cell--warm': slot }"
              />
            </view>
          </view>

          <!--
          <scroll-view scroll-x class="equip-strip" show-scrollbar="false">
            <view class="equip-strip__track">
              <EquipmentSlot
                v-for="equip in selfPlayer.equipments"
                :key="equip.id"
                :name="equip.name"
                :phase="equip.phase"
                :theme="equip.theme"
                minimal
              />
              <view v-if="!selfPlayer.equipments.length" class="equip-strip__empty">
                <text>暂无装备</text>
              </view>
            </view>
          </scroll-view>
          -->
        </view>

        <view class="hand-box hand-box--floating" :style="handDockStyle" @tap.stop="handleHandAreaTap">
          <view class="linear-hand">
            <view
              v-for="card in linearHand"
              :key="card.id"
              class="linear-hand__card"
              :style="card.style"
              @tap.stop="handleCardTap(card.id)"
              @mouseenter="hoverState.activeCardId = card.id"
              @mouseleave="hoverState.activeCardId = ''"
              @touchstart="handleCardTouchStart(card.id, $event)"
              @touchmove="handleCardTouchMove(card.id, $event)"
              @touchend="handleCardTouchEnd(card.id)"
              @touchcancel="handleCardTouchCancel(card.id)"
              :data-card-id="card.id"
            >
              <GameCard
                :name="card.name"
                :kind="card.kind"
                :subtitle="card.subtitle"
                :cost-label="card.costLabel"
                :attack-label="card.attackLabel"
                :defense-label="card.defenseLabel"
                :keywords="card.keywords"
                :special-text="card.specialText"
                :theme="card.theme"
                :disabled="card.isLocked"
                :disabled-label="card.disabledLabel"
                :crushed="card.isCrushed"
              />
            </view>
            <view v-if="!linearHand.length" class="linear-hand__empty">
              <text>{{ socketStatus === "open" ? "等待服务端下发手牌..." : "服务器连接中，请稍候..." }}</text>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { onLoad, onUnload } from "@dcloudio/uni-app";
import BattlefieldArena from "@/components/battle/BattlefieldArena.vue";
import EquipmentSlot from "@/components/battle/EquipmentSlot.vue";
import GameCard from "@/components/battle/GameCard.vue";
import type { BattleCardModel } from "@/types/match";
import { useBattleStore } from "@/stores/battle";

const gameStarted = ref(false);
const SOCKET_URL = "wss://efxlzhrnfjci.sealoshzh.site/ws/battle";
const PROFILE_STORAGE_KEY = "xu-player-profile";

const battleStore = useBattleStore();
const {
  countdownDeadline,
  myReady,
  enemyReady,
  gameState,
  opponentPlayer,
  phaseLabel,
  resolution,
  revealCards,
  selfPlayer,
  socketStatus,
} = storeToRefs(battleStore);

const profile = reactive({ nickname: "", avatarUrl: "" });
const equipmentPopoverSide = ref<"" | "enemy" | "self">("");
const selectedCardId = ref("");
const equipmentGainToast = reactive({
  visible: false,
  side: "" as "" | "self" | "enemy",
});
const dragState = reactive({
  activeCardId: "",
  startX: 0,
  startY: 0,
  offsetX: 0,
  offsetY: 0,
  moved: false,
  suppressTap: false,
});
const hoverState = reactive({ activeCardId: "" });
const viewport = reactive({
  windowWidth: 375,
  windowHeight: 667,
  safeLeft: 0,
  safeRight: 0,
  safeTop: 0,
  safeBottom: 0,
});

let touchStartX = 0;
let touchStartIndex = -1;
const nowTick = ref(Date.now());
let timerHandle: ReturnType<typeof setInterval> | null = null;
let viewportSyncTimers: ReturnType<typeof setTimeout>[] = [];
let arenaMeasureTimers: ReturnType<typeof setTimeout>[] = [];
let roundAnnouncementTimers: ReturnType<typeof setTimeout>[] = [];
const lastRoundAnnouncementKey = ref("");
const arenaBounds = reactive({
  upperPx: 0,
  lowerPx: 0,
  ready: false,
});

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function getLandscapeWidth() {
  return Math.max(viewport.windowWidth, viewport.windowHeight, 1);
}

function getLandscapeHeight() {
  return Math.min(viewport.windowWidth, viewport.windowHeight, 1);
}

function rpxToPx(value: number) {
  const baseWidth = getLandscapeWidth();
  return baseWidth > 0 ? (value * baseWidth) / 750 : value;
}

const handThemeOrder: Record<string, number> = {
  base: 0,
  pegasus: 10,
  frost: 20,
  dragon: 30,
  immune: 40,
  justice: 50,
  guardian: 60,
  wolf: 70,
  gold: 80,
  paper: 81,
  azure: 82,
  storm: 83,
  crimson: 84,
  super: 90,
};

function startTicker() {
  stopTicker();
  timerHandle = setInterval(() => {
    nowTick.value = Date.now();
  }, 200);
}

function stopTicker() {
  if (timerHandle) {
    clearInterval(timerHandle);
    timerHandle = null;
  }
}

function clearViewportSyncTimers() {
  viewportSyncTimers.forEach((timer) => clearTimeout(timer));
  viewportSyncTimers = [];
}

function clearArenaMeasureTimers() {
  arenaMeasureTimers.forEach((timer) => clearTimeout(timer));
  arenaMeasureTimers = [];
}

function clearRoundAnnouncementTimers() {
  roundAnnouncementTimers.forEach((timer) => clearTimeout(timer));
  roundAnnouncementTimers = [];
}

function syncViewport(info?: Partial<UniNamespace.GetSystemInfoResult>) {
  const systemInfo = uni.getSystemInfoSync();
  const nextWidth = Number(info?.windowWidth ?? systemInfo.windowWidth) || viewport.windowWidth;
  const nextHeight = Number(info?.windowHeight ?? systemInfo.windowHeight) || viewport.windowHeight;
  const screenWidth = Number(systemInfo.screenWidth) || nextWidth;
  const screenHeight = Number(systemInfo.screenHeight) || nextHeight;
  const safeArea = systemInfo.safeArea;

  let safeLeft = 0;
  let safeRight = 0;
  let safeTop = 0;
  let safeBottom = 0;

  if (safeArea) {
    const safeAreaLeft = Number(safeArea.left) || 0;
    const safeAreaTop = Number(safeArea.top) || 0;
    const safeAreaRight = Number(safeArea.right) || screenWidth;
    const safeAreaBottom = Number(safeArea.bottom) || screenHeight;

    safeLeft = clamp(safeAreaLeft, 0, nextWidth / 2);
    safeRight = clamp(screenWidth - safeAreaRight, 0, nextWidth / 2);
    safeTop = clamp(safeAreaTop, 0, nextHeight / 2);
    safeBottom = clamp(screenHeight - safeAreaBottom, 0, nextHeight / 2);
  }

  viewport.windowWidth = nextWidth;
  viewport.windowHeight = nextHeight;
  viewport.safeLeft = safeLeft;
  viewport.safeRight = safeRight;
  viewport.safeTop = safeTop;
  viewport.safeBottom = safeBottom;
}

function scheduleViewportSync() {
  clearViewportSyncTimers();
  [0, 80, 220].forEach((delay) => {
    viewportSyncTimers.push(
      setTimeout(() => {
        syncViewport();
      }, delay),
    );
  });
}

function measureArenaBounds() {
  if (!layoutMetrics.value.isLandscape || !gameStarted.value) {
    arenaBounds.ready = false;
    return;
  }

  nextTick(() => {
    const query = uni.createSelectorQuery();
    query.select(".enemy-hand-fan").boundingClientRect();
    query.select(".battle-overlay-controls").boundingClientRect();
    query.select(".player-hud--enemy-corner").boundingClientRect();
    query.select(".hand-box--floating").boundingClientRect();
    query.exec((result) => {
      const rects = Array.isArray(result) ? result : [];
      const enemyHandRect = (rects[0] as UniApp.NodeInfo | undefined) ?? null;
      const overlayRect = (rects[1] as UniApp.NodeInfo | undefined) ?? null;
      const enemyHudRect = (rects[2] as UniApp.NodeInfo | undefined) ?? null;
      const handRect = (rects[3] as UniApp.NodeInfo | undefined) ?? null;

      const upperCandidates = [enemyHandRect?.bottom, overlayRect?.bottom, enemyHudRect?.bottom]
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0);
      const lowerCandidates = [handRect?.top]
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0);

      if (!upperCandidates.length || !lowerCandidates.length) {
        arenaBounds.ready = false;
        return;
      }

      arenaBounds.upperPx = Math.max(...upperCandidates);
      arenaBounds.lowerPx = Math.max(...lowerCandidates);
      arenaBounds.ready = arenaBounds.lowerPx > arenaBounds.upperPx;
    });
  });
}

function scheduleArenaMeasure() {
  clearArenaMeasureTimers();
  [0, 80, 220, 420].forEach((delay) => {
    arenaMeasureTimers.push(
      setTimeout(() => {
        measureArenaBounds();
      }, delay),
    );
  });
}

function loadProfile() {
  const saved = uni.getStorageSync(PROFILE_STORAGE_KEY);
  if (saved && typeof saved === "object") {
    profile.nickname = typeof saved.nickname === "string" ? saved.nickname : "";
    profile.avatarUrl = typeof saved.avatarUrl === "string" ? saved.avatarUrl : "";
  }
}

onLoad(() => {
  loadProfile();
  scheduleViewportSync();
  scheduleArenaMeasure();
  uni.onWindowResize?.((event) => {
    syncViewport(event.size);
    scheduleViewportSync();
    scheduleArenaMeasure();
  });
});

onUnload(() => {
  stopTicker();
  clearViewportSyncTimers();
  clearArenaMeasureTimers();
  clearRoundAnnouncementTimers();
  battleStore.disconnect();
});

onBeforeUnmount(() => {
  stopTicker();
  clearViewportSyncTimers();
  clearArenaMeasureTimers();
  clearRoundAnnouncementTimers();
});

const displayName = computed(() => profile.nickname.trim() || "我方");
const avatarFallback = computed(() => displayName.value.slice(0, 1).toUpperCase());
const socketStatusLabel = computed(() => {
  if (socketStatus.value === "open") return "联机中";
  if (socketStatus.value === "connecting" || socketStatus.value === "reconnecting") return "连接中";
  if (socketStatus.value === "error") return "连接异常";
  return "未连接";
});
const connectionActionLabel = computed(() => {
  if (socketStatus.value === "connecting" || socketStatus.value === "reconnecting") return "连接中";
  return socketStatus.value === "open" ? "重连" : "开局";
});
const selfScore = computed(() => Number(gameState.value.scores?.my ?? gameState.value.my_state.score ?? 0));
const enemyScore = computed(() => Number(gameState.value.scores?.enemy ?? gameState.value.enemy_state.score ?? 0));

function formatDisplayNumber(value: unknown) {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return "0";
  if (Math.abs(parsed - Math.round(parsed)) < 0.001) {
    return String(Math.round(parsed));
  }
  return parsed.toFixed(1);
}

const opponentEnergyLabel = computed(() => formatDisplayNumber(opponentPlayer.value.energy));
const selfEnergyLabel = computed(() => formatDisplayNumber(selfPlayer.value.energy));

const opponentStatusLabel = computed(() => {
  if (opponentPlayer.value.isDead) return "本小局已阵亡";
  if (revealCards.value && resolution.value?.enemy_card_status === "crushed") return "本回合被粉碎";
  if (enemyReady.value && !revealCards.value) return "已出牌，等待翻牌";
  return "等待出牌";
});

const selfStatusLabel = computed(() => {
  if (selfPlayer.value.isDead) return "本小局已阵亡";
  if (revealCards.value && resolution.value?.my_card_status === "crushed") return "本回合被粉碎";
  if (myReady.value && !revealCards.value) return "已出牌，等待翻牌";
  return "等待出牌";
});

const revealSummary = computed(() => {
  if (!revealCards.value || !resolution.value?.winner) return phaseLabel.value;
  if (resolution.value.winner === "self") return "本回合我方占优";
  if (resolution.value.winner === "enemy") return "本回合对手占优";
  return "本回合平局";
});

const battleLog = computed(() => {
  if (socketStatus.value !== "open") return "正在连接服务器，请稍候...";
  const log = resolution.value?.logs?.[0];
  if (log) return log;
  if (myReady.value && enemyReady.value && !revealCards.value) return "双方已出牌，正在同步翻牌。";
  if (myReady.value && !enemyReady.value) return "我方已出牌，等待对手响应。";
  if (!myReady.value && enemyReady.value) return "对手已锁牌，请尽快从下方手牌区完成选择。";
  return "请在 10 秒内完成出牌，未操作会自动打出“蓄”。";
});

const remainingSeconds = computed(() => {
  if (!countdownDeadline.value) return 0;
  return Math.ceil(Math.max(0, countdownDeadline.value - nowTick.value) / 1000);
});

function buildRoundAnnouncementText(
  gameIndex: number,
  winner: "self" | "enemy" | "draw" | null | undefined,
  equipmentName?: string | null,
) {
  const gameLabel = `第 ${gameIndex} 小局`;
  if (winner === "draw") {
    return {
      text: `${gameLabel} 平局`,
      side: "" as const,
    };
  }

  if (winner === "self" || winner === "enemy") {
    const sideLabel = winner === "self" ? "我方" : "对手";
    const suffix = equipmentName ? `获得 ${equipmentName}` : "获胜";
    return {
      text: `${gameLabel} ${sideLabel}${suffix}`,
      side: winner,
    };
  }

  return {
    text: "",
    side: "" as const,
  };
}

function showRoundAnnouncement(round: number, winner: "self" | "enemy" | "draw" | null | undefined, equipmentName?: string | null) {
  const payload = buildRoundAnnouncementText(round, winner, equipmentName);
  if (!payload.text) {
    return;
  }

  clearRoundAnnouncementTimers();
  uni.showToast({
    title: payload.text,
    icon: "none",
    duration: 1500,
  });

  if (payload.side === "self" || payload.side === "enemy") {
    if (equipmentName) {
      equipmentGainToast.visible = true;
      equipmentGainToast.side = payload.side;
    } else {
      equipmentGainToast.visible = false;
      equipmentGainToast.side = "";
    }
  } else {
    equipmentGainToast.visible = false;
    equipmentGainToast.side = "";
  }

  roundAnnouncementTimers.push(
    setTimeout(() => {
      equipmentGainToast.visible = false;
      equipmentGainToast.side = "";
    }, 950),
  );
}
const opponentEnergySlots = computed(() =>
  Array.from({ length: 8 }, (_, index) => index < Math.max(0, Math.floor(Number(opponentPlayer.value.energy) || 0))),
);
const selfEnergySlots = computed(() =>
  Array.from({ length: 8 }, (_, index) => index < Math.max(0, Math.floor(Number(selfPlayer.value.energy) || 0))),
);

const enemyHandCount = computed(() => {
  const state = gameState.value as unknown as Record<string, unknown>;
  const topLevelCount = Number(state.enemy_hand_count);
  if (!Number.isNaN(topLevelCount) && topLevelCount >= 0) return Math.floor(topLevelCount);
  const enemyState = state.enemy_state as Record<string, unknown> | undefined;
  const nestedCount = Number(enemyState?.hand_count);
  if (!Number.isNaN(nestedCount) && nestedCount >= 0) return Math.floor(nestedCount);
  return Math.max(0, selfPlayer.value.hand.length);
});

const enemyBackCards = computed(() => Array.from({ length: Math.max(0, Math.min(12, enemyHandCount.value)) }, (_, index) => index));

const layoutMetrics = computed(() => {
  const widthPx = getLandscapeWidth();
  const heightPx = getLandscapeHeight();
  const safeWidthPx = Math.max(220, widthPx);
  const safeHeightPx = Math.max(220, heightPx);
  const shortSide = Math.min(safeWidthPx, safeHeightPx);
  const isLandscape = true;
  const compact = shortSide <= 390 || safeHeightPx <= 760;
  const narrow = shortSide <= 360;
  const fitScale = isLandscape
    ? clamp(Math.min(safeWidthPx / 844, safeHeightPx / 390), 0.84, 1)
    : clamp(Math.min(safeWidthPx / 390, safeHeightPx / 844), 0.88, 1);
  const hudWidthPx = isLandscape ? clamp(safeWidthPx * 0.19 * fitScale, 136, 220) : 188;
  const hudInsetXPx = isLandscape ? clamp(safeWidthPx * 0.012, 8, 18) : 6;
  const handLaneGapPx = isLandscape ? clamp(safeWidthPx * 0.016, 8, 22) : 0;
  const handLaneLeftPx = isLandscape ? hudInsetXPx + hudWidthPx + handLaneGapPx : 0;
  const handLaneRightPx = isLandscape
    ? widthPx - hudInsetXPx - hudWidthPx - handLaneGapPx
    : widthPx;
  const handLaneWidthPx = Math.max(220, handLaneRightPx - handLaneLeftPx);
  const pxToRpx = widthPx > 0 ? 750 / widthPx : 1;
  const fieldMaxScale = isLandscape ? (safeHeightPx <= 360 ? 0.26 : safeHeightPx <= 390 ? 0.28 : 0.3) : 0.94;
  const fieldScale = isLandscape
    ? clamp(Math.min(handLaneWidthPx / 560, safeHeightPx / 780), 0.22, fieldMaxScale)
    : clamp(Math.min(safeWidthPx / 390, safeHeightPx / 844) * 1.18, 0.64, fieldMaxScale);
  const deckWidth = isLandscape
    ? Math.max(240, handLaneWidthPx * pxToRpx)
    : 750 - (narrow ? 28 : compact ? 32 : 40) * 2;
  return {
    isLandscape,
    compact,
    narrow,
    fitScale,
    safeWidthPx,
    safeHeightPx,
    fieldScale,
    railScale: isLandscape ? clamp(fieldScale * 0.48, 0.1, 0.16) : clamp(fieldScale * 0.36, 0.2, 0.34),
    enemyRailWidth: isLandscape ? clamp(handLaneWidthPx * pxToRpx * 0.56, 170, 260) : compact ? 520 : 620,
    deckWidth,
    handLaneLeftPx,
    handLaneWidthPx,
    hoverLift: isLandscape ? clamp((safeHeightPx / 390) * 42, 28, 46) : heightPx <= 700 ? 70 : compact ? 84 : 98,
  };
});

const handMetrics = computed(() => {
  const count = Math.max(1, selfPlayer.value.hand.length);
  let scale = layoutMetrics.value.isLandscape
    ? clamp(
        (layoutMetrics.value.safeHeightPx / 390) * (layoutMetrics.value.safeHeightPx <= 360 ? 0.56 : 0.62),
        layoutMetrics.value.safeHeightPx <= 360 ? 0.46 : 0.5,
        layoutMetrics.value.safeHeightPx <= 360 ? 0.58 : 0.68,
      )
    : clamp(layoutMetrics.value.compact ? 0.8 : 0.88, 0.58, 0.92);
  let cardWidth = 196 * scale;
  let spacing = count > 1 ? (layoutMetrics.value.deckWidth - cardWidth) / (count - 1) : 0;
  if (count > 1) {
    spacing = layoutMetrics.value.isLandscape
      ? clamp(
          spacing,
          cardWidth * (count >= 10 ? 0.04 : count >= 8 ? 0.06 : 0.1),
          cardWidth * (count >= 10 ? 0.18 : count >= 8 ? 0.24 : 0.42),
        )
      : clamp(spacing, layoutMetrics.value.narrow ? 38 : 46, layoutMetrics.value.compact ? 88 : 104);
    const totalWidth = cardWidth + (count - 1) * spacing;
    if (totalWidth > layoutMetrics.value.deckWidth) {
      const shrink = layoutMetrics.value.deckWidth / totalWidth;
      const minScale = layoutMetrics.value.isLandscape
        ? layoutMetrics.value.safeHeightPx <= 360
          ? 0.44
          : 0.48
        : 0.58;
      scale = Math.max(minScale, scale * shrink);
      cardWidth = 196 * scale;
      spacing = clamp(
        (layoutMetrics.value.deckWidth - cardWidth) / (count - 1),
        cardWidth * (count >= 10 ? 0.03 : count >= 8 ? 0.05 : 0.08),
        cardWidth * (count >= 10 ? 0.16 : count >= 8 ? 0.22 : 0.38),
      );
    }
  }
  const cardHeight = 276 * scale;
  const handHeight = layoutMetrics.value.isLandscape
    ? clamp(cardHeight + Math.max(8, cardHeight * 0.08), 126, 190)
    : layoutMetrics.value.safeHeightPx <= 700
      ? 194
      : layoutMetrics.value.compact
        ? 214
        : 238;
  return {
    scale: Number(scale.toFixed(3)),
    cardWidth,
    cardHeight,
    handHeight,
    spacing,
    hoverLift: layoutMetrics.value.isLandscape ? clamp(cardHeight * 0.18, 18, 34) : layoutMetrics.value.hoverLift,
    spreadPush: layoutMetrics.value.isLandscape
      ? clamp(cardWidth * (count > 10 ? 0.06 : 0.12), 6, count > 10 ? 10 : 16)
      : layoutMetrics.value.compact ? 28 : 42,
    dragFactor: layoutMetrics.value.isLandscape ? 1.05 : layoutMetrics.value.compact ? 1.22 : 1.4,
    playThreshold: layoutMetrics.value.isLandscape ? -24 : layoutMetrics.value.compact ? -42 : -56,
  };
});

const hudStyleVars = computed(() => ({
  "--field-w": `${(196 * layoutMetrics.value.fieldScale).toFixed(1)}rpx`,
  "--field-h": `${(276 * layoutMetrics.value.fieldScale).toFixed(1)}rpx`,
  "--hand-h": `${handMetrics.value.handHeight.toFixed(1)}rpx`,
  "--enemy-rail-width": `${layoutMetrics.value.enemyRailWidth}rpx`,
}));

const handDockStyle = computed(() => {
  if (!layoutMetrics.value.isLandscape) {
    return {};
  }

  return {
    position: "fixed",
    width: `${layoutMetrics.value.handLaneWidthPx}px`,
    minWidth: "0px",
    bottom: "0px",
    left: `${layoutMetrics.value.handLaneLeftPx}px`,
    transform: "none",
    padding: "0px",
    zIndex: "20",
  };
});

const freeLayoutStyle = computed(() => {
  if (!layoutMetrics.value.isLandscape) {
    return {};
  }

  return {
    height: "100%",
    paddingBottom: "0px",
  };
});

const overlayControlsStyle = computed(() => {
  if (!layoutMetrics.value.isLandscape) {
    return {};
  }

  const chromeScale = clamp(layoutMetrics.value.fitScale + 0.02, 0.88, 1);
  const topOffset = Math.max(6, Math.round(layoutMetrics.value.safeHeightPx * 0.018));
  const rightOffset = Math.max(8, Math.round(layoutMetrics.value.safeWidthPx * 0.012));

  return {
    top: `calc(env(safe-area-inset-top) + ${topOffset}px)`,
    right: `calc(env(safe-area-inset-right) + ${rightOffset}px)`,
    transform: `scale(${chromeScale.toFixed(3)})`,
    transformOrigin: "top right",
  };
});

const enemyHandFanStyle = computed(() => {
  if (!layoutMetrics.value.isLandscape) {
    return {};
  }

  const fanScale = clamp(layoutMetrics.value.fitScale + 0.01, 0.9, 1);
  const topOffset = Math.max(2, Math.round(layoutMetrics.value.safeHeightPx * 0.004));
  const widthPx = clamp(layoutMetrics.value.handLaneWidthPx * 0.72, 220, 380);

  return {
    width: `${widthPx}px`,
    top: `calc(env(safe-area-inset-top) + ${topOffset}px)`,
    left: "50%",
    transform: `translateX(-50%) scale(${fanScale.toFixed(3)})`,
    transformOrigin: "top center",
  };
});

const battlefieldArenaStyle = computed(() => {
  if (!layoutMetrics.value.isLandscape) {
    return {};
  }

  const fanTopOffsetPx = Math.max(2, Math.round(layoutMetrics.value.safeHeightPx * 0.004));
  const estimatedEnemyHandBottomPx =
    fanTopOffsetPx +
    rpxToPx(54) +
    Math.max(rpxToPx(16), handMetrics.value.cardHeight * 0.14);
  const overlayTopPx = Math.max(6, Math.round(layoutMetrics.value.safeHeightPx * 0.018));
  const overlayScale = clamp(layoutMetrics.value.fitScale + 0.02, 0.88, 1);
  const estimatedOverlayBottomPx = overlayTopPx + rpxToPx(74) * overlayScale;
  const estimatedEnemyHudBottomPx = cornerHudMetrics.value.insetTop + cornerHudMetrics.value.heightPx;
  const estimatedUpperBattleBoundaryPx = Math.max(
    estimatedEnemyHandBottomPx,
    estimatedOverlayBottomPx,
    estimatedEnemyHudBottomPx,
  );
  const estimatedLowerBattleBoundaryPx = layoutMetrics.value.safeHeightPx - rpxToPx(handMetrics.value.handHeight);
  const upperBattleBoundaryPx = arenaBounds.ready ? arenaBounds.upperPx : estimatedUpperBattleBoundaryPx;
  const lowerBattleBoundaryPx = arenaBounds.ready ? arenaBounds.lowerPx : estimatedLowerBattleBoundaryPx;
  const arenaCenterYPx = upperBattleBoundaryPx + (lowerBattleBoundaryPx - upperBattleBoundaryPx) * 0.54;
  const arenaScale = clamp(
    layoutMetrics.value.fitScale * (layoutMetrics.value.safeHeightPx <= 360 ? 0.84 : 0.92),
    0.82,
    1.02,
  );

  return {
    left: "50%",
    top: `calc(env(safe-area-inset-top) + ${arenaCenterYPx}px)`,
    transform: `translate(-50%, -50%) scale(${arenaScale.toFixed(3)})`,
    transformOrigin: "center center",
  };
});

const cornerHudMetrics = computed(() => {
  const isLandscape = layoutMetrics.value.isLandscape;
  const widthPx = isLandscape
    ? clamp(layoutMetrics.value.safeWidthPx * 0.19 * layoutMetrics.value.fitScale, 136, 220)
    : 188;
  const heightPx = isLandscape
    ? clamp(layoutMetrics.value.safeHeightPx * 0.21, layoutMetrics.value.safeHeightPx <= 360 ? 76 : 82, 112)
    : 128;
  const insetX = isLandscape ? clamp(layoutMetrics.value.safeWidthPx * 0.012, 8, 18) : 6;
  const insetRight = isLandscape ? clamp(layoutMetrics.value.safeWidthPx * 0.012, 8, 18) : 6;
  const insetTop = isLandscape ? clamp(layoutMetrics.value.safeHeightPx * 0.02, 8, 14) : 6;
  const insetBottom = isLandscape ? clamp(layoutMetrics.value.safeHeightPx * 0.02, 8, 14) : 6;

  return {
    widthPx,
    heightPx,
    insetX,
    insetRight,
    insetTop,
    insetBottom,
  };
});

const enemyHudStyle = computed(() => ({
  width: `${cornerHudMetrics.value.widthPx}px`,
  minHeight: `${cornerHudMetrics.value.heightPx}px`,
  left: `calc(env(safe-area-inset-left) + ${cornerHudMetrics.value.insetX}px)`,
  top: `calc(env(safe-area-inset-top) + ${cornerHudMetrics.value.insetTop}px)`,
}));

const selfHudStyle = computed(() => ({
  width: `${cornerHudMetrics.value.widthPx}px`,
  minHeight: `${cornerHudMetrics.value.heightPx}px`,
  right: `calc(env(safe-area-inset-right) + ${Math.max(4, Math.round(cornerHudMetrics.value.insetRight * 0.7))}px)`,
  bottom: `calc(env(safe-area-inset-bottom) + ${Math.max(0, Math.round(cornerHudMetrics.value.insetBottom * 0.3) - 1)}px)`,
}));

function showEquipmentPopover(side: "enemy" | "self") {
  equipmentPopoverSide.value = side;
}

function hideEquipmentPopover(side: "enemy" | "self") {
  if (equipmentPopoverSide.value === side) {
    equipmentPopoverSide.value = "";
  }
}

function toggleEquipmentPopover(side: "enemy" | "self") {
  equipmentPopoverSide.value = equipmentPopoverSide.value === side ? "" : side;
}

function getEnemyBackCardStyle(index: number, total: number) {
  if (total <= 0) return "";
  const scale = layoutMetrics.value.isLandscape ? clamp(handMetrics.value.scale * 0.5, 0.1, 0.17) : 0.18;
  const areaWidthPx = clamp(viewport.windowWidth * 0.34, 260, 380);
  const pxToRpx = viewport.windowWidth > 0 ? 750 / viewport.windowWidth : 1;
  const areaWidthRpx = areaWidthPx * pxToRpx;
  const cardWidth = 196 * scale;
  const cardHeight = 276 * scale;
  const spread = total > 1 ? clamp((areaWidthRpx - cardWidth) / (total - 1), cardWidth * 0.22, cardWidth * 0.44) : 0;
  const centerIndex = (total - 1) / 2;
  const distance = Math.abs(index - centerIndex);
  const offsetX = -((total - 1) * spread) / 2 + index * spread;
  const offsetY = -(cardHeight * 0.42) + Math.max(0, centerIndex - distance) * 1.8;
  const rotate = (centerIndex - index) * 4.1;
  return `transform: translateX(${offsetX.toFixed(2)}rpx) translateY(${offsetY.toFixed(2)}rpx) rotate(${rotate.toFixed(2)}deg) scale(${scale.toFixed(3)}); z-index: ${index + 1};`;
}

const orderedHand = computed(() =>
  [...selfPlayer.value.hand].sort((left, right) => {
    const themeDelta = (handThemeOrder[left.theme] ?? 80) - (handThemeOrder[right.theme] ?? 80);
    if (themeDelta !== 0) return themeDelta;
    const costDelta = left.costValue - right.costValue;
    if (Math.abs(costDelta) > 0.001) return costDelta;
    return left.name.localeCompare(right.name, "zh-Hans-CN");
  }),
);

function buildLinearStyle(index: number, total: number, cardId: string, isLocked: boolean) {
  const { cardWidth, spacing, scale, hoverLift, spreadPush, dragFactor } = handMetrics.value;
  const totalGroupWidth = cardWidth + (total - 1) * spacing;
  const startX = -totalGroupWidth / 2 + cardWidth / 2;
  let offsetX = startX + index * spacing;
  let offsetY = 0;
  let cardScale = 1;
  let zIndex = index + 1;
  let rotate = 0;
  const isDragging = dragState.activeCardId === cardId;
  const activeCardId = selectedCardId.value || hoverState.activeCardId;
  const isSelected = selectedCardId.value === cardId && !isLocked;
  const isHovered =
    !selectedCardId.value && hoverState.activeCardId === cardId && !dragState.moved && !isLocked;
  if (isDragging && dragState.moved) {
    offsetX += dragState.offsetX * dragFactor;
    offsetY += dragState.offsetY * dragFactor;
    cardScale = 1.04;
    zIndex = 100;
  } else if (isSelected) {
    offsetY = -hoverLift;
    cardScale = layoutMetrics.value.isLandscape ? 1.08 : 1.12;
    zIndex = 120;
  } else if (isHovered) {
    offsetY = -hoverLift;
    cardScale = layoutMetrics.value.isLandscape ? 1.04 : layoutMetrics.value.compact ? 1.08 : 1.12;
    zIndex = 100;
  } else if (activeCardId && !dragState.moved && !isLocked) {
    const hoveredIndex = orderedHand.value.findIndex((card) => card.id === activeCardId);
    if (hoveredIndex !== -1) {
      const distance = Math.abs(index - hoveredIndex);
      if (index < hoveredIndex) offsetX -= Math.max(0, spreadPush - distance * 8);
      if (index > hoveredIndex) offsetX += Math.max(0, spreadPush - distance * 8);
      if (index < hoveredIndex) rotate = -Math.max(0, 4 - distance);
      if (index > hoveredIndex) rotate = Math.max(0, 4 - distance);
      if (distance === 1) offsetY = -10;
      if (distance === 2) offsetY = -4;
    }
  }
  return {
    transform: `translateX(${offsetX}rpx) translateY(${offsetY}rpx) scale(${(scale * cardScale).toFixed(3)}) rotate(${rotate}deg)`,
    zIndex: String(zIndex),
    transition: isDragging && dragState.moved ? "none" : "transform 0.3s cubic-bezier(0.2, 0.9, 0.2, 1), z-index 0s",
  };
}

function isCardLocked(card: BattleCardModel) {
  return socketStatus.value !== "open" || myReady.value || revealCards.value || selfPlayer.value.isDead || card.isCrushed;
}

function getDisabledLabel(card: BattleCardModel) {
  if (socketStatus.value !== "open") return "未连接";
  if (card.isCrushed) return "已粉碎";
  if (myReady.value && !revealCards.value) return "已出牌";
  if (revealCards.value) return "结算中";
  return "";
}

function handlePlayCard(cardId: string) {
  selectedCardId.value = "";
  hoverState.activeCardId = "";
  battleStore.playCard(cardId);
}

function handleGameStart() {
  gameStarted.value = true;
  scheduleViewportSync();
  scheduleArenaMeasure();
  nextTick(() => {
    battleStore.initializeSocket(SOCKET_URL);
    startTicker();
    setTimeout(() => battleStore.restartMatch(), 260);
  });
}

function handleGameExit() {
  uni.reLaunch({
    url: "/pages/index/index",
  });
}

function handleStartBattle() {
  scheduleViewportSync();
  scheduleArenaMeasure();
  battleStore.initializeSocket(SOCKET_URL);
  startTicker();
  setTimeout(() => battleStore.restartMatch(), 260);
}

function handleCardTap(cardId: string) {
  if (dragState.suppressTap) {
    dragState.suppressTap = false;
    return;
  }
  const card = orderedHand.value.find((item) => item.id === cardId);
  if (!card || isCardLocked(card)) return;
  if (selectedCardId.value === cardId) {
    selectedCardId.value = "";
    hoverState.activeCardId = "";
    return;
  }
  selectedCardId.value = cardId;
  hoverState.activeCardId = cardId;
}

function handleHandAreaTap() {
  if (!selectedCardId.value) return;
  selectedCardId.value = "";
  hoverState.activeCardId = "";
}

function handleOutsidePlayConfirm() {
  if (!selectedCardId.value) return;
  const card = orderedHand.value.find((item) => item.id === selectedCardId.value);
  if (!card || isCardLocked(card)) {
    selectedCardId.value = "";
    hoverState.activeCardId = "";
    return;
  }
  handlePlayCard(selectedCardId.value);
}

function handleCardTouchStart(cardId: string, event: any) {
  if (dragState.suppressTap) return;
  const card = orderedHand.value.find((item) => item.id === cardId);
  if (!card || isCardLocked(card)) return;
  const touch = event.touches?.[0];
  if (!touch) return;
  dragState.activeCardId = cardId;
  dragState.startX = touch.clientX;
  dragState.startY = touch.clientY;
  dragState.offsetX = 0;
  dragState.offsetY = 0;
  dragState.moved = false;
  touchStartX = touch.clientX;
  touchStartIndex = orderedHand.value.findIndex((item) => item.id === cardId);
}

function handleCardTouchMove(cardId: string, event: any) {
  if (dragState.activeCardId !== cardId) return;
  const touch = event.touches?.[0];
  if (!touch) return;
  const deltaX = touch.clientX - dragState.startX;
  const deltaY = touch.clientY - dragState.startY;
  if (!dragState.moved) {
    if (Math.abs(deltaY) > 8 || Math.abs(deltaX) > 8) {
      dragState.moved = true;
    }
  }
  if (dragState.moved) {
    dragState.offsetX = 0;
    dragState.offsetY = 0;
  }
}

function resetDragState() {
  dragState.activeCardId = "";
  dragState.startX = 0;
  dragState.startY = 0;
  dragState.offsetX = 0;
  dragState.offsetY = 0;
  dragState.moved = false;
}

function handleCardTouchEnd(cardId: string) {
  if (dragState.activeCardId !== cardId) {
    return;
  }
  dragState.suppressTap = dragState.moved;
  resetDragState();
  if (dragState.suppressTap) {
    setTimeout(() => {
      dragState.suppressTap = false;
    }, 320);
  }
}

function handleCardTouchCancel(cardId: string) {
  if (dragState.activeCardId !== cardId) return;
  dragState.suppressTap = dragState.moved;
  resetDragState();
  if (dragState.suppressTap) {
    setTimeout(() => {
      dragState.suppressTap = false;
    }, 320);
  }
}

const linearHand = computed(() =>
  orderedHand.value.map((card, index, array) => {
    const isLocked = isCardLocked(card);
    return {
      ...card,
      isLocked,
      disabledLabel: getDisabledLabel(card),
      style: buildLinearStyle(index, array.length, card.id, isLocked),
    };
  }),
);

watch(
  () => [
    gameStarted.value,
    selfPlayer.value.hand.length,
    enemyBackCards.value.length,
    myReady.value,
    enemyReady.value,
    revealCards.value,
    socketStatus.value,
    layoutMetrics.value.safeWidthPx,
    layoutMetrics.value.safeHeightPx,
    handMetrics.value.handHeight,
  ],
  () => {
    scheduleArenaMeasure();
  },
  { flush: "post" },
);

watch(
  () => [
    selectedCardId.value,
    myReady.value,
    revealCards.value,
    socketStatus.value,
    selfPlayer.value.isDead,
    orderedHand.value.map((card) => `${card.id}:${card.isCrushed}`).join("|"),
  ],
  () => {
    if (!selectedCardId.value) return;
    const selectedCard = orderedHand.value.find((card) => card.id === selectedCardId.value);
    if (!selectedCard || isCardLocked(selectedCard)) {
      selectedCardId.value = "";
      hoverState.activeCardId = "";
    }
  },
);

watch(
  () => ({
    reveal: revealCards.value,
    winner: resolution.value?.winner ?? null,
    equipment: resolution.value?.granted_equipment ?? null,
    myScore: selfScore.value,
    enemyScore: enemyScore.value,
  }),
  (payload) => {
    if (!payload.reveal || !payload.winner) {
      if (!payload.reveal) {
        lastRoundAnnouncementKey.value = "";
      }
      return;
    }

    const completedSmallGames = Math.max(0, payload.myScore + payload.enemyScore);
    const displayRound =
      payload.winner === "self" || payload.winner === "enemy"
        ? Math.max(1, completedSmallGames)
        : Math.max(1, completedSmallGames + 1);
    const announcementKey = `${displayRound}-${payload.winner}-${payload.equipment ?? ""}`;
    if (announcementKey === lastRoundAnnouncementKey.value) {
      return;
    }

    lastRoundAnnouncementKey.value = announcementKey;
    showRoundAnnouncement(displayRound, payload.winner, payload.equipment);
  },
  { flush: "post" },
);
</script>

<style scoped lang="scss">
.battle-page {
  position: relative;
  height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% 0%, rgba(244, 198, 97, 0.14), transparent 26%),
    radial-gradient(circle at 100% 14%, rgba(42, 111, 146, 0.18), transparent 24%),
    linear-gradient(180deg, #08131a 0%, #0d1e29 46%, #091119 100%);
}

.battle-page__grain {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%) 0 0 / 22rpx 22rpx,
    linear-gradient(225deg, rgba(255, 255, 255, 0.012) 25%, transparent 25%) 0 0 / 28rpx 28rpx;
  opacity: 0.45;
  pointer-events: none;
}

.battle-shell {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: calc(16rpx + env(safe-area-inset-top)) 16rpx calc(16rpx + env(safe-area-inset-bottom));
  gap: 14rpx;
  box-sizing: border-box;
}

.hud-panel {
  position: relative;
  overflow: hidden;
  border-radius: 28rpx;
  border: 1rpx solid rgba(226, 190, 126, 0.15);
  background:
    linear-gradient(180deg, rgba(18, 33, 45, 0.96), rgba(8, 16, 24, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.03), transparent);
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.06), 0 18rpx 38rpx rgba(0, 0, 0, 0.26);
}

.hud-panel::before {
  content: "";
  position: absolute;
  inset: 10rpx;
  border-radius: 20rpx;
  border: 1rpx solid rgba(226, 190, 126, 0.08);
  pointer-events: none;
}

.battle-header,
.player-hud,
.command-panel {
  padding: 18rpx 20rpx;
}

.battle-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 12rpx;
}

.battle-header__title {
  display: block;
  font-size: 48rpx;
  font-weight: 900;
  color: #fff4db;
}

.battle-header__sub {
  display: block;
  margin-top: 4rpx;
  font-size: 20rpx;
  color: #93a8b5;
}

.battle-header__score,
.battle-header__actions,
.player-hud__head,
.player-hud__identity,
.energy-box__meta,
.hand-box__head,
.stage-slot__head,
.enemy-rail__head,
.stage-core__flags,
.player-hud__badges {
  display: flex;
  align-items: center;
}

.battle-header__score {
  justify-content: center;
  gap: 12rpx;
  font-size: 26rpx;
  font-weight: 800;
  color: #fff0c6;
}

.battle-header__score-dot {
  color: rgba(255, 232, 186, 0.6);
}

.battle-header__actions {
  justify-content: flex-end;
  gap: 10rpx;
}

.battle-header__timer,
.battle-header__start,
.pill {
  border-radius: 999rpx;
}

.battle-header__timer {
  display: flex;
  flex-direction: column;
  padding: 10rpx 16rpx;
  border: 1rpx solid rgba(236, 197, 112, 0.2);
  background: rgba(13, 24, 33, 0.72);
}

.battle-header__timer-value {
  font-size: 28rpx;
  font-weight: 900;
  color: #ffde99;
}

.battle-header__timer-label {
  margin-top: 4rpx;
  font-size: 18rpx;
  color: #8ba0ac;
}

.battle-header__start,
.start-modal__btn {
  display: flex;
  align-items: center;
  justify-content: center;
}

.battle-header__start {
  min-width: 100rpx;
  height: 64rpx;
  padding: 0 18rpx;
  border: 1rpx solid rgba(236, 197, 112, 0.3);
  background: linear-gradient(180deg, rgba(146, 101, 40, 0.94), rgba(72, 45, 18, 0.98));
  color: #fff0cc;
  font-size: 22rpx;
  font-weight: 800;
}

.battle-layout {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 14rpx;
}

.battle-shell--arena {
  position: relative;
}

.battle-overlay-controls {
  position: absolute;
  top: calc(10rpx + env(safe-area-inset-top));
  right: 12rpx;
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 10rpx;
  padding: 10rpx 12rpx;
}

.battle-overlay-controls__score,
.battle-overlay-controls__tools {
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.battle-overlay-controls__score {
  font-size: 18rpx;
  font-weight: 800;
  color: #fff0c6;
}

.battle-overlay-controls__divider {
  color: rgba(255, 232, 186, 0.6);
}

.battle-overlay-controls__timer {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6rpx 10rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(236, 197, 112, 0.2);
  background: rgba(13, 24, 33, 0.72);
}

.battle-overlay-controls__timer-value {
  font-size: 18rpx;
  font-weight: 900;
  color: #ffde99;
}

.battle-overlay-controls__timer-label {
  margin-top: 2rpx;
  font-size: 11rpx;
  color: #8ba0ac;
}

.battle-overlay-controls__start {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 64rpx;
  height: 38rpx;
  padding: 0 10rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(236, 197, 112, 0.28);
  background: linear-gradient(180deg, rgba(146, 101, 40, 0.94), rgba(72, 45, 18, 0.98));
  color: #fff0cc;
  font-size: 14rpx;
  font-weight: 800;
}

.battle-layout--free {
  position: relative;
  display: block;
  min-height: 0;
  padding-bottom: calc(var(--hand-h) + 44rpx);
}

.player-hud--corner {
  position: fixed;
  z-index: 3;
  width: 206rpx;
  min-height: 220rpx;
  gap: 4rpx;
  padding: 6rpx 8rpx;
  overflow: visible;
}

.player-hud--corner::before,
.battle-overlay-controls::before {
  display: none;
}

.player-hud--enemy-corner {
  top: 8rpx;
  left: 8rpx;
}

.player-hud--self-corner {
  right: 8rpx;
  bottom: calc(env(safe-area-inset-bottom) + 8rpx);
}

.player-hud--corner .player-hud__avatar {
  width: 24rpx;
  height: 24rpx;
  min-width: 24rpx;
  min-height: 24rpx;
  border-radius: 7rpx;
  font-size: 10rpx;
  flex-shrink: 0;
}

.player-hud--corner .player-hud__label {
  display: none;
}

.player-hud--corner .player-hud__name {
  margin-top: 0;
  font-size: 11rpx;
  line-height: 1.15;
  white-space: nowrap;
}

.player-hud--corner .player-hud__status {
  display: none;
}

.player-hud--corner .player-hud__badges {
  gap: 4rpx;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-shrink: 0;
}

.player-hud--corner .energy-box {
  padding: 5rpx 6rpx;
  border-radius: 10rpx;
}

.player-hud--corner .energy-box__meta text:first-child {
  font-size: 8rpx;
  color: #9aafbb;
}

.player-hud--corner .energy-box__value {
  font-size: 12rpx;
}

.player-hud--corner .energy-box__cells {
  gap: 2rpx;
  margin-top: 4rpx;
}

.player-hud--corner .energy-box__cell {
  height: 4rpx;
}

.player-hud--corner .equip-strip :deep(.equipment-slot--minimal) {
  width: 50rpx;
  min-height: 30rpx;
  padding: 3rpx 4rpx;
  border-radius: 8rpx;
}

.player-hud--corner .equip-strip :deep(.equipment-slot--minimal .equipment-slot__name) {
  margin-top: 6rpx;
  font-size: 8rpx;
}

.player-hud--corner .equip-strip :deep(.equipment-slot--minimal .equipment-slot__phase) {
  top: 2rpx;
  right: 2rpx;
  min-width: 12rpx;
  padding: 0 2rpx;
  font-size: 7rpx;
}

.player-hud--corner .player-hud__head {
  align-items: center;
  justify-content: space-between;
}

.player-hud--corner .player-hud__identity {
  align-items: center;
  gap: 7rpx;
  padding-left: 6rpx;
  flex: 1;
}

.player-hud--corner .player-hud__badges {
  justify-content: flex-end;
}

.player-hud__equip-anchor {
  position: relative;
}

.equip-gain-toast {
  position: absolute;
  right: -4rpx;
  top: -18rpx;
  z-index: 3;
  min-width: 34rpx;
  height: 26rpx;
  padding: 0 8rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(245, 214, 138, 0.28);
  background: linear-gradient(180deg, rgba(159, 113, 42, 0.96), rgba(88, 55, 16, 0.98));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff2cf;
  font-size: 16rpx;
  font-weight: 900;
  box-shadow: 0 8rpx 18rpx rgba(87, 52, 15, 0.26);
  animation: equip-gain-pop 0.9s ease forwards;
  pointer-events: none;
}

.player-hud--corner .pill {
  padding: 3rpx 7rpx;
  font-size: 8rpx;
}

.equipment-popover {
  position: absolute;
  z-index: 60;
  width: 146rpx;
  padding: 5rpx 5rpx 6rpx;
  border-radius: 10rpx;
  border: 1rpx solid rgba(226, 190, 126, 0.18);
  background:
    linear-gradient(180deg, rgba(18, 33, 45, 0.98), rgba(8, 16, 24, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.03), transparent);
  box-shadow: 0 10rpx 24rpx rgba(0, 0, 0, 0.26);
}

.equipment-popover--enemy {
  top: -2rpx;
  left: calc(100% + 6rpx);
}

.equipment-popover--self {
  right: 0;
  bottom: calc(100% + 6rpx);
}

.equipment-popover__title {
  display: block;
  font-size: 6rpx;
  color: #d9e7ef;
}

.equipment-popover__scroll {
  height: 108rpx;
  margin-top: 3rpx;
}

.equipment-popover__list {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3rpx;
  justify-items: center;
}

.equipment-popover__list :deep(.equipment-slot--minimal) {
  width: 32rpx;
  min-width: 32rpx;
  height: 32rpx;
  min-height: 32rpx;
  padding: 3rpx;
  border-radius: 8rpx;
}

.equipment-popover__list :deep(.equipment-slot--minimal::before) {
  inset: 2rpx;
  border-radius: 6rpx;
}

.equipment-popover__list :deep(.equipment-slot--minimal .equipment-slot__name) {
  right: 3rpx;
  bottom: 3rpx;
  left: 3rpx;
  margin-top: 0;
  font-size: 5rpx;
  line-height: 1.05;
}

.equipment-popover__list :deep(.equipment-slot--minimal .equipment-slot__phase) {
  font-size: 9rpx;
}

.equipment-popover__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  grid-column: 1 / -1;
  min-height: 26rpx;
  border-radius: 6rpx;
  border: 1rpx dashed rgba(226, 190, 126, 0.14);
  color: #93a5b2;
  font-size: 6rpx;
}

.hand-box--floating {
  position: absolute;
  left: 50%;
  z-index: 4;
  width: min(520rpx, calc(100% - 260rpx));
  min-width: 360rpx;
  bottom: calc(env(safe-area-inset-bottom) + 8rpx);
  transform: translateX(-50%);
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
}

.hand-box--floating::before {
  display: none;
}

.player-hud,
.command-panel {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.player-hud--dead {
  animation: player-dead-flash 0.48s ease-in-out 3;
}

.player-hud__head,
.energy-box,
.equip-strip,
.hand-box,
.enemy-rail,
.stage-stack {
  position: relative;
  z-index: 1;
}

.player-hud__head,
.hand-box__head,
.stage-slot__head,
.enemy-rail__head {
  justify-content: space-between;
  gap: 10rpx;
}

.player-hud__identity {
  gap: 14rpx;
  min-width: 0;
}

.player-hud__avatar {
  overflow: hidden;
  width: 78rpx;
  height: 78rpx;
  border-radius: 22rpx;
  border: 2rpx solid rgba(233, 198, 129, 0.28);
  background: linear-gradient(180deg, rgba(23, 51, 73, 0.92), rgba(10, 19, 29, 0.98));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff3d9;
  font-size: 28rpx;
  font-weight: 800;
}

.player-hud__avatar--enemy {
  background: linear-gradient(180deg, rgba(90, 61, 27, 0.94), rgba(30, 21, 12, 0.98));
}

.player-hud__avatar-image {
  width: 100%;
  height: 100%;
}

.player-hud__label,
.energy-box__meta text:first-child,
.hand-box__sub {
  color: #8ea2af;
}

.player-hud__label {
  display: block;
  font-size: 18rpx;
  letter-spacing: 2rpx;
}

.player-hud__name {
  display: block;
  margin-top: 4rpx;
  font-size: 32rpx;
  font-weight: 900;
  color: #f8f0de;
}

.player-hud__status {
  display: block;
  margin-top: 6rpx;
  font-size: 19rpx;
  color: #9eb0ba;
}

.player-hud__badges,
.stage-core__flags {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8rpx;
}

.pill {
  padding: 8rpx 14rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.05);
  color: #c4d2dc;
  font-size: 18rpx;
}

.pill--warm {
  border-color: rgba(236, 197, 112, 0.2);
  background: rgba(92, 61, 24, 0.24);
  color: #ffdca2;
}

.pill--active {
  box-shadow: 0 0 18rpx rgba(236, 197, 112, 0.14);
}

.energy-box {
  padding: 14rpx 16rpx;
  border-radius: 22rpx;
  border: 1rpx solid rgba(230, 193, 124, 0.1);
  background: linear-gradient(180deg, rgba(10, 22, 31, 0.92), rgba(14, 26, 37, 0.96));
}

.energy-box__meta {
  justify-content: space-between;
}

.energy-box__value {
  font-size: 36rpx;
  font-weight: 900;
  color: #f0c97b;
}

.energy-box__cells {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 6rpx;
  margin-top: 12rpx;
}

.energy-box__cell {
  height: 16rpx;
  border-radius: 999rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  background: linear-gradient(180deg, rgba(35, 48, 58, 0.84), rgba(17, 27, 36, 0.92));
}

.energy-box__cell--active {
  border-color: rgba(244, 223, 165, 0.36);
  background:
    radial-gradient(circle at 50% 40%, rgba(255, 243, 201, 0.95), rgba(240, 196, 94, 0.86) 56%, rgba(182, 116, 38, 0.92) 100%);
}

.energy-box__cell--warm {
  background:
    radial-gradient(circle at 50% 40%, rgba(255, 240, 191, 0.98), rgba(236, 181, 78, 0.88) 56%, rgba(156, 89, 27, 0.92) 100%);
}

.equip-strip__track {
  display: inline-flex;
  gap: 12rpx;
  min-width: 100%;
}

.equip-strip :deep(.equipment-slot--minimal) {
  width: 156rpx;
  min-height: 94rpx;
  border-radius: 18rpx;
  flex-shrink: 0;
}

.equip-strip :deep(.equipment-slot--minimal .equipment-slot__name) {
  font-size: 23rpx;
}

.equip-strip__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 92rpx;
  border-radius: 18rpx;
  border: 1rpx dashed rgba(226, 190, 126, 0.16);
  color: #92a3af;
  font-size: 20rpx;
}

.battle-stage {
  position: relative;
  padding: 116rpx 18rpx 22rpx;
}

.enemy-hand-fan {
  position: fixed;
  z-index: 2;
  pointer-events: none;
  overflow: visible;
  height: 88rpx;
  top: env(safe-area-inset-top);
  left: 50%;
  transform: translateX(-50%);
}

.enemy-hand-fan__head {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  position: absolute;
  left: 50%;
  top: 0;
  transform: translateX(-50%);
  padding: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  color: #e8f0f6;
  white-space: nowrap;
  z-index: 3;
}

.enemy-hand-fan__label {
  font-size: 14rpx;
  font-weight: 800;
  letter-spacing: 1rpx;
}

.enemy-hand-fan__status {
  font-size: 9rpx;
  color: rgba(159, 176, 188, 0.9);
}

.enemy-hand-fan__status--ready {
  color: #f3d18f;
}

.enemy-hand-fan__deck {
  position: absolute;
  left: 50%;
  top: 8rpx;
  width: 100%;
  height: 80rpx;
  margin-top: 0;
  transform: translateX(-50%);
}

.enemy-hand-fan__card {
  position: absolute;
  left: 50%;
  top: 0;
  margin-left: -98rpx;
  transform-origin: center 12%;
}

.enemy-hand-fan__back {
  position: relative;
  width: 196rpx;
  height: 276rpx;
  border-radius: 22rpx;
  border: 3rpx solid rgba(215, 183, 118, 0.5);
  background:
    radial-gradient(circle at 50% 18%, rgba(255, 244, 211, 0.12), transparent 30%),
    linear-gradient(160deg, rgba(8, 32, 54, 0.98), rgba(16, 56, 84, 0.96) 54%, rgba(34, 16, 9, 0.98));
  box-shadow:
    0 8rpx 18rpx rgba(0, 0, 0, 0.24),
    inset 0 2rpx 0 rgba(255, 255, 255, 0.1);
}

.enemy-hand-fan__back-frame {
  position: absolute;
  inset: 10rpx;
  border-radius: 18rpx;
  border: 2rpx solid rgba(214, 181, 112, 0.22);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.06), transparent 18%),
    linear-gradient(180deg, rgba(9, 25, 37, 0.88), rgba(7, 17, 24, 0.94));
}

.enemy-hand-fan__back-core {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 66rpx;
  height: 66rpx;
  border-radius: 50%;
  border: 2rpx solid rgba(236, 203, 137, 0.28);
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 36, 52, 0.76);
}

.enemy-hand-fan__back-glyph {
  font-size: 26rpx;
  font-weight: 900;
  color: rgba(255, 239, 196, 0.9);
}

.battlefield-arena--floating {
  position: fixed;
  z-index: 2;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
}

.battle-stage--floating {
  position: fixed;
  z-index: 2;
  overflow: hidden;
}

.enemy-rail {
  position: absolute;
  top: 16rpx;
  left: 50%;
  width: min(var(--enemy-rail-width), calc(100% - 36rpx));
  transform: translateX(-50%);
  pointer-events: none;
}

.enemy-rail__head {
  margin-bottom: 8rpx;
  color: #dfe8ef;
  font-size: 20rpx;
}

.enemy-rail__stack {
  position: relative;
  height: 96rpx;
}

.enemy-rail__card {
  position: absolute;
  left: 50%;
  top: -10rpx;
  margin-left: -98rpx;
  transform-origin: center bottom;
}

.stage-stack {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 12rpx;
  height: 100%;
}

.stage-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
}

.stage-slot__label {
  font-size: 21rpx;
  font-weight: 800;
  color: #dfe8ef;
}

.stage-slot__placeholder,
.board-card {
  width: var(--field-w);
}

.stage-slot__placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(var(--field-h) - 24rpx);
  padding: 0 16rpx;
  border-radius: 22rpx;
  border: 2rpx dashed rgba(137, 170, 195, 0.18);
  background: linear-gradient(180deg, rgba(16, 30, 41, 0.94), rgba(9, 18, 26, 0.96));
  color: #8fa1ad;
  font-size: 20rpx;
  text-align: center;
}

.stage-slot__placeholder--warm {
  border-color: rgba(241, 196, 104, 0.2);
}

.board-card {
  height: var(--field-h);
  perspective: 1200rpx;
}

.board-card :deep(.game-card) {
  width: 100%;
  min-height: 100%;
  height: 100%;
}

.board-card :deep(.game-card__frame),
.board-card :deep(.game-card__back-frame) {
  inset: 6rpx;
}

.board-card :deep(.game-card__frame) {
  padding: 10rpx 8rpx 8rpx;
}

.board-card :deep(.game-card__name) {
  font-size: 20rpx;
}

.board-card :deep(.game-card__subtitle),
.board-card :deep(.game-card__special),
.board-card :deep(.game-card__kind),
.board-card :deep(.game-card__cost),
.board-card :deep(.game-card__keyword),
.board-card :deep(.game-card__stat-label),
.board-card :deep(.game-card__back-title) {
  font-size: 12rpx;
}

.board-card :deep(.game-card__stat-value) {
  font-size: 17rpx;
}

.board-card__inner {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  transition: transform 0.68s cubic-bezier(0.2, 0.7, 0.2, 1);
}

.board-card--revealed .board-card__inner {
  transform: rotateY(180deg);
}

.board-card__face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
}

.board-card__face--front {
  transform: rotateY(180deg);
}

.stage-core {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10rpx;
  padding: 16rpx 18rpx;
  border-radius: 24rpx;
  border: 1rpx solid rgba(231, 193, 126, 0.16);
  background:
    radial-gradient(circle at center, rgba(241, 196, 104, 0.13), transparent 48%),
    linear-gradient(180deg, rgba(22, 35, 45, 0.98), rgba(9, 17, 25, 0.98));
}

.stage-core__timer {
  width: 96rpx;
  height: 96rpx;
  border-radius: 50%;
  border: 4rpx solid rgba(243, 209, 143, 0.26);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff0c5;
}

.stage-core__timer-value {
  font-size: 36rpx;
  font-weight: 900;
}

.stage-core__timer-unit,
.stage-core__log {
  font-size: 18rpx;
}

.stage-core__phase {
  font-size: 24rpx;
  font-weight: 800;
  color: #f7efdf;
}

.stage-core__log {
  line-height: 1.5;
  color: #94a7b3;
  text-align: center;
}

.hand-box__title {
  display: block;
  font-size: 28rpx;
  font-weight: 900;
  color: #f8efdf;
}

.hand-box__sub {
  display: block;
  margin-top: 6rpx;
  font-size: 18rpx;
}

.linear-hand {
  position: relative;
  height: var(--hand-h);
  margin-top: 12rpx;
}

.linear-hand__card {
  position: absolute;
  left: 50%;
  bottom: 0;
  margin-left: -98rpx;
  transform-origin: center bottom;
  will-change: transform, z-index;
}

.linear-hand__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  border-radius: 18rpx;
  border: 1rpx dashed rgba(226, 190, 126, 0.2);
  color: #93a5b2;
  font-size: 20rpx;
  text-align: center;
  padding: 0 18rpx;
}

@media screen and (max-width: 420px) {
  .battle-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .battle-header__score,
  .battle-header__actions {
    justify-content: space-between;
  }

  .battle-header,
  .player-hud,
  .command-panel {
    padding: 16rpx;
  }

  .player-hud__avatar {
    width: 70rpx;
    height: 70rpx;
    border-radius: 18rpx;
  }

  .player-hud__name {
    font-size: 28rpx;
  }

  .battle-stage {
    padding: 102rpx 14rpx 18rpx;
  }

  .stage-core__timer {
    width: 84rpx;
    height: 84rpx;
  }
}

@media screen and (orientation: landscape) {
  .battle-shell {
    gap: 8rpx;
    padding: calc(8rpx + env(safe-area-inset-top)) 10rpx calc(8rpx + env(safe-area-inset-bottom));
  }

  .battle-header,
  .player-hud,
  .command-panel {
    padding: 10rpx 12rpx;
  }

  .battle-header {
    grid-template-columns: minmax(180rpx, 1fr) auto auto;
    gap: 8rpx;
    min-height: 0;
  }

  .battle-header__title {
    font-size: 28rpx;
    line-height: 1;
  }

  .battle-header__sub {
    margin-top: 2rpx;
    font-size: 14rpx;
  }

  .battle-header__score {
    gap: 8rpx;
    font-size: 20rpx;
  }

  .battle-header__timer {
    min-width: 76rpx;
    padding: 6rpx 10rpx;
  }

  .battle-header__timer-value {
    font-size: 20rpx;
  }

  .battle-header__timer-label {
    margin-top: 2rpx;
    font-size: 12rpx;
  }

  .battle-header__start {
    min-width: 74rpx;
    height: 44rpx;
    padding: 0 12rpx;
    font-size: 16rpx;
  }

  .battle-layout {
    grid-template-columns: 190rpx minmax(0, 1fr) 222rpx;
    grid-template-rows: minmax(0, 1fr);
    gap: 8rpx;
    align-items: stretch;
  }

  .battle-layout--free {
    display: block;
    height: 100%;
    padding-bottom: 0;
  }

  .battle-overlay-controls {
    top: calc(6rpx + env(safe-area-inset-top));
    right: 8rpx;
    gap: 8rpx;
    padding: 8rpx 10rpx;
  }

  .battle-overlay-controls__score {
    font-size: 14rpx;
  }

  .battle-overlay-controls__tools {
    gap: 6rpx;
  }

  .battle-overlay-controls__timer {
    padding: 4rpx 8rpx;
  }

  .battle-overlay-controls__timer-value {
    font-size: 14rpx;
  }

  .battle-overlay-controls__timer-label {
    font-size: 10rpx;
  }

  .battle-overlay-controls__start {
    min-width: 54rpx;
    height: 32rpx;
    padding: 0 8rpx;
    font-size: 12rpx;
  }

  .player-hud,
  .battle-stage,
  .command-panel {
    min-height: 0;
  }

  .player-hud--corner {
    padding: 8rpx 10rpx;
  }

  .player-hud--enemy-corner {
    top: 8rpx;
    left: 8rpx;
  }

  .player-hud--self-corner {
    right: 8rpx;
    bottom: calc(env(safe-area-inset-bottom) + 8rpx);
  }

  .command-panel.player-hud--self-corner {
    display: flex;
    grid-template-rows: none;
  }

  .player-hud,
  .command-panel {
    gap: 8rpx;
  }

  .battle-stage {
    padding: 62rpx 10rpx 10rpx;
  }

  .enemy-rail {
    top: 6rpx;
    width: min(300rpx, calc(100% - 20rpx));
  }

  .enemy-rail__stack {
    height: 54rpx;
  }

  .enemy-rail__head {
    margin-bottom: 4rpx;
    font-size: 12rpx;
  }

  .stage-stack {
    grid-template-rows: minmax(0, 1fr) auto minmax(0, 1fr);
    gap: 6rpx;
  }

  .stage-core {
    gap: 6rpx;
    padding: 8rpx 10rpx;
    border-radius: 18rpx;
  }

  .stage-core__timer {
    width: 52rpx;
    height: 52rpx;
    border-width: 2rpx;
  }

  .stage-core__timer-value {
    font-size: 18rpx;
  }

  .stage-core__timer-unit,
  .stage-core__log,
  .hand-box__sub,
  .player-hud__status,
  .battle-header__sub {
    font-size: 11rpx;
  }

  .stage-core__phase,
  .hand-box__title,
  .player-hud__name {
    font-size: 16rpx;
  }

  .stage-core__phase {
    line-height: 1.2;
  }

  .stage-core__flags,
  .player-hud__badges {
    gap: 6rpx;
  }

  .stage-slot {
    gap: 6rpx;
  }

  .stage-slot__head {
    gap: 6rpx;
  }

  .stage-slot__label {
    font-size: 12rpx;
  }

  .player-hud__avatar {
    width: 28rpx;
    height: 28rpx;
    min-width: 28rpx;
    min-height: 28rpx;
    border-radius: 8rpx;
    font-size: 12rpx;
  }

  .player-hud__label {
    font-size: 10rpx;
  }

  .player-hud__name {
    margin-top: 2rpx;
    font-size: 10rpx;
  }

  .player-hud__status {
    margin-top: 2rpx;
    font-size: 8rpx;
  }

  .energy-box {
    padding: 8rpx 10rpx;
    border-radius: 16rpx;
  }

  .energy-box__value {
    font-size: 12rpx;
  }

  .energy-box__meta text:first-child {
    font-size: 8rpx;
  }

  .energy-box__cell {
    height: 8rpx;
  }

  .energy-box__cells {
    gap: 4rpx;
    margin-top: 8rpx;
  }

  .equip-strip :deep(.equipment-slot--minimal) {
    width: 84rpx;
    min-height: 52rpx;
    padding: 6rpx 8rpx;
    border-radius: 12rpx;
  }

  .equip-strip :deep(.equipment-slot--minimal .equipment-slot__name) {
    margin-top: 10rpx;
    font-size: 13rpx;
  }

  .equip-strip :deep(.equipment-slot--minimal .equipment-slot__phase) {
    top: 4rpx;
    right: 4rpx;
    min-width: 22rpx;
    padding: 2rpx 5rpx;
    font-size: 11rpx;
  }

  .equip-strip__empty {
    min-height: 50rpx;
    font-size: 8rpx;
  }

  .command-panel {
    display: grid;
    grid-template-rows: auto auto auto minmax(0, 1fr);
    gap: 8rpx;
  }

  .hand-box {
    min-height: 0;
  }

  .hand-box--floating {
    position: fixed;
    width: auto;
    min-width: 0;
    padding: 0;
    z-index: 20;
  }

  .linear-hand {
    height: var(--hand-h);
    margin-top: 0;
    overflow: visible;
  }

  .linear-hand__empty {
    font-size: 12rpx;
    padding: 0 12rpx;
  }

  .pill {
    padding: 4rpx 8rpx;
    font-size: 11rpx;
  }

  .hand-box--floating .linear-hand__card {
    bottom: 0;
  }
}

@keyframes player-dead-flash {
  0%,
  100% {
    box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.06), 0 18rpx 38rpx rgba(0, 0, 0, 0.26);
  }
  50% {
    box-shadow:
      inset 0 1rpx 0 rgba(255, 255, 255, 0.06),
      0 0 0 2rpx rgba(228, 83, 83, 0.24),
      0 0 28rpx rgba(228, 83, 83, 0.26);
  }
}

@keyframes equip-gain-pop {
  0% {
    opacity: 0;
    transform: translateY(10rpx) scale(0.82);
  }

  18% {
    opacity: 1;
    transform: translateY(0) scale(1.04);
  }

  72% {
    opacity: 1;
    transform: translateY(-2rpx) scale(1);
  }

  100% {
    opacity: 0;
    transform: translateY(-10rpx) scale(0.94);
  }
}

.start-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.start-overlay__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(4, 8, 14, 0.88);
  backdrop-filter: blur(18rpx);
}

.start-modal {
  position: relative;
  z-index: 1;
  width: min(465rpx, calc(100vw - 48rpx));
  max-width: calc(100vw - 48rpx);
  max-height: calc(100vh - 48rpx);
  padding: 42rpx 30rpx 30rpx;
  border-radius: 30rpx;
  border: 2rpx solid rgba(226, 190, 126, 0.22);
  background: linear-gradient(180deg, rgba(18, 33, 45, 0.98), rgba(8, 16, 24, 0.99));
  text-align: center;
  box-sizing: border-box;
  overflow: hidden;
}

.start-modal__emblem {
  width: 99rpx;
  height: 99rpx;
  margin: 0 auto 18rpx;
  border-radius: 50%;
  border: 4rpx solid rgba(243, 209, 143, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 44rpx;
  font-weight: 900;
  color: #fff0c5;
}

.start-modal__title {
  display: block;
  font-size: 36rpx;
  font-weight: 900;
  color: #fff4de;
  line-height: 1.1;
}

.start-modal__desc {
  display: block;
  margin-top: 12rpx;
  font-size: 17rpx;
  color: #9db0bc;
  line-height: 1.45;
}

.start-modal__btn {
  height: 66rpx;
  margin-top: 15rpx;
  font-size: 21rpx;
  font-weight: 800;
}

.start-modal__btn--primary {
  border-radius: 999rpx;
  background: linear-gradient(180deg, rgba(159, 113, 42, 0.96), rgba(88, 55, 16, 0.98));
  color: #ffe8b8;
}

.start-modal__btn--ghost {
  border-radius: 999rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.1);
  color: #8ea2af;
}

@media screen and (orientation: landscape) {
  .start-overlay {
    padding: 16rpx;
    box-sizing: border-box;
  }

  .start-modal {
    width: 18.75vw;
    min-width: 225rpx;
    max-width: 285rpx;
    max-height: calc(100vh - 36rpx);
    padding: 16rpx 16rpx 15rpx;
    border-radius: 18rpx;
  }

  .start-modal__emblem {
    width: 52rpx;
    height: 52rpx;
    margin-bottom: 8rpx;
    font-size: 24rpx;
    border-width: 2rpx;
  }

  .start-modal__title {
    font-size: 21rpx;
  }

  .start-modal__desc {
    margin-top: 6rpx;
    font-size: 11rpx;
    line-height: 1.35;
  }

  .start-modal__btn {
    height: 39rpx;
    margin-top: 8rpx;
    font-size: 14rpx;
  }
}
</style>
