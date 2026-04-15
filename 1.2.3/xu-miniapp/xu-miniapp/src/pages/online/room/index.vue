<template>
  <view class="online-room-page">
    <view class="online-room-page__grain" />
    <view class="online-room-page__glow online-room-page__glow--left" />
    <view class="online-room-page__glow online-room-page__glow--right" />

    <view class="online-room-page__stage">
      <view class="online-room-page__hud online-room-page__hud--left">
        <text class="online-room-page__hud-label">房间号</text>
        <text class="online-room-page__hud-value">{{ roomCode || "--" }}</text>
      </view>

      <view class="online-room-page__hud online-room-page__hud--right">
        <text class="online-room-page__hud-label">连接状态</text>
        <text class="online-room-page__hud-value">{{ connectionLabel }}</text>
      </view>
    </view>

    <view class="wait-overlay">
      <view class="wait-overlay__backdrop" />

      <view class="wait-modal">
        <view class="wait-modal__emblem">蓄</view>
        <text class="wait-modal__title">联机对战</text>
        <text class="wait-modal__desc">{{ waitingMessage }}</text>

        <view class="wait-modal__room-pill">
          <text>{{ roomNameLabel }}</text>
          <text># {{ roomCode || "--" }}</text>
        </view>

        <view class="wait-modal__players">
          <view class="wait-player">
            <text class="wait-player__role">房主</text>
            <text class="wait-player__name">{{ hostName }}</text>
            <text class="wait-player__status">{{ hostStatusLabel }}</text>
          </view>

          <view class="wait-player">
            <text class="wait-player__role">客位</text>
            <text class="wait-player__name">{{ guestName }}</text>
            <text class="wait-player__status">{{ guestStatusLabel }}</text>
          </view>
        </view>

        <view class="wait-modal__actions">
          <view
            class="wait-modal__btn wait-modal__btn--primary"
            :class="{ 'wait-modal__btn--disabled': !canReady }"
            @tap="handleReady"
          >
            <text>{{ readyButtonLabel }}</text>
          </view>

          <view class="wait-modal__btn wait-modal__btn--ghost" @tap="handleExit">
            <text>{{ leaving ? "退出中..." : "退出" }}</text>
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
  buildOnlineRoomSocketUrl,
  clearSavedOnlineSession,
  getOnlineRoom,
  getSavedOnlineSession,
  leaveOnlineRoom,
  type OnlineRoomState,
} from "@/utils/onlineApi";

type RoomSeat = "host" | "guest";
type RoomSocketStatus = "idle" | "connecting" | "open" | "closed" | "error" | "reconnecting";

interface OnlineSessionCache {
  room_code: string;
  room_name?: string;
  seat: RoomSeat;
  session_token: string;
}

interface OnlineSocketMessage {
  action: string;
  state?: OnlineRoomState;
  payload?: Record<string, unknown>;
  [key: string]: unknown;
}

const roomCode = ref("");
const roomState = ref<OnlineRoomState | null>(null);
const seat = ref<RoomSeat>("host");
const sessionToken = ref("");
const socketStatus = ref<RoomSocketStatus>("idle");
const leaving = ref(false);
const startedHintShown = ref(false);
const topInset = ref(0);

let socketTask: UniApp.SocketTask | null = null;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let manualClose = false;

const selfSeatState = computed(() => {
  if (!roomState.value) return null;
  return seat.value === "host" ? roomState.value.host : roomState.value.guest;
});

const otherSeatState = computed(() => {
  if (!roomState.value) return null;
  return seat.value === "host" ? roomState.value.guest : roomState.value.host;
});

const connectionLabel = computed(() => {
  if (socketStatus.value === "open") return "已连接";
  if (socketStatus.value === "connecting" || socketStatus.value === "reconnecting") return "连接中";
  if (socketStatus.value === "error") return "连接异常";
  return "未连接";
});

const hostName = computed(() => roomState.value?.host.display_name || "等待房主");
const guestName = computed(() => roomState.value?.guest?.display_name || "等待加入");
const roomNameLabel = computed(() => roomState.value?.room_name || "联机房间");

