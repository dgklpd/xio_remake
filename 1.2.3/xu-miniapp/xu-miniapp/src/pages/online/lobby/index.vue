<template>
  <view class="lobby-page">
    <view class="lobby-page__grain" />
    <view class="lobby-page__glow lobby-page__glow--left" />
    <view class="lobby-page__glow lobby-page__glow--right" />

    <view class="lobby-shell">
      <view class="topbar">
        <view class="topbar__header">
          <view class="back-pill" @tap="goBack">
            <text class="back-pill__arrow">‹</text>
            <text class="back-pill__text">返回</text>
          </view>
          <text class="headline__title">联机大厅</text>
        </view>

        <view class="topbar__actions">
          <view class="top-action top-action--soft" @tap="openSheet('join')">
            <text class="top-action__text">加入房间</text>
          </view>

          <view class="top-action top-action--gold" @tap="openSheet('create')">
            <text class="top-action__text">创建房间</text>
          </view>

          <view class="icon-button" @tap="refreshRooms(true)">
            <text class="icon-button__icon">↻</text>
          </view>
        </view>
      </view>

      <scroll-view class="room-cloud" scroll-y>
        <view class="room-cloud__inner">
          <view
            v-for="room in rooms"
            :key="room.room_code"
            class="room-bubble"
            :class="{ 'room-bubble--active': room.room_code === highlightedRoomCode }"
          >
            <view class="room-bubble__cap">
              <text class="room-bubble__status" :class="`room-bubble__status--${room.status}`">
                {{ statusLabelMap[room.status] }}
              </text>
              <text class="room-bubble__code"># {{ room.room_code }}</text>
            </view>

            <view class="room-bubble__main">
              <text class="room-bubble__name">{{ room.room_name }}</text>
              <text class="room-bubble__host">房主：{{ room.host_display_name }}</text>
              <text class="room-bubble__guest">
                {{ room.guest_display_name ? `客位：${room.guest_display_name}` : "客位：等待加入" }}
              </text>
            </view>

            <view class="room-bubble__chips">
              <text class="room-chip">{{ room.host_connected ? "房主在线" : "房主离线" }}</text>
              <text class="room-chip">{{ room.guest_display_name ? "双人房" : "单人等待" }}</text>
              <text class="room-chip">{{ room.host_ready || room.guest_ready ? "准备中" : "未准备" }}</text>
            </view>

            <view class="room-bubble__footer">
              <text class="room-bubble__brief">
                {{
                  room.status === "playing"
                    ? "战斗已开始"
                    : room.status === "full"
                      ? "房间已满"
                      : "现在可加入"
                }}
              </text>

              <view
                class="room-bubble__join"
                :class="{ 'room-bubble__join--disabled': room.status !== 'waiting' }"
                @tap="handleQuickJoin(room.room_code)"
              >
                <text class="room-bubble__join-text">
                  {{
                    room.status === "waiting"
                      ? "加入"
                      : room.status === "full"
                        ? "已满"
                        : "锁定"
                  }}
                </text>
              </view>
            </view>
          </view>

          <view v-if="!rooms.length" class="empty-bubble">
            <text class="empty-bubble__title">大厅里还没有公开房间</text>
            <text class="empty-bubble__desc">现在就创建一个房间，等对手进来开打。</text>
          </view>
        </view>
      </scroll-view>

    </view>

    <view v-if="sheetMode" class="sheet-mask" @tap="closeSheet">
      <view class="sheet-card" @tap.stop>
        <text class="sheet-card__title">{{ sheetMode === "create" ? "创建房间" : "加入房间" }}</text>
        <text class="sheet-card__desc">
          {{
            sheetMode === "create"
              ? "给房间取一个名字，方便在大厅里快速辨认。"
              : "输入 6 位房间号，直接进入指定房间。"
          }}
        </text>

        <view class="field">
          <text class="field__label">你的昵称</text>
          <input
            v-model.trim="profileName"
            class="field__input"
            maxlength="12"
            placeholder="输入你的昵称"
            placeholder-class="field__placeholder"
          />
        </view>

        <view v-if="sheetMode === 'create'" class="field">
          <text class="field__label">房间名</text>
          <input
            v-model.trim="createRoomName"
            class="field__input"
            maxlength="24"
            placeholder="例如：晚饭前来一局"
            placeholder-class="field__placeholder"
          />
        </view>

        <view v-else class="field">
          <text class="field__label">房间号</text>
          <input
            v-model.trim="joinRoomCode"
            class="field__input field__input--code"
            maxlength="6"
            placeholder="输入 6 位房间号"
            placeholder-class="field__placeholder"
          />
        </view>

        <view class="sheet-card__actions">
          <view class="sheet-button sheet-button--ghost" @tap="closeSheet">
            <text class="sheet-button__text">取消</text>
          </view>
          <view class="sheet-button sheet-button--gold" @tap="submitSheet">
            <text class="sheet-button__text">
              {{ submitting ? "处理中..." : sheetMode === "create" ? "确认创建" : "确认加入" }}
            </text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onHide, onLoad, onShow, onUnload } from "@dcloudio/uni-app";
