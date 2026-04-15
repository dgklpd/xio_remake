export interface OnlineIdentityPayload {
  display_name: string;
  avatar_url?: string;
  auth_provider?: "guest" | "wechat";
  external_user_id?: string | null;
  is_guest?: boolean;
}

export interface OnlineRoomSeatSummary {
  seat: "host" | "guest";
  user_id: string | null;
  display_name: string;
  avatar_url: string;
  connected: boolean;
  ready: boolean;
}

export interface OnlineRoomState {
  room_code: string;
  room_name: string;
  status: "waiting" | "full" | "playing" | "finished" | "closed";
  created_at: number;
  updated_at: number;
  expires_at: number;
  host: OnlineRoomSeatSummary;
  guest: OnlineRoomSeatSummary | null;
  can_start: boolean;
}

export interface OnlineRoomListItem {
  room_code: string;
  room_name: string;
  status: "waiting" | "full" | "playing" | "finished" | "closed";
  created_at: number;
  updated_at: number;
  expires_at: number;
  host_display_name: string;
  guest_display_name: string | null;
  host_connected: boolean;
  guest_connected: boolean;
  host_ready: boolean;
  guest_ready: boolean;
}

export interface CreateRoomResponse {
  seat: "host" | "guest";
  session_token: string;
  room: OnlineRoomState;
}

export interface JoinRoomResponse {
  seat: "host" | "guest";
  session_token: string;
  room: OnlineRoomState;
}

export interface ReadyOnlineRoomResponse {
  room: OnlineRoomState;
}

export interface LeaveOnlineRoomResponse {
  closed: boolean;
  room: OnlineRoomState | null;
}

const ONLINE_API_BASE_URL_STORAGE_KEY = "xio_online_api_base_url";
const ONLINE_SESSION_STORAGE_KEY = "xio_online_session";
const GUEST_IDENTITY_STORAGE_KEY = "xio_guest_identity";
const DEFAULT_API_BASE_URL = "https://efxlzhrnfjci.sealoshzh.site";

export function getOnlineApiBaseUrl() {
  const saved = uni.getStorageSync(ONLINE_API_BASE_URL_STORAGE_KEY);
  return typeof saved === "string" && saved.trim() ? saved.trim().replace(/\/$/, "") : DEFAULT_API_BASE_URL;
}

function request<T>(options: UniApp.RequestOptions) {
  return new Promise<T>((resolve, reject) => {
    uni.request({
      ...options,
      success: (response) => {
        const statusCode = response.statusCode ?? 500;
        if (statusCode >= 200 && statusCode < 300) {
          resolve(response.data as T);
          return;
        }

        const detail =
          typeof response.data === "object" &&
          response.data !== null &&
          "detail" in (response.data as Record<string, unknown>)
            ? String((response.data as Record<string, unknown>).detail)
            : `请求失败(${statusCode})`;

        reject(new Error(detail));
      },
      fail: (error) => {
        reject(new Error(error.errMsg || "网络请求失败"));
      },
    });
  });
}

export async function listOnlineRooms(limit = 60) {
  const baseUrl = getOnlineApiBaseUrl();
  const response = await request<{ rooms: OnlineRoomListItem[] }>({
    url: `${baseUrl}/online/rooms?limit=${limit}`,
    method: "GET",
  });
  return response.rooms;
}

export async function createOnlineRoom(payload: {
  roomName?: string;
  identity: OnlineIdentityPayload;
}) {
  const baseUrl = getOnlineApiBaseUrl();
  const response = await request<CreateRoomResponse>({
    url: `${baseUrl}/online/rooms`,
    method: "POST",
    data: {
      room_name: payload.roomName,
      identity: payload.identity,
    },
  });
  persistOnlineSession({
    room_code: response.room.room_code,
    room_name: response.room.room_name,
    seat: response.seat,
    session_token: response.session_token,
    identity: payload.identity,
  });
  return response;
}

export async function joinOnlineRoom(roomCode: string, payload: { identity: OnlineIdentityPayload }) {
  const baseUrl = getOnlineApiBaseUrl();
  const response = await request<JoinRoomResponse>({
    url: `${baseUrl}/online/rooms/${roomCode}/join`,
    method: "POST",
    data: {
      identity: payload.identity,
    },
  });
  persistOnlineSession({
    room_code: response.room.room_code,
    room_name: response.room.room_name,
    seat: response.seat,
    session_token: response.session_token,
    identity: payload.identity,
  });
  return response;
}

export async function getOnlineRoom(roomCode: string) {
  const baseUrl = getOnlineApiBaseUrl();
  const response = await request<{ room: OnlineRoomState }>({
    url: `${baseUrl}/online/rooms/${roomCode}`,
    method: "GET",
  });
  return response.room;
}

export async function setOnlineRoomReady(roomCode: string, payload: { seat: "host" | "guest"; ready: boolean }) {
  const baseUrl = getOnlineApiBaseUrl();
  return request<ReadyOnlineRoomResponse>({
    url: `${baseUrl}/online/rooms/${roomCode}/ready`,
    method: "POST",
    data: payload,
  });
}

export async function leaveOnlineRoom(roomCode: string, payload: { seat: "host" | "guest" }) {
  const baseUrl = getOnlineApiBaseUrl();
  return request<LeaveOnlineRoomResponse>({
    url: `${baseUrl}/online/rooms/${roomCode}/leave`,
    method: "POST",
    data: payload,
  });
}

export function persistOnlineSession(payload: Record<string, unknown>) {
  uni.setStorageSync(ONLINE_SESSION_STORAGE_KEY, payload);
}

export function getSavedOnlineSession<T extends Record<string, unknown>>() {
  return uni.getStorageSync(ONLINE_SESSION_STORAGE_KEY) as T | "";
}

export function clearSavedOnlineSession() {
  uni.removeStorageSync(ONLINE_SESSION_STORAGE_KEY);
}

export function buildOnlineRoomSocketUrl(roomCode: string, seat: "host" | "guest", sessionToken: string) {
  const baseUrl = getOnlineApiBaseUrl();
  const wsBase = baseUrl.replace(/^http:\/\//i, "ws://").replace(/^https:\/\//i, "wss://");
  return `${wsBase}/ws/online/rooms/${encodeURIComponent(roomCode)}?seat=${seat}&session_token=${encodeURIComponent(sessionToken)}`;
}

function generateGuestId() {
  return `guest_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
}

export function getOrCreateGuestIdentity(preferredName?: string): OnlineIdentityPayload & {
  external_user_id: string;
} {
  const saved = uni.getStorageSync(GUEST_IDENTITY_STORAGE_KEY) as Record<string, unknown> | "";
  const savedId = saved && typeof saved === "object" ? String(saved.external_user_id || "") : "";
  const savedName = saved && typeof saved === "object" ? String(saved.display_name || "") : "";
  const displayName = preferredName?.trim() || savedName || `玩家${Math.floor(Math.random() * 9000 + 1000)}`;
  const externalId = savedId || generateGuestId();

  const identity = {
    display_name: displayName,
    avatar_url: "",
    auth_provider: "guest" as const,
    external_user_id: externalId,
    is_guest: true,
  };
  uni.setStorageSync(GUEST_IDENTITY_STORAGE_KEY, identity);
  return identity;
}
