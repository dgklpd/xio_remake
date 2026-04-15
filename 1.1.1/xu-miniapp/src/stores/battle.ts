import { defineStore } from "pinia";
import type { BattleCardModel, EquipmentModel } from "@/types/match";
import {
  connectSocket,
  disconnectSocket,
  onSocketMessage,
  onSocketStatusChange,
  sendMessage,
  type SocketConnectionStatus,
  type SocketIncomingMessage,
} from "@/utils/socket";

export interface ServerEquipmentState {
  id: string;
  name: string;
  phase: string;
  theme?: EquipmentModel["theme"];
}

export interface ServerCardMeta {
  name: string;
  kind: BattleCardModel["kind"];
  subtitle: string;
  cost_label: string;
  attack_label: string;
  defense_label: string;
  special_text: string;
  keywords: string[];
  theme: BattleCardModel["theme"];
}

export interface ServerPlayerState {
  energy: number;
  equipment: ServerEquipmentState[] | null;
  status: string;
  hp: number;
  statuses?: string[];
  score?: number;
}

export interface ServerRoundResolution {
  my_card_status?: string | null;
  enemy_card_status?: string | null;
  my_status?: string | null;
  enemy_status?: string | null;
  winner?: "self" | "enemy" | "draw" | null;
  logs?: string[];
  granted_equipment?: string | null;
  [key: string]: unknown;
}

export interface ServerBattlefieldState {
  my_card_played: string | null;
  enemy_card_played: string | null;
  my_card_ready: boolean;
  enemy_card_ready: boolean;
  reveal_cards: boolean;
  resolution: ServerRoundResolution | null;
}

export interface ServerTimerState {
  round_seconds: number;
  deadline_ts: number | null;
}

export interface ServerGameState {
  round: number;
  my_state: ServerPlayerState;
  enemy_state: ServerPlayerState;
  hand_cards: string[];
  battlefield: ServerBattlefieldState;
  timer: ServerTimerState;
  card_catalog?: Record<string, ServerCardMeta>;
  scores?: {
    my: number;
    enemy: number;
  };
}

interface PendingActionState {
  action: string;
  payload: Record<string, unknown>;
}

interface BattleStoreState {
  socketUrl: string;
  socketStatus: SocketConnectionStatus;
  initialized: boolean;
  lastEventAction: string;
  lastError: string;
  pendingAction: PendingActionState | null;
  gameState: ServerGameState;
}

const fallbackCatalog: Record<string, ServerCardMeta> = {
  xu: {
    name: "蓄",
    kind: "蓄",
    subtitle: "基础局",
    cost_label: "0",
    attack_label: "-",
    defense_label: "0",
    special_text: "积蓄 1 点蓄能量。",
    keywords: ["能量增长"],
    theme: "gold",
  },
  di_bo: {
    name: "地波",
    kind: "技",
    subtitle: "基础局",
    cost_label: "0",
    attack_label: "-",
    defense_label: "0",
    special_text: "获得遁地。",
    keywords: ["遁地"],
    theme: "paper",
  },
  tian_bo: {
    name: "天波",
    kind: "技",
    subtitle: "基础局",
    cost_label: "0",
    attack_label: "-",
    defense_label: "0",
    special_text: "获得飞天。",
    keywords: ["飞天"],
    theme: "azure",
  },
  bo_bo: {
    name: "波波",
    kind: "攻",
    subtitle: "基础局",
    cost_label: "1",
    attack_label: "2",
    defense_label: "2",
    special_text: "基础攻击牌。",
    keywords: ["攻防一体"],
    theme: "azure",
  },
  lei_ba: {
    name: "雷八",
    kind: "攻",
    subtitle: "基础局",
    cost_label: "1/3",
    attack_label: "1",
    defense_label: "1",
    special_text: "快速点杀攻击。",
    keywords: ["点杀"],
    theme: "storm",
  },
  chao_fang: {
    name: "超防",
    kind: "守",
    subtitle: "基础局",
    cost_label: "1",
    attack_label: "-",
    defense_label: "4.5",
    special_text: "高防御守牌。",
    keywords: ["高防"],
    theme: "paper",
  },
  san_kan: {
    name: "三砍",
    kind: "攻",
    subtitle: "基础局",
    cost_label: "3",
    attack_label: "3",
    defense_label: "3",
    special_text: "破免攻击。",
    keywords: ["破免"],
    theme: "crimson",
  },
  wu_he_ti: {
    name: "五合体",
    kind: "攻",
    subtitle: "基础局",
    cost_label: "5",
    attack_label: "4",
    defense_label: "4",
    special_text: "高费重击。",
    keywords: ["爆发"],
    theme: "gold",
  },
  hu_he_ti: {
    name: "虎合体",
    kind: "攻",
    subtitle: "基础局",
    cost_label: "10",
    attack_label: "5",
    defense_label: "5",
    special_text: "终结大招。",
    keywords: ["终结"],
    theme: "crimson",
  },
};