import {
  createOnlineRoom,
  getOrCreateGuestIdentity,
  joinOnlineRoom,
  listOnlineRooms,
  type OnlineRoomListItem,
} from "@/utils/onlineApi";

type SheetMode = "create" | "join" | null;

const statusLabelMap: Record<OnlineRoomListItem["status"], string> = {
  waiting: "等待中",
  full: "已满员",
  playing: "对战中",
  finished: "已结束",
  closed: "已关闭",
};

const rooms = ref<OnlineRoomListItem[]>([]);
const loading = ref(false);
const submitting = ref(false);
const sheetMode = ref<SheetMode>(null);
const createRoomName = ref("");
const joinRoomCode = ref("");
const highlightedRoomCode = ref("");
const lastRefreshAt = ref(Date.now());
const refreshTimer = ref<ReturnType<typeof setInterval> | null>(null);

const profileName = ref(getOrCreateGuestIdentity().display_name);

function normalizedProfileName() {
  return profileName.value.trim() || "玩家";
}

function persistProfileName() {
  profileName.value = normalizedProfileName();
  getOrCreateGuestIdentity(profileName.value);
}

async function refreshRooms(showFeedback = false) {
  if (loading.value) return;
  loading.value = true;
  try {
    rooms.value = await listOnlineRooms(80);
    lastRefreshAt.value = Date.now();
    if (showFeedback) {
      uni.showToast({
        title: "大厅已刷新",
        icon: "none",
      });
    }
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "刷新失败",
      icon: "none",
    });
  } finally {
    loading.value = false;
  }
}

function openSheet(mode: Exclude<SheetMode, null>) {
  persistProfileName();
  sheetMode.value = mode;
  if (mode === "create") {
    createRoomName.value = createRoomName.value.trim() || `${profileName.value}的房间`;
    joinRoomCode.value = "";
  } else {
    joinRoomCode.value = highlightedRoomCode.value || "";
  }
}

function closeSheet() {
  sheetMode.value = null;
}

async function handleQuickJoin(roomCode: string) {
  const targetRoom = rooms.value.find((room) => room.room_code === roomCode);
  if (!targetRoom || targetRoom.status !== "waiting") {
    uni.showToast({
      title: "这个房间暂时不能加入",
      icon: "none",
    });
    return;
  }

  joinRoomCode.value = roomCode;
  sheetMode.value = "join";
}

async function submitSheet() {
  if (!sheetMode.value || submitting.value) return;
  persistProfileName();
  submitting.value = true;
  let targetRoomCode = "";

  try {
    if (sheetMode.value === "create") {
      const response = await createOnlineRoom({
        roomName: createRoomName.value.trim(),
        identity: getOrCreateGuestIdentity(profileName.value),
      });
      highlightedRoomCode.value = response.room.room_code;
      targetRoomCode = response.room.room_code;
      uni.showToast({
        title: `已创建 ${response.room.room_code}`,
        icon: "none",
      });
    } else {
      const response = await joinOnlineRoom(joinRoomCode.value.trim().toUpperCase(), {
        identity: getOrCreateGuestIdentity(profileName.value),
      });
      highlightedRoomCode.value = response.room.room_code;
      targetRoomCode = response.room.room_code;
      uni.showToast({
        title: `已加入 ${response.room.room_code}`,
        icon: "none",
      });
    }

    closeSheet();
    if (targetRoomCode) {
      uni.navigateTo({
        url: `/pages/battle/BattlePage?mode=online&roomCode=${targetRoomCode}`,
      });
    }
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "提交失败",
      icon: "none",
    });
  } finally {
    submitting.value = false;
  }
}

function goBack() {
  uni.navigateBack({
    fail: () => {
      uni.reLaunch({
        url: "/pages/index/index",
      });
    },
  });
}

function startAutoRefresh() {
  stopAutoRefresh();
  refreshTimer.value = setInterval(() => {
    refreshRooms(false);
  }, 8000);
}

function stopAutoRefresh() {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value);
    refreshTimer.value = null;
  }
}