const hostStatusLabel = computed(() => {
  const host = roomState.value?.host;
  if (!host) return "";
  if (!host.connected) return "离线";
  if (host.ready) return "已准备";
  return "未准备";
});

const guestStatusLabel = computed(() => {
  const guest = roomState.value?.guest;
  if (!guest) return "未加入";
  if (!guest.connected) return "离线";
  if (guest.ready) return "已准备";
  return "未准备";
});

const waitingMessage = computed(() => {
  const room = roomState.value;
  if (!room) return "正在连接房间";
  if (!room.guest) return "正在等待玩家加入";
  if (room.status === "playing") return "双方已准备，对局正在启动";
  return `玩家 ${otherSeatState.value?.display_name || "对手"} 已经加入`;
});

const canReady = computed(() => {
  const room = roomState.value;
  if (!room || !room.guest) return false;
  if (room.status !== "waiting") return false;
  if (socketStatus.value !== "open") return false;
  if (leaving.value) return false;
  return !selfSeatState.value?.ready;
});

const readyButtonLabel = computed(() => {
  const room = roomState.value;
  if (!room?.guest) return "等待加入";
  if (room.status === "playing") return "已开始";
  if (selfSeatState.value?.ready) return "已准备";
  return "准备";
});

function updateTopInset() {
  const info = uni.getSystemInfoSync();
  const statusBarHeight = Number(info.statusBarHeight) || 0;
  topInset.value = Math.max(16, statusBarHeight + 12);
}

function clearHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
}

function clearReconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function closeSocket() {
  manualClose = true;
  clearHeartbeat();
  clearReconnect();
  if (socketTask) {
    socketTask.close({});
    socketTask = null;
  }
  socketStatus.value = "closed";
}

function startHeartbeat() {
  clearHeartbeat();
  heartbeatTimer = setInterval(() => {
    if (!socketTask || socketStatus.value !== "open") return;
    socketTask.send({
      data: JSON.stringify({
        action: "ping",
        payload: { ts: Date.now() },
      }),
    });
  }, 15000);
}

function scheduleReconnect() {
  if (manualClose || leaving.value || !roomCode.value || !sessionToken.value) return;
  clearReconnect();
  socketStatus.value = "reconnecting";
  reconnectTimer = setTimeout(() => {
    connectRoomSocket();
  }, 2000);
}

function handleSocketMessage(raw: string) {
  let message: OnlineSocketMessage;
  try {
    message = JSON.parse(raw) as OnlineSocketMessage;
  } catch {
    return;
  }

  if (message.action === "pong") return;

  if (message.action === "room_state" && message.state) {
    roomState.value = message.state;
    if (message.state.status === "playing" && !startedHintShown.value) {
      startedHintShown.value = true;
      uni.showToast({
        title: "双方已准备，联机对战即将接入",
        icon: "none",
      });
    }
    return;
  }

  if (message.action === "player_disconnected") {
    uni.showToast({
      title: "有玩家掉线，正在等待重连",
      icon: "none",
    });
    return;
  }

  if (message.action === "player_reconnected") {
    uni.showToast({
      title: "玩家已重新连接",
      icon: "none",
    });
    return;
  }

  if (message.action === "room_closed") {
    uni.showToast({
      title: "房间已关闭",
      icon: "none",
    });
    clearSavedOnlineSession();
    closeSocket();
    setTimeout(() => {
      uni.reLaunch({
        url: "/pages/online/lobby/index",
      });
    }, 220);
    return;
  }

  if (message.action === "error") {
    const text = typeof message.payload?.message === "string" ? message.payload.message : "房间连接异常";
    uni.showToast({
      title: text,
      icon: "none",
    });
  }
}

