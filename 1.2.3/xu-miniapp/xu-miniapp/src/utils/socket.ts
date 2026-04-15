import type { ServerGameState, ServerRoundResolution } from "@/stores/battle";

export type SocketConnectionStatus =
  | "idle"
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed"
  | "error";

export interface SocketIncomingMessage {
  action: string;
  payload?: unknown;
  state?: ServerGameState | Record<string, unknown>;
  details?: ServerRoundResolution | Record<string, unknown>;
  [key: string]: unknown;
}

type MessageHandler = (message: SocketIncomingMessage) => void;
type StatusHandler = (status: SocketConnectionStatus) => void;

let socketTask: UniApp.SocketTask | null = null;
let currentUrl = "";
let manualClose = false;
let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectCount = 0;
let currentStatus: SocketConnectionStatus = "idle";

const messageHandlers = new Set<MessageHandler>();
const statusHandlers = new Set<StatusHandler>();

const HEARTBEAT_INTERVAL = 15000;
const MAX_RECONNECT_DELAY = 15000;

function updateStatus(status: SocketConnectionStatus) {
  currentStatus = status;
  statusHandlers.forEach((handler) => handler(status));
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

function startHeartbeat() {
  clearHeartbeat();
  heartbeatTimer = setInterval(() => {
    sendMessage("ping", {
      ts: Date.now(),
    });
  }, HEARTBEAT_INTERVAL);
}

function scheduleReconnect() {
  if (manualClose || !currentUrl) {
    console.log(`[Socket] 跳过重连: manualClose=${manualClose}, hasUrl=${!!currentUrl}`);
    return;
  }

  clearReconnect();
  const delay = Math.min(1000 * 2 ** reconnectCount, MAX_RECONNECT_DELAY);
  reconnectCount += 1;
  console.log(`[Socket] 将在 ${delay}ms 后重连 (第${reconnectCount}次)`);
  updateStatus("reconnecting");

  reconnectTimer = setTimeout(() => {
    console.log(`[Socket] 执行重连...`);
    connectSocket(currentUrl);
  }, delay);
}

function bindSocketEvents(task: UniApp.SocketTask) {
  const connectStart = Date.now();

  task.onOpen(() => {
    console.log(`[Socket] 连接已建立 (总耗时 ${Date.now() - connectStart}ms)`);
    reconnectCount = 0;
    updateStatus("open");
    startHeartbeat();
  });

  task.onMessage((event) => {
    if (!event.data) {
      return;
    }

    try {
      const message = JSON.parse(String(event.data)) as SocketIncomingMessage;

      if (message.action === "pong") {
        return;
      }

      messageHandlers.forEach((handler) => handler(message));
    } catch {
      messageHandlers.forEach((handler) =>
        handler({
          action: "error",
          payload: {
            message: "无法解析服务器消息",
          },
        }),
      );
    }
  });

  task.onClose(() => {
    console.log(`[Socket] 连接已关闭`);
    clearHeartbeat();
    updateStatus("closed");
    socketTask = null;
    scheduleReconnect();
  });

  task.onError((err) => {
    console.error(`[Socket] 连接错误:`, JSON.stringify(err));
    clearHeartbeat();
    updateStatus("error");
    scheduleReconnect();
  });
}

export function connectSocket(url: string) {
  currentUrl = url;
  manualClose = false;
  clearReconnect();

  if (socketTask && (currentStatus === "open" || currentStatus === "connecting")) {
    console.log("[Socket] 连接已存在，跳过重复连接");
    return;
  }

  console.log(`[Socket] 开始连接: ${url}`);
  updateStatus("connecting");

  const connectStart = Date.now();
  socketTask = uni.connectSocket({
    url,
    success: () => {
      console.log(`[Socket] connectSocket 成功 (耗时 ${Date.now() - connectStart}ms)`);
    },
    fail: (err) => {
      console.error(`[Socket] connectSocket 失败:`, JSON.stringify(err));
      updateStatus("error");
    },
  });

  bindSocketEvents(socketTask);
}

export function disconnectSocket() {
  manualClose = true;
  clearHeartbeat();
  clearReconnect();

  if (socketTask) {
    socketTask.close({});
    socketTask = null;
  }

  updateStatus("closed");
}

export function sendMessage(action: string, payload: Record<string, unknown> = {}) {
  if (!socketTask || currentStatus !== "open") {
    console.warn(`[Socket] 发送失败: 状态=${currentStatus}, action=${action}`);
    return false;
  }

  console.log(`[Socket] 发送: ${action}`, payload);
  socketTask.send({
    data: JSON.stringify({
      action,
      payload,
    }),
  });

  return true;
}

export function onSocketMessage(handler: MessageHandler) {
  messageHandlers.add(handler);
}

export function onSocketStatusChange(handler: StatusHandler) {
  statusHandlers.add(handler);
  handler(currentStatus);
}