onLoad(() => {
  refreshRooms(false);
  startAutoRefresh();
});

onShow(() => {
  refreshRooms(false);
  startAutoRefresh();
});

onHide(() => {
  stopAutoRefresh();
});

onUnload(() => {
  stopAutoRefresh();
});
</script>

<style scoped lang="scss">
.lobby-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 12%, rgba(66, 150, 186, 0.17), transparent 22%),
    radial-gradient(circle at 82% 18%, rgba(216, 170, 88, 0.16), transparent 22%),
    linear-gradient(180deg, #07131b 0%, #0b1e29 52%, #09131a 100%);
}

.lobby-page__grain {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%) 0 0 / 24rpx 24rpx,
    linear-gradient(225deg, rgba(255, 255, 255, 0.014) 25%, transparent 25%) 0 0 / 32rpx 32rpx;
  opacity: 0.42;
  pointer-events: none;
}

.lobby-page__glow {
  position: absolute;
  border-radius: 999rpx;
  filter: blur(48rpx);
  pointer-events: none;
}

.lobby-page__glow--left {
  top: 180rpx;
  left: -80rpx;
  width: 320rpx;
  height: 320rpx;
  background: rgba(45, 127, 179, 0.16);
}

.lobby-page__glow--right {
  right: -100rpx;
  bottom: 160rpx;
  width: 360rpx;
  height: 360rpx;
  background: rgba(210, 164, 84, 0.12);
}

.lobby-shell {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  padding: calc(env(safe-area-inset-top) + 6rpx) 24rpx calc(20rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.topbar {
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.topbar__header {
  display: flex;
  align-items: center;
  gap: 14rpx;
}

.back-pill {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  align-self: flex-start;
  min-height: 64rpx;
  padding: 0 22rpx;
  border-radius: 999rpx;
  background: rgba(8, 23, 33, 0.76);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
}

.back-pill__arrow,
.back-pill__text {
  color: #f1e3c2;
  font-size: 24rpx;
  font-weight: 700;
}

.headline__title {
  color: #fff2d0;
  font-size: 50rpx;
  line-height: 1.06;
  font-weight: 900;
}

.topbar__actions {
  display: flex;
  align-items: stretch;
  justify-content: flex-start;
  flex-wrap: wrap;
  gap: 12rpx;
}

.icon-button {
  width: 82rpx;
  height: 82rpx;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(180deg, rgba(19, 39, 54, 0.96), rgba(8, 22, 31, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.05), transparent);
  box-shadow: 0 14rpx 26rpx rgba(0, 0, 0, 0.22);
}

.icon-button__icon {
  color: #f5ead6;
  font-size: 34rpx;
  font-weight: 900;
}

.top-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 168rpx;
  min-height: 82rpx;
  padding: 0 22rpx;
  border-radius: 999rpx;
  box-shadow: 0 14rpx 26rpx rgba(0, 0, 0, 0.22);
}

.top-action--soft {
  background:
    linear-gradient(180deg, rgba(19, 39, 54, 0.96), rgba(8, 22, 31, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.05), transparent);
}

.top-action--gold {
  background:
    linear-gradient(180deg, rgba(161, 115, 45, 0.98), rgba(89, 58, 18, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent);
}

.top-action__text {
  color: #f8efdb;
  font-size: 25rpx;
  font-weight: 800;
}

.room-cloud {
  flex: 1;
  min-height: 0;
  margin-top: 18rpx;
}

.room-cloud__inner {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 18rpx;
  padding-bottom: 12rpx;
}

.room-bubble {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12rpx;
  width: calc(50% - 9rpx);
  aspect-ratio: 1 / 1;
  padding: 18rpx;
  border-radius: 30rpx;
  box-sizing: border-box;
  background:
    radial-gradient(circle at 84% 16%, rgba(255, 255, 255, 0.08), transparent 24%),
    linear-gradient(180deg, rgba(17, 35, 48, 0.96), rgba(8, 21, 29, 0.98));
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 18rpx 32rpx rgba(0, 0, 0, 0.2);
}

.room-bubble--active {
  border-color: rgba(240, 200, 118, 0.48);
  box-shadow: 0 18rpx 38rpx rgba(77, 55, 18, 0.24);
}

.room-bubble__cap,
.room-bubble__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
}

.room-bubble__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  font-size: 20rpx;
  font-weight: 800;
}

.room-bubble__status--waiting {
  color: #f4e8ca;
  background: rgba(55, 116, 139, 0.34);
}

.room-bubble__status--full,
.room-bubble__status--playing {
  color: #f8e7c4;
  background: rgba(160, 115, 46, 0.42);
}

.room-bubble__status--finished,
.room-bubble__status--closed {
  color: #d4d9dc;
  background: rgba(255, 255, 255, 0.12);
}

.room-bubble__code {
  color: #f3ddb1;
  font-size: 22rpx;
  font-weight: 800;
}

.room-bubble__main {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.room-bubble__name {
  color: #fff1cf;
  font-size: 28rpx;
  line-height: 1.26;
  font-weight: 900;
}

.room-bubble__host,
.room-bubble__guest,
.room-bubble__brief {
  color: #a7bac4;
  font-size: 18rpx;
  line-height: 1.45;
}

.room-bubble__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
}

.room-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36rpx;
  padding: 0 14rpx;
  border-radius: 999rpx;
  color: #d8e1e5;
  font-size: 18rpx;
  background: rgba(255, 255, 255, 0.08);
}

