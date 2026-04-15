export type BattleSide = "self" | "opponent";
export type CardKind = "蓄" | "守" | "攻" | "技";
export type CardTheme =
  | "gold"
  | "paper"
  | "azure"
  | "storm"
  | "crimson"
  | "base"
  | "pegasus"
  | "frost"
  | "dragon"
  | "immune"
  | "justice"
  | "guardian"
  | "wolf"
  | "super";
export type EquipmentTheme = "solar" | "frost" | "jade";
export type CardZone = "hand" | "field";
export type RoundStatus = "awaiting_play" | "resolved" | "small_round_end";

export interface BattleCardTemplate {
  templateId: string;
  name: string;
  kind: CardKind;
  subtitle: string;
  costLabel: string;
  costValue: number;
  attackValue: number | null;
  defenseValue: number | null;
  attackLabel: string;
  defenseLabel: string;
  keywords: string[];
  specialText: string;
  theme: CardTheme;
}

export interface BattleCardModel extends BattleCardTemplate {
  id: string;
  ownerId: BattleSide;
  zone: CardZone;
  isCrushed: boolean;
}

export interface EquipmentModel {
  id: string;
  name: string;
  phase: string;
  skill: string;
  tag: string;
  theme: EquipmentTheme;
}

export interface BattlePlayerState {
  id: BattleSide;
  name: string;
  energy: number;
  isDead: boolean;
  equipments: EquipmentModel[];
  hand: BattleCardModel[];
  fieldCard: BattleCardModel | null;
}

export interface RoundResolution {
  selfCrushed: boolean;
  opponentCrushed: boolean;
  selfDead: boolean;
  opponentDead: boolean;
}

export interface BattleState {
  smallRound: number;
  turn: number;
  phaseLabel: string;
  actionHint: string;
  roundStatus: RoundStatus;
  resolution: RoundResolution;
  players: Record<BattleSide, BattlePlayerState>;
}