function connectRoomSocket() {
  if (!roomCode.value || !sessionToken.value) return;
  closeSocket();
  manualClose = false;
  socketStatus.value = "connecting";

  const url = buildOnlineRoomSocketUrl(roomCode.value, seat.value, sessionToken.value);
  socketTask = uni.connectSocket({ url });

  socketTask.onOpen(() => {
    socketStatus.value = "open";
    startHeartbeat();
    socketTask?.send({
      data: JSON.stringify({
        action: "get_room_state",
        payload: {},
      }),
    });
  });

  socketTask.onMessage((event) => {
    if (!event.data) return;
    handleSocketMessage(String(event.data));
  });

  socketTask.onClose(() => {
    clearHeartbeat();
    socketTask = null;
    if (!manualClose) {
      socketStatus.value = "closed";
      scheduleReconnect();
    }
  });

  socketTask.onError(() => {
    clearHeartbeat();
    socketStatus.value = "error";
    scheduleReconnect();
  });
}

async function fetchRoomState() {
  if (!roomCode.value) return;
  try {
    roomState.value = await getOnlineRoom(roomCode.value);
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "加载房间失败",
      icon: "none",
    });
  }
}

function initializeSession(options?: Record<string, string>) {
  const session = getSavedOnlineSession<OnlineSessionCache>();
  const optionRoomCode = options?.roomCode || "";
  const resolvedRoomCode = optionRoomCode || (session && typeof session === "object" ? session.room_code : "");

  if (!session || typeof session !== "object" || !resolvedRoomCode) {
    uni.showToast({
      title: "未找到房间信息",
      icon: "none",
    });
    setTimeout(() => {
      uni.reLaunch({
        url: "/pages/online/lobby/index",
      });
    }, 200);
    return false;
  }

  roomCode.value = resolvedRoomCode;
  seat.value = session.seat;
  sessionToken.value = session.session_token;
  return true;
}

function handleReady() {
  if (!canReady.value || !socketTask || socketStatus.value !== "open") return;
  socketTask.send({
    data: JSON.stringify({
      action: "ready_room",
      payload: {
        ready: true,
      },
    }),
  });
}

async function handleExit() {
  if (leaving.value || !roomCode.value) return;
  leaving.value = true;
  try {
    await leaveOnlineRoom(roomCode.value, {
      seat: seat.value,
    });
    clearSavedOnlineSession();
    closeSocket();
    uni.reLaunch({
      url: "/pages/online/lobby/index",
    });
  } catch (error) {
    uni.showToast({
      title: error instanceof Error ? error.message : "退出房间失败",
      icon: "none",
    });
  } finally {
    leaving.value = false;
  }
}

onLoad((options) => {
  updateTopInset();
  if (!initializeSession((options ?? {}) as Record<string, string>)) return;
  fetchRoomState();
  connectRoomSocket();
});

onShow(() => {
  updateTopInset();
  if (!roomCode.value || !sessionToken.value) return;
  if (socketStatus.value !== "open" && socketStatus.value !== "connecting") {
    connectRoomSocket();
  }
});

onHide(() => {
  clearHeartbeat();
});

onUnload(() => {
  closeSocket();
});
</script>

<style scoped lang="scss">
.online-room-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(circle at 20% 10%, rgba(42, 124, 176, 0.16), transparent 24%),
    radial-gradient(circle at 82% 18%, rgba(209, 165, 86, 0.14), transparent 20%),
    linear-gradient(180deg, #07131b 0%, #0a1b26 54%, #081118 100%);
}

.online-room-page__grain {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.02) 25%, transparent 25%) 0 0 / 24rpx 24rpx,
    linear-gradient(225deg, rgba(255, 255, 255, 0.014) 25%, transparent 25%) 0 0 / 32rpx 32rpx;
  opacity: 0.42;
  pointer-events: none;
}

.online-room-page__glow {
  position: absolute;
  border-radius: 999rpx;
  filter: blur(52rpx);
  pointer-events: none;
}

.online-room-page__glow--left {
  left: -120rpx;
  top: 220rpx;
  width: 380rpx;
  height: 380rpx;
  background: rgba(52, 133, 180, 0.14);
}

.online-room-page__glow--right {
  right: -110rpx;
  bottom: 180rpx;
  width: 360rpx;
  height: 360rpx;
  background: rgba(214, 167, 89, 0.1);
}