.room-bubble__join {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 96rpx;
  min-height: 62rpx;
  padding: 0 22rpx;
  border-radius: 999rpx;
  background:
    linear-gradient(180deg, rgba(161, 115, 45, 0.98), rgba(89, 58, 18, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent);
}

.room-bubble__join--disabled {
  background: rgba(255, 255, 255, 0.12);
}

.room-bubble__join-text {
  color: #f7efe2;
  font-size: 24rpx;
  font-weight: 800;
}

.empty-bubble {
  width: 100%;
  min-height: 260rpx;
  padding: 34rpx;
  border-radius: 34rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 18rpx;
  background: rgba(8, 22, 31, 0.82);
  border: 2rpx dashed rgba(255, 255, 255, 0.08);
}

.empty-bubble__title {
  color: #fff1cf;
  font-size: 34rpx;
  font-weight: 900;
}

.empty-bubble__desc {
  color: #9fb1bb;
  font-size: 22rpx;
  line-height: 1.6;
}

.sheet-mask {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30rpx;
  box-sizing: border-box;
  background: rgba(3, 10, 14, 0.62);
}

.sheet-card {
  width: 100%;
  max-width: 640rpx;
  padding: 34rpx;
  border-radius: 34rpx;
  box-sizing: border-box;
  background:
    linear-gradient(180deg, rgba(18, 36, 49, 0.98), rgba(7, 19, 28, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent);
  box-shadow: 0 24rpx 44rpx rgba(0, 0, 0, 0.28);
}

.sheet-card__title {
  color: #fff1cf;
  font-size: 36rpx;
  font-weight: 900;
}

.sheet-card__desc {
  display: block;
  margin-top: 10rpx;
  color: #9db0bb;
  font-size: 22rpx;
  line-height: 1.6;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 22rpx;
}

.field__label {
  color: #e6d7b2;
  font-size: 24rpx;
  font-weight: 700;
}

.field__input {
  width: 100%;
  min-height: 92rpx;
  padding: 0 24rpx;
  border-radius: 24rpx;
  box-sizing: border-box;
  background: rgba(255, 255, 255, 0.05);
  color: #f8f2e5;
  font-size: 28rpx;
}

.field__input--code {
  letter-spacing: 6rpx;
  text-transform: uppercase;
}

.field__placeholder {
  color: rgba(153, 170, 182, 0.78);
}

.sheet-card__actions {
  display: flex;
  gap: 16rpx;
  margin-top: 30rpx;
}

.sheet-button {
  flex: 1;
  min-height: 92rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sheet-button--ghost {
  background: rgba(255, 255, 255, 0.06);
}

.sheet-button--gold {
  background:
    linear-gradient(180deg, rgba(160, 115, 46, 0.98), rgba(89, 57, 18, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent);
}

.sheet-button__text {
  color: #f7efe0;
  font-size: 28rpx;
  font-weight: 800;
}

@media (max-width: 390px) {
  .headline__title {
    font-size: 44rpx;
  }

  .topbar__actions {
    gap: 10rpx;
  }

  .icon-button {
    width: 76rpx;
    height: 76rpx;
  }

  .top-action {
    min-width: 148rpx;
    min-height: 76rpx;
    padding: 0 16rpx;
  }

  .top-action__text {
    font-size: 23rpx;
  }

  .room-bubble {
    padding: 16rpx;
    border-radius: 28rpx;
  }

  .room-bubble__name {
    font-size: 25rpx;
  }

  .room-bubble__host,
  .room-bubble__guest,
  .room-bubble__brief {
    font-size: 17rpx;
  }
}
</style>
