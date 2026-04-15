export type CardKind = "攻" | "守" | "技";
export type CardState = "idle" | "charged" | "locked";
export type BattlePhase = "prepare" | "clash" | "resolve";

export interface BattleCardPreview {
  id: string;
  name: string;
  kind: CardKind;
  cost: number;
  attack?: number;
  defense?: number;
  effect: string;
  accent: string;
  state: CardState;
}

export interface BattlePlayerPreview {
  id: string;
  name: string;
  hp: number;
  maxHp: number;
  energy: number;
  maxEnergy: number;
  deckCount: number;
  rateUnlocked: boolean;
  statusLabel: string;
}

export interface ActionButtonPreview {
  key: string;
  label: string;
  cost?: number;
  disabled?: boolean;
  highlight?: boolean;
}