function createEmptyGameState(): ServerGameState {
  return {
    round: 1,
    my_state: {
      energy: 0,
      equipment: [],
      status: "normal",
      hp: 1,
      statuses: [],
      score: 0,
    },
    enemy_state: {
      energy: 0,
      equipment: [],
      status: "normal",
      hp: 1,
      statuses: [],
      score: 0,
    },
    hand_cards: [],
    battlefield: {
      my_card_played: null,
      enemy_card_played: null,
      my_card_ready: false,
      enemy_card_ready: false,
      reveal_cards: false,
      resolution: null,
    },
    timer: {
      round_seconds: 10,
      deadline_ts: null,
    },
    card_catalog: {},
    scores: {
      my: 0,
      enemy: 0,
    },
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isServerGameState(value: unknown): value is ServerGameState {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.round === "number" &&
    isRecord(value.my_state) &&
    isRecord(value.enemy_state) &&
    Array.isArray(value.hand_cards) &&
    isRecord(value.battlefield) &&
    isRecord(value.timer)
  );
}

function extractGameState(message: SocketIncomingMessage): ServerGameState | null {
  if (isServerGameState(message.state)) {
    return message.state;
  }

  if (isServerGameState(message.payload)) {
    return message.payload;
  }

  if (isServerGameState(message)) {
    return message;
  }

  return null;
}

function extractErrorMessage(payload: unknown) {
  if (isRecord(payload) && typeof payload.message === "string") {
    return payload.message;
  }
  return "";
}

function toCostValue(costLabel: string) {
  if (costLabel.includes("/")) {
    const [left, right] = costLabel.split("/");
    const numerator = Number(left);
    const denominator = Number(right);
    if (!Number.isNaN(numerator) && !Number.isNaN(denominator) && denominator !== 0) {
      return numerator / denominator;
    }
  }

  const parsed = Number(costLabel);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function formatNumericLabel(rawLabel: string, fallback = "?") {
  const label = String(rawLabel ?? "").trim();
  if (!label || label === "-" || label === "?") {
    return label || fallback;
  }

  const parsed = toCostValue(label);
  if (Number.isNaN(parsed)) {
    return label;
  }

  if (Math.abs(parsed - Math.round(parsed)) < 0.001) {
    return String(Math.round(parsed));
  }

  return parsed.toFixed(1).replace(/\.0$/, "");
}

const BASE_CARD_NAMES = new Set(["蓄", "地波", "天波", "波波", "雷八", "超防", "三砍", "五合体", "虎合体"]);
const PEGASUS_SERIES_NAMES = new Set(["天马", "天马流星拳", "天马彗星拳", "天马后空翻"]);
const FROST_SERIES_NAMES = new Set(["冰盾", "爆冰", "爆冰拳", "凝冰", "晶冰拳", "冰狼拳"]);
const DRAGON_SERIES_NAMES = new Set(["龙盾", "爆龙", "爆龙拳", "金龙拳", "金狼拳"]);
const IMMUNE_SERIES_NAMES = new Set(["免疫", "小免", "大免", "挪移"]);
const JUSTICE_SERIES_NAMES = new Set(["正义", "反射镜", "穿心镜", "卡兹拳", "卡兹光", "卡兹膜"]);
const GUARDIAN_SERIES_NAMES = new Set(["牛盾", "顶", "锁链*1", "小盾"]);
const WOLF_SERIES_NAMES = new Set(["狼拳", "冰狼拳", "金狼拳"]);

function resolveCardTheme(name: string, fallbackTheme: BattleCardModel["theme"]): BattleCardModel["theme"] {
  if (name.startsWith("超率")) return "super";
  if (BASE_CARD_NAMES.has(name)) return "base";
  if (PEGASUS_SERIES_NAMES.has(name)) return "pegasus";
  if (FROST_SERIES_NAMES.has(name)) return "frost";
  if (DRAGON_SERIES_NAMES.has(name)) return "dragon";
  if (IMMUNE_SERIES_NAMES.has(name)) return "immune";
  if (JUSTICE_SERIES_NAMES.has(name)) return "justice";
  if (GUARDIAN_SERIES_NAMES.has(name)) return "guardian";
  if (WOLF_SERIES_NAMES.has(name)) return "wolf";
  return fallbackTheme;
}

function resolveCardSortRank(name: string) {
  if (name.startsWith("超率")) return 90;
  if (BASE_CARD_NAMES.has(name)) return 0;
  if (PEGASUS_SERIES_NAMES.has(name)) return 10;
  if (FROST_SERIES_NAMES.has(name)) return 20;
  if (DRAGON_SERIES_NAMES.has(name)) return 30;
  if (IMMUNE_SERIES_NAMES.has(name)) return 40;
  if (JUSTICE_SERIES_NAMES.has(name)) return 50;
  if (GUARDIAN_SERIES_NAMES.has(name)) return 60;
  if (WOLF_SERIES_NAMES.has(name)) return 70;
  return 80;
}

function toStatValue(label: string) {
  const parsed = Number(label);
  return Number.isNaN(parsed) ? null : parsed;
}

function mapEquipment(equipment: ServerEquipmentState[] | null): EquipmentModel[] {
  if (!equipment?.length) {
    return [];
  }

  return equipment.map((item) => ({
    id: item.id,
    name: item.name,
    phase: item.phase,
    skill: "",
    tag: "",
    theme: item.theme ?? "solar",
  }));
}

function buildFallbackCard(cardId: string): BattleCardModel {
  return {
    id: cardId,
    ownerId: "self",
    zone: "hand",
    isCrushed: false,
    templateId: cardId,
    name: cardId,
    kind: "技",
    subtitle: "未知卡牌",
    costLabel: "?",
    costValue: 0,
    attackValue: null,
    defenseValue: null,
    attackLabel: "-",
    defenseLabel: "-",
    keywords: [],
    specialText: "等待服务端同步详细信息。",
    theme: "paper",
  };
}

function mapCard(
  cardId: string,
  ownerId: "self" | "opponent",
  zone: "hand" | "field",
  catalog?: Record<string, ServerCardMeta>,
): BattleCardModel {
  const meta = catalog?.[cardId] ?? fallbackCatalog[cardId];
  if (!meta) {
    return {
      ...buildFallbackCard(cardId),
      ownerId,
      zone,
    };
  }

  return {
    id: cardId,
    ownerId,
    zone,
    isCrushed: false,
    templateId: cardId,
    name: meta.name,
    kind: meta.kind,
    subtitle: meta.subtitle,
    costLabel: formatNumericLabel(meta.cost_label),
    costValue: toCostValue(meta.cost_label),
    attackValue: meta.attack_label === "-" ? null : toStatValue(meta.attack_label),
    defenseValue: meta.defense_label === "-" ? null : toStatValue(meta.defense_label),
    attackLabel: formatNumericLabel(meta.attack_label, "-"),
    defenseLabel: formatNumericLabel(meta.defense_label, "-"),
    keywords: meta.keywords,
    specialText: meta.special_text,
    theme: resolveCardTheme(meta.name, meta.theme),
  };
}

export const useBattleStore = defineStore("battle", {
  state: (): BattleStoreState => ({
    socketUrl: "",
    socketStatus: "idle",
    initialized: false,
    lastEventAction: "",
    lastError: "",
    pendingAction: null,
    gameState: createEmptyGameState(),
  }),

  getters: {
    smallRound: (state) => state.gameState.round,

    phaseLabel: (state) => {
      if (state.socketStatus === "idle" || state.socketStatus === "closed" || state.socketStatus === "error") {
        return "未连接";
      }
      if (state.socketStatus === "connecting" || state.socketStatus === "reconnecting") {
        return "正在连接";
      }
      if (state.gameState.battlefield.reveal_cards) {
        return "翻牌结算";
      }
      if (state.gameState.battlefield.my_card_ready && state.gameState.battlefield.enemy_card_ready) {
        return "双方已出牌";
      }
      if (state.gameState.battlefield.my_card_ready || state.gameState.battlefield.enemy_card_ready) {
        return "等待对方";
      }
      return "出牌阶段";
    },

    selfPlayer: (state) => ({
      id: "self" as const,
      name: "我方",
      energy: state.gameState.my_state.energy,
      isDead: state.gameState.my_state.status === "dead" || state.gameState.my_state.hp <= 0,
      equipments: mapEquipment(state.gameState.my_state.equipment),
      hand: state.gameState.hand_cards.map((cardId) => {
        const card = mapCard(cardId, "self", "hand", state.gameState.card_catalog);
        const isCrushed =
          state.gameState.battlefield.resolution?.my_card_status === "crushed" &&
          state.gameState.battlefield.my_card_played === cardId;
        return { ...card, isCrushed };
      }),
      fieldCard: state.gameState.battlefield.my_card_played
        ? {
            ...mapCard(
              state.gameState.battlefield.my_card_played,
              "self",
              "field",
              state.gameState.card_catalog,
            ),
            isCrushed: state.gameState.battlefield.resolution?.my_card_status === "crushed",
          }
        : null,
    }),

    opponentPlayer: (state) => ({
      id: "opponent" as const,
      name: "人机",
      energy: state.gameState.enemy_state.energy,
      isDead: state.gameState.enemy_state.status === "dead" || state.gameState.enemy_state.hp <= 0,
      equipments: mapEquipment(state.gameState.enemy_state.equipment),
      hand: [] as BattleCardModel[],
      fieldCard: state.gameState.battlefield.enemy_card_played
        ? {
            ...mapCard(
              state.gameState.battlefield.enemy_card_played,
              "opponent",
              "field",
              state.gameState.card_catalog,
            ),
            isCrushed: state.gameState.battlefield.resolution?.enemy_card_status === "crushed",
          }
        : null,
    }),

    countdownDeadline: (state) => state.gameState.timer.deadline_ts,
    countdownSeconds: (state) => state.gameState.timer.round_seconds,
    myReady: (state) => state.gameState.battlefield.my_card_ready,
    enemyReady: (state) => state.gameState.battlefield.enemy_card_ready,
    revealCards: (state) => state.gameState.battlefield.reveal_cards,
    resolution: (state) => state.gameState.battlefield.resolution,
  },

  actions: {
    initializeSocket(url: string) {
      this.socketUrl = url;

      if (!this.initialized) {
        onSocketStatusChange((status) => {
          this.socketStatus = status;
        });

        onSocketMessage((message) => {
          this.handleServerMessage(message);
        });

        this.initialized = true;
      }

      connectSocket(url);
    },

    disconnect() {
      disconnectSocket();
      this.pendingAction = null;
    },

    applyGameState(gameState: ServerGameState) {
      this.gameState = {
        ...createEmptyGameState(),
        ...gameState,
      };
    },

    handleServerMessage(message: SocketIncomingMessage) {
      this.lastEventAction = typeof message.action === "string" ? message.action : "";
      const nextState = extractGameState(message);

      if (message.action === "pong") {
        return;
      }

      if (message.action === "error") {
        this.lastError = extractErrorMessage(message.payload) || "服务端返回了错误信息";
        this.pendingAction = null;
        uni.showToast({
          title: this.lastError,
          icon: "none",
        });
        return;
      }

      if (nextState) {
        this.applyGameState(nextState);
        this.pendingAction = null;
        this.lastError = "";
      }
    },

    sendPlayerAction(action: string, payload: Record<string, unknown> = {}) {
      const ok = sendMessage(action, payload);

      if (!ok) {
        this.lastError = "Socket 未连接，消息发送失败";
        uni.showToast({
          title: "连接未就绪",
          icon: "none",
        });
        return false;
      }

      this.pendingAction = {
        action,
        payload,
      };
      this.lastError = "";
      return true;
    },

    playCard(cardId: string) {
      return this.sendPlayerAction("play_card", {
        card_id: cardId,
      });
    },

    restartMatch() {
      return this.sendPlayerAction("restart_match");
    },
  },
});