.online-room-page__stage {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  padding: calc(20rpx + env(safe-area-inset-top)) 22rpx calc(20rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.online-room-page__hud {
  position: absolute;
  top: v-bind(topInset + "px");
  min-width: 170rpx;
  padding: 16rpx 22rpx;
  border-radius: 28rpx;
  background: rgba(10, 24, 34, 0.82);
  border: 2rpx solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 16rpx 30rpx rgba(0, 0, 0, 0.22);
}

.online-room-page__hud--left {
  left: 22rpx;
}

.online-room-page__hud--right {
  right: 22rpx;
  text-align: right;
}

.online-room-page__hud-label {
  color: #94a9b4;
  font-size: 18rpx;
}

.online-room-page__hud-value {
  display: block;
  margin-top: 6rpx;
  color: #f4e7c7;
  font-size: 24rpx;
  font-weight: 800;
}

.wait-overlay {
  position: fixed;
  inset: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30rpx;
  box-sizing: border-box;
}

.wait-overlay__backdrop {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at center, rgba(10, 20, 28, 0.1), rgba(4, 10, 14, 0.42) 72%),
    linear-gradient(180deg, rgba(4, 10, 14, 0.18), rgba(4, 10, 14, 0.38));
}

.wait-modal {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 620rpx;
  padding: 34rpx 30rpx 30rpx;
  border-radius: 36rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18rpx;
  box-sizing: border-box;
  background:
    linear-gradient(180deg, rgba(18, 37, 50, 0.96), rgba(7, 19, 28, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.05), transparent);
  border: 2rpx solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 26rpx 52rpx rgba(0, 0, 0, 0.28);
}

.wait-modal__emblem {
  width: 108rpx;
  height: 108rpx;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f7ead1;
  font-size: 44rpx;
  font-weight: 900;
  background:
    linear-gradient(180deg, rgba(160, 114, 45, 0.98), rgba(90, 57, 18, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent);
  box-shadow: 0 16rpx 30rpx rgba(78, 54, 18, 0.3);
}

.wait-modal__title {
  color: #fff1cf;
  font-size: 42rpx;
  font-weight: 900;
}

.wait-modal__desc {
  color: #a9bcc6;
  font-size: 24rpx;
  line-height: 1.6;
  text-align: center;
}

.wait-modal__room-pill {
  display: flex;
  align-items: center;
  gap: 16rpx;
  min-height: 64rpx;
  padding: 0 20rpx;
  border-radius: 999rpx;
  color: #f0dfbc;
  font-size: 22rpx;
  background: rgba(255, 255, 255, 0.06);
}

.wait-modal__players {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.wait-player {
  display: grid;
  grid-template-columns: 88rpx minmax(0, 1fr) auto;
  gap: 12rpx;
  align-items: center;
  min-height: 86rpx;
  padding: 0 18rpx;
  border-radius: 24rpx;
  background: rgba(255, 255, 255, 0.05);
}

.wait-player__role {
  color: #dbc89d;
  font-size: 22rpx;
  font-weight: 800;
}

.wait-player__name {
  color: #f7efdc;
  font-size: 26rpx;
  font-weight: 700;
}

.wait-player__status {
  color: #9fb2bc;
  font-size: 22rpx;
}

.wait-modal__actions {
  width: 100%;
  display: flex;
  gap: 16rpx;
  margin-top: 6rpx;
}

.wait-modal__btn {
  flex: 1;
  min-height: 96rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f8efdc;
  font-size: 30rpx;
  font-weight: 800;
}

.wait-modal__btn--primary {
  background:
    linear-gradient(180deg, rgba(160, 114, 45, 0.98), rgba(90, 57, 18, 0.98)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.08), transparent);
}

.wait-modal__btn--primary.wait-modal__btn--disabled {
  background: rgba(255, 255, 255, 0.12);
  color: rgba(248, 239, 220, 0.6);
}

.wait-modal__btn--ghost {
  background: rgba(255, 255, 255, 0.07);
}

@media (max-width: 390px) {
  .wait-modal {
    padding: 30rpx 24rpx 24rpx;
  }

  .wait-modal__title {
    font-size: 38rpx;
  }

  .wait-modal__desc {
    font-size: 22rpx;
  }

  .wait-modal__btn {
    min-height: 88rpx;
    font-size: 28rpx;
  }
}
</style>
