from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import (
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
)


Energy = Fraction


# 将输入值转化为分数形式的能量值（Energy）
def F(value: int | float | str) -> Energy:
    return Fraction(str(value))


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    attack: Energy = F(0)
    defense: Energy = F(0)
    energy_cost: Energy = F(0)
    alt_cost: Mapping[str, int] = field(default_factory=dict)
    specials: Tuple[str, ...] = field(default_factory=tuple)
    deteriorate_ground: bool = False
    deteriorate_air: bool = False
    tags: frozenset[str] = field(default_factory=frozenset)
    desc: str = ""


@dataclass
class EquipmentState:
    phase: int = 0


@dataclass
class PlayerState:
    player_id: int
    team_id: int
    alive: bool = True
    energy: Energy = F(0)
    equipments: Dict[str, EquipmentState] = field(default_factory=dict)
    welfare: Set[str] = field(default_factory=set)
    smashed_skills: Set[str] = field(default_factory=set)
    charge_bonus: int = 0
    counters: Dict[str, int] = field(
        default_factory=lambda: {
            "bao_bing": 0,
            "bao_long": 0,
            "jing_bing": 0,
        }
    )
    statuses: Set[str] = field(default_factory=set)

    # 针对每个小局进行状态重置：恢复存活状态、清空能量和被粉碎技能、清空累积加成状态
    def small_round_reset(self) -> None:
        self.alive = True
        self.energy = F(0)
        self.smashed_skills.clear()
        self.statuses.clear()
        self.counters = {"bao_bing": 0, "bao_long": 0, "jing_bing": 0}

    # 针对每一个基本回合进行状态重置：移除各种单回合状态（例如飞天、遁地）
    def round_reset(self) -> None:
        self.statuses.clear()


@dataclass(frozen=True)
class EquipmentBlueprint:
    name: str
    max_phase: int
    phase_skills: Mapping[int, Tuple[str, ...]]
    combo_rules: Tuple["ComboBlueprint", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComboBlueprint:
    skill_name: str
    require_equipment: Mapping[str, int]


@dataclass
class TurnState:
    player: PlayerState
    skill: Skill
    skill_name: str
    effective_attack: Energy
    effective_defense: Energy
    invalidated: bool = False


@dataclass
class RoundResult:
    actions: Dict[int, str]
    logs: List[str] = field(default_factory=list)
    dead_players: Set[int] = field(default_factory=set)
    smashed_this_round: Dict[int, Set[str]] = field(default_factory=dict)
    draw_restart: bool = False


SKILLS: Dict[str, Skill] = {
    "蓄": Skill(
        "蓄",
        "special",
        defense=F(0),
        specials=("charge",),
        desc="本回合积蓄 1 点能量，受锁链加成",
    ),
    "地波": Skill(
        "地波",
        "special",
        defense=F(0),
        specials=("dive",),
        desc="获得遁地，免疫劣化对地攻击",
    ),
    "天波": Skill(
        "天波",
        "special",
        defense=F(0),
        specials=("fly",),
        desc="获得飞天，免疫劣化对空攻击",
    ),
    "波波": Skill(
        "波波",
        "attack",
        attack=F(2),
        defense=F(2),
        energy_cost=F(1),
        deteriorate_ground=True,
        deteriorate_air=True,
    ),
    "雷八": Skill(
        "雷八",
        "attack",
        attack=F(1),
        defense=F(1),
        energy_cost=F("1/3"),
        deteriorate_ground=True,
        specials=("lei_ba",),
    ),
    "超防": Skill("超防", "defense", defense=F("4.5"), energy_cost=F(1)),
    "三砍": Skill(
        "三砍",
        "attack",
        attack=F(3),
        defense=F(3),
        energy_cost=F(3),
        specials=("smash_mian_yi",),
    ),
    "五合体": Skill("五合体", "attack", attack=F(4), defense=F(4), energy_cost=F(5)),
    "虎合体": Skill("虎合体", "attack", attack=F(5), defense=F(5), energy_cost=F(10)),
    "超率": Skill(
        "超率",
        "defense",
        defense=Fraction(10**9, 1),
        energy_cost=F(3),
        specials=("super_rate",),
    ),
    "天马": Skill(
        "天马",
        "attack",
        attack=F("2.5"),
        defense=F("2.5"),
        energy_cost=F("1/3"),
        deteriorate_ground=True,
    ),
    "天马流星拳": Skill(
        "天马流星拳",
        "attack",
        attack=F(3),
        defense=F(3),
        energy_cost=F(1),
        deteriorate_air=True,
    ),
    "天马彗星拳": Skill(
        "天马彗星拳",
        "attack",
        attack=F(3),
        defense=F(3),
        energy_cost=F(1),
        deteriorate_air=True,
    ),
    "天马后空翻": Skill(
        "天马后空翻", "defense", defense=F(5), specials=("killed_by_lei_ba",)
    ),
    "冰盾": Skill("冰盾", "defense", defense=F("2.5")),
    "爆冰": Skill("爆冰", "defense", defense=F("3.5"), specials=("add_bao_bing",)),
    "爆冰拳": Skill(
        "爆冰拳",
        "attack",
        attack=F(3),
        defense=F(3),
        energy_cost=F(1),
        alt_cost={"bao_bing": 3},
        deteriorate_ground=True,
    ),
    "凝冰": Skill(
        "凝冰",
        "defense",
        defense=F("4.5"),
        energy_cost=F("1/6"),
        specials=("add_jing_bing",),
        tags=frozenset({"ning_bing"}),
    ),
    "晶冰拳": Skill(
        "晶冰拳",
        "attack",
        attack=F("3.5"),
        defense=F("3.5"),
        energy_cost=F(1),
        alt_cost={"jing_bing": 3},
        deteriorate_air=True,
    ),
    "龙盾": Skill("龙盾", "defense", defense=F("2.5")),
    "爆龙": Skill("爆龙", "defense", defense=F("3.5"), specials=("add_bao_long",)),
    "爆龙拳": Skill(
        "爆龙拳",
        "attack",
        attack=F(3),
        defense=F(3),
        energy_cost=F(1),
        alt_cost={"bao_long": 3},
        deteriorate_ground=True,
    ),
    "金龙拳": Skill(
        "金龙拳",
        "attack",
        attack=F("4.5"),
        defense=F("4.5"),
        deteriorate_air=True,
        specials=("smash_ning_bing",),
    ),
    "免疫": Skill("免疫", "defense", defense=F(3), tags=frozenset({"mian_yi"})),
    "小免": Skill("小免", "defense", defense=F(3), specials=("smash_shield",)),
    "大免": Skill(
        "大免",
        "defense",
        defense=F(4),
        specials=("smash_weak_attack", "killed_by_lei_ba"),
    ),
    "挪移": Skill(
        "挪移",
        "defense",
        defense=F(5),
        energy_cost=F("1/3"),
        specials=("smash_strong_attack",),
    ),
    "正义": Skill(
        "正义",
        "attack",
        attack=F(3),
        defense=F(3),
        deteriorate_air=True,
        specials=("killed_by_lei_ba",),
    ),
    "反射镜": Skill(
        "反射镜", "defense", defense=F(3), specials=("reflect_lt3", "killed_by_lei_ba")
    ),
    "穿心镜": Skill(
        "穿心镜",
        "attack",
        attack=F("3.5"),
        defense=F("3.5"),
        specials=("killed_by_lei_ba",),
    ),
    "卡兹拳": Skill(
        "卡兹拳", "attack", attack=F(4), defense=F(4), specials=("killed_by_lei_ba",)
    ),
    "卡兹光": Skill(
        "卡兹光", "defense", defense=F(5), specials=("reflect_le45", "killed_by_lei_ba")
    ),
    "卡兹膜": Skill("卡兹膜", "defense", defense=F(4), specials=("killed_by_lei_ba",)),
    "牛盾": Skill("牛盾", "defense", defense=F("4.5"), energy_cost=F("1/6")),
    "顶": Skill(
        "顶",
        "attack",
        attack=F(3),
        defense=F(3),
        energy_cost=F("1/3"),
        deteriorate_air=True,
    ),
    "狼拳": Skill(
        "狼拳",
        "attack",
        attack=F("2.5"),
        defense=F("2.5"),
        energy_cost=F("1/2"),
        deteriorate_ground=True,
        specials=("smash_nuo_yi",),
    ),
    "冰狼拳": Skill(
        "冰狼拳",
        "attack",
        attack=F("3.5"),
        defense=F("3.5"),
        energy_cost=F(1),
        alt_cost={"jing_bing": 3},
        deteriorate_air=True,
        specials=("smash_nuo_yi", "immune_da_mian_smash", "immune_nuo_yi_smash"),
    ),
    "金狼拳": Skill(
        "金狼拳",
        "attack",
        attack=F("4.5"),
        defense=F("4.5"),
        deteriorate_air=True,
        specials=(
            "smash_nuo_yi",
            "smash_ning_bing",
            "immune_da_mian_smash",
            "immune_nuo_yi_smash",
        ),
    ),
    "小盾": Skill("小盾", "defense", defense=F(0), specials=("immune_deteriorate",)),
}


EQUIPMENT_POOL: Tuple[str, ...] = (
    "天马",
    "冰盾",
    "龙盾",
    "免疫",
    "正义",
    "牛脖",
    "狼拳",
)


EQUIPMENT_BLUEPRINTS: Dict[str, EquipmentBlueprint] = {
    "天马": EquipmentBlueprint(
        "天马",
        8,
        {
            0: ("天马",),
            1: ("天马流星拳",),
            2: ("天马彗星拳",),
            3: ("天马后空翻",),
        },
    ),
    "冰盾": EquipmentBlueprint(
        "冰盾",
        3,
        {
            0: ("冰盾",),
            1: ("爆冰", "爆冰拳"),
            2: ("凝冰",),
            3: ("晶冰拳",),
        },
    ),
    "龙盾": EquipmentBlueprint(
        "龙盾",
        2,
        {
            0: ("龙盾",),
            1: ("爆龙", "爆龙拳"),
            2: ("金龙拳",),
        },
    ),
    "免疫": EquipmentBlueprint(
        "免疫",
        3,
        {
            0: ("免疫",),
            1: ("小免",),
            2: ("大免",),
            3: ("挪移",),
        },
    ),
    "正义": EquipmentBlueprint(
        "正义",
        16,
        {
            0: ("正义",),
            1: ("反射镜",),
            2: ("穿心镜",),
            3: ("卡兹拳",),
            4: ("卡兹光",),
            5: ("卡兹膜",),
        },
    ),
    "牛脖": EquipmentBlueprint("牛脖", 0, {0: ("牛盾", "顶")}),
    "狼拳": EquipmentBlueprint(
        "狼拳",
        0,
        {0: ("狼拳",)},
        combo_rules=(
            ComboBlueprint("冰狼拳", {"冰盾": 2}),
            ComboBlueprint("金狼拳", {"龙盾": 1}),
        ),
    ),
}


CHAIN_RULES: Dict[str, int] = {
    "天马": 0,
    "天马流星拳": 0,
    "天马彗星拳": 0,
    "天马后空翻": 0,
    "正义": 0,
    "反射镜": 0,
    "穿心镜": 0,
    "卡兹拳": 0,
    "卡兹光": 0,
    "卡兹膜": 0,
}


# 根据装备名称和所处成长阶段，计算所能提供的蓄能量连锁加成
def chain_bonus_for_equipment(name: str, phase: int) -> int:
    if name == "天马" and phase >= 4:
        return phase - 3
    if name == "正义" and phase >= 6:
        return phase - 5
    return 0


class RuleEngine:
    # 初始化规则引擎。配置每回合结算的预处理规则和反弹处理规则列表
    def __init__(self) -> None:
        self.pre_rules: Tuple[
            Callable[[Dict[int, TurnState], RoundResult], None], ...
        ] = (
            self._rule_smash_shield,
            self._rule_smash_weak_attack,
            self._rule_smash_strong_attack,
            self._rule_smash_ning_bing,
            self._rule_smash_mian_yi,
        )
        self.reflect_rules: Tuple[
            Callable[[Dict[int, TurnState], RoundResult], None], ...
        ] = (
            self._rule_reflect_lt3,
            self._rule_reflect_le45,
        )

    # 根据玩家当前状态、拥有的装备及其等级、低保状态，计算该玩家本回合可以使用的所有技能集合
    def available_skills(self, player: PlayerState) -> Dict[str, Skill]:
        skills = {
            name: SKILLS[name]
            for name in (
                "蓄",
                "地波",
                "天波",
                "波波",
                "雷八",
                "超防",
                "三砍",
                "五合体",
                "虎合体",
            )
        }
        for equip_name, equip_state in player.equipments.items():
            blueprint = EQUIPMENT_BLUEPRINTS[equip_name]
            for phase in range(equip_state.phase + 1):
                for skill_name in blueprint.phase_skills.get(phase, ()):
                    skills[skill_name] = SKILLS[skill_name]
            for combo in blueprint.combo_rules:
                if all(
                    req in player.equipments and player.equipments[req].phase >= need
                    for req, need in combo.require_equipment.items()
                ):
                    skills[combo.skill_name] = SKILLS[combo.skill_name]
        if "锁链*1" in player.welfare:
            pass
        if "小盾" in player.welfare:
            skills["小盾"] = SKILLS["小盾"]
        return {
            name: skill
            for name, skill in skills.items()
            if name not in player.smashed_skills
        }

    # 获取当前玩家可以进行"超率"（即升级操作）的装备候选列表
    def super_rate_candidates(self, player: PlayerState) -> List[str]:
        candidates: List[str] = []
        for equip_name, equip_state in player.equipments.items():
            blueprint = EQUIPMENT_BLUEPRINTS[equip_name]
            if equip_name == "狼拳":
                if any(
                    all(
                        req in player.equipments
                        and player.equipments[req].phase >= need
                        for req, need in combo.require_equipment.items()
                    )
                    for combo in blueprint.combo_rules
                ):
                    candidates.append(equip_name)
            elif equip_state.phase < blueprint.max_phase:
                candidates.append(equip_name)
        return candidates

    # 对指定的装备执行超级进化（超率），同时扣除所需能量，提升装备等级并刷新蓄能加成
    def apply_super_rate(self, player: PlayerState, equipment_name: str) -> None:
        if equipment_name not in self.super_rate_candidates(player):
            raise ValueError(f"{equipment_name} 当前不可超率")
        if player.energy < F(3):
            raise ValueError("超率至少需要 3 点蓄能量")
        player.energy -= F(3)
        player.equipments[equipment_name].phase += 1
        self._refresh_charge_bonus(player)

    # 核心的每回合对决结算系统：验证->扣费->前期状态->防御特判->无敌特判->反弹->雷八秒杀->通用攻防->结算死亡
    def resolve_round(
        self,
        players: Sequence[PlayerState],
        declared_actions: Mapping[int, str],
        *,
        first_round_of_small_game: bool = False,
    ) -> RoundResult:
        living = [player for player in players if player.alive]
        actions = self._normalize_actions(
            living, declared_actions, first_round_of_small_game
        )
        round_result = RoundResult(
            actions=dict(actions),
            smashed_this_round={player.player_id: set() for player in players},
        )
        turn_states = self._build_turn_states(living, actions)
        self._apply_self_effects(turn_states, round_result)
        for rule in self.pre_rules:
            rule(turn_states, round_result)
        self._apply_deterioration_immunity(turn_states, round_result)
        for rule in self.reflect_rules:
            rule(turn_states, round_result)
        self._apply_lei_ba_kill(turn_states, round_result)
        self._apply_core_combat(turn_states, round_result)
        self._finalize_deaths(players, round_result)
        if all(not player.alive for player in living):
            round_result.draw_restart = True
        for player in players:
            player.round_reset()
        return round_result

    # 按照公共装备池序列，给指定玩家发放下一个未被其他人获取的基础装备
    def grant_next_equipment(
        self, player: PlayerState, taken_equipment: Set[str]
    ) -> Optional[str]:
        for equip_name in EQUIPMENT_POOL:
            if equip_name not in taken_equipment:
                player.equipments[equip_name] = EquipmentState(phase=0)
                self._refresh_charge_bonus(player)
                if equip_name == "牛脖":
                    return equip_name
                return equip_name
        return None

    # 弱势补贴：当有人拥有牛脖装备且存在无装备玩家时，发放低保（锁链与小盾）
    def apply_welfare_if_needed(self, players: Sequence[PlayerState]) -> None:
        has_niu_bo = any("牛脖" in player.equipments for player in players)
        if not has_niu_bo:
            return
        for player in players:
            if player.equipments:
                continue
            player.welfare.update({"锁链*1", "小盾"})
            self._refresh_charge_bonus(player)

    # 校准和格式化动作。处理第一回合强制出“蓄”、分析特殊指令（如“超率”），完成行动扣费
    def _normalize_actions(
        self,
        living: Sequence[PlayerState],
        declared_actions: Mapping[int, str],
        first_round_of_small_game: bool,
    ) -> Dict[int, str]:
        actions: Dict[int, str] = {}
        for player in living:
            action_name = (
                "蓄"
                if first_round_of_small_game
                else declared_actions[player.player_id]
            )
            if action_name.startswith("超率"):
                equipment_name = self._parse_super_rate_action(action_name)
                self.apply_super_rate(player, equipment_name)
                actions[player.player_id] = "超率"
                continue
            available = self.available_skills(player)
            if action_name not in available:
                raise ValueError(f"玩家 {player.player_id} 不能使用技能 {action_name}")
            self._pay_cost(player, available[action_name])
            actions[player.player_id] = action_name
        return actions

    # 扣除技能释放所需的常规蓄能量或特殊代币能量（如爆冰）
    def _pay_cost(self, player: PlayerState, skill: Skill) -> None:
        if skill.alt_cost:
            for counter_name, need in skill.alt_cost.items():
                if player.counters[counter_name] >= need:
                    player.counters[counter_name] -= need
                    return
        if player.energy < skill.energy_cost:
            raise ValueError(f"玩家 {player.player_id} 的蓄能量不足以使用 {skill.name}")
        player.energy -= skill.energy_cost

    # 装配并初始化本回合需要结算的玩家 TurnState 状态数据包
    def _build_turn_states(
        self, living: Sequence[PlayerState], actions: Mapping[int, str]
    ) -> Dict[int, TurnState]:
        states: Dict[int, TurnState] = {}
        for player in living:
            skill_name = actions[player.player_id]
            skill = (
                SKILLS[skill_name]
                if skill_name == "超率"
                else self.available_skills(player)[skill_name]
            )
            states[player.player_id] = TurnState(
                player=player,
                skill=skill,
                skill_name=skill_name,
                effective_attack=skill.attack,
                effective_defense=skill.defense,
            )
        return states

    # 对超率动作字符串进行初步语义解析，提取其指向的实际装备名
    def _parse_super_rate_action(self, action_name: str) -> str:
        if action_name == "超率":
            raise ValueError("超率动作需要写成 `超率:装备名`")
        prefix, _, equipment_name = action_name.partition(":")
        if prefix != "超率" or not equipment_name:
            raise ValueError("超率动作格式错误，应为 `超率:装备名`")
        return equipment_name

    # 自增类独立效果结算（技能加蓄、飞天、遁地、层数积累等）
    def _apply_self_effects(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for state in states.values():
            player = state.player
            for special in state.skill.specials:
                if special == "charge":
                    gain = 1 + player.charge_bonus
                    player.energy += F(gain)
                    result.logs.append(f"玩家{player.player_id} 使用蓄，能量 +{gain}")
                elif special == "fly":
                    player.statuses.add("fly")
                elif special == "dive":
                    player.statuses.add("dive")
                elif special == "add_bao_bing":
                    player.counters["bao_bing"] += 1
                elif special == "add_bao_long":
                    player.counters["bao_long"] += 1
                elif special == "add_jing_bing":
                    player.counters["jing_bing"] += 1

    # 规则特判：小免技能破除特定的护盾（冰盾、龙盾）
    def _rule_smash_shield(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for source in states.values():
            if "smash_shield" not in source.skill.specials:
                continue
            for target in self._enemies_of(source.player, states):
                if target.skill_name in {"冰盾", "龙盾"}:
                    self._smash_skill(
                        target,
                        result,
                        f"玩家{source.player.player_id} 的小免粉碎了 玩家{target.player.player_id} 的 {target.skill_name}",
                    )

    # 规则特判：大免技能使大部分效能低于3点的弱攻击直接被粉碎失效（雷八除外）
    def _rule_smash_weak_attack(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for source in states.values():
            if "smash_weak_attack" not in source.skill.specials:
                continue
            for target in self._enemy_attackers_of(source.player, states):
                if target.skill_name == "雷八":
                    continue
                if "immune_da_mian_smash" in target.skill.specials:
                    continue
                if target.effective_attack < F(3):
                    self._smash_skill(
                        target,
                        result,
                        f"玩家{source.player.player_id} 的大免粉碎了 玩家{target.player.player_id} 的 {target.skill_name}",
                    )

    # 规则特判：挪移技能抵消并粉碎效能不超过4.5的攻击，并兼顾反制特性
    def _rule_smash_strong_attack(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for source in states.values():
            if "smash_strong_attack" not in source.skill.specials:
                continue
            for target in self._enemy_attackers_of(source.player, states):
                if "smash_nuo_yi" in target.skill.specials:
                    self._smash_skill(
                        source,
                        result,
                        f"玩家{target.player.player_id} 的 {target.skill_name} 反制并粉碎了 玩家{source.player.player_id} 的挪移",
                    )
                    continue
                if "immune_nuo_yi_smash" in target.skill.specials:
                    continue
                if target.effective_attack <= F("4.5"):
                    self._smash_skill(
                        target,
                        result,
                        f"玩家{source.player.player_id} 的挪移粉碎了 玩家{target.player.player_id} 的 {target.skill_name}",
                    )

    # 规则特判：附带破冰特效的技能针对性粉碎对方的“凝冰”状态
    def _rule_smash_ning_bing(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for source in states.values():
            if "smash_ning_bing" not in source.skill.specials:
                continue
            for target in self._enemies_of(source.player, states):
                if target.skill_name == "凝冰":
                    self._smash_skill(
                        target,
                        result,
                        f"玩家{source.player.player_id} 的 {source.skill_name} 粉碎了 玩家{target.player.player_id} 的 凝冰",
                    )

    # 规则特判：三砍可以直接无视并粉碎防御技“免疫”
    def _rule_smash_mian_yi(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for source in states.values():
            if "smash_mian_yi" not in source.skill.specials:
                continue
            for target in self._enemies_of(source.player, states):
                if target.skill_name == "免疫":
                    self._smash_skill(
                        target,
                        result,
                        f"玩家{source.player.player_id} 的三砍粉碎了 玩家{target.player.player_id} 的 免疫",
                    )

    # 处理“劣化环境防守”（遁地免对地，飞天免对空，小盾全免）
    def _apply_deterioration_immunity(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for attacker in states.values():
            if attacker.invalidated or attacker.skill.category != "attack":
                continue
            for defender in self._enemies_of(attacker.player, states):
                if defender.skill_name == "小盾" and (
                    attacker.skill.deteriorate_air or attacker.skill.deteriorate_ground
                ):
                    attacker.effective_attack = F(0)
                    result.logs.append(
                        f"玩家{defender.player.player_id} 的小盾免疫了 玩家{attacker.player.player_id} 的劣化攻击"
                    )
                    break
                if attacker.skill.deteriorate_air and "fly" in defender.player.statuses:
                    attacker.effective_attack = F(0)
                    result.logs.append(
                        f"玩家{defender.player.player_id} 的飞天免疫了 玩家{attacker.player.player_id} 的对空劣化攻击"
                    )
                    break
                if (
                    attacker.skill.deteriorate_ground
                    and "dive" in defender.player.statuses
                ):
                    attacker.effective_attack = F(0)
                    result.logs.append(
                        f"玩家{defender.player.player_id} 的遁地免疫了 玩家{attacker.player.player_id} 的对地劣化攻击"
                    )
                    break

    # 规则特判：反射镜对小于3点的普通攻击产生反弹并击杀对应施法者
    def _rule_reflect_lt3(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        self._reflect(
            states, result, threshold=F(3), inclusive=False, effect_name="反射镜"
        )

    # 规则特判：卡兹光对小于等于4.5点的普通攻击产生反弹并击杀对应施法者
    def _rule_reflect_le45(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        self._reflect(
            states, result, threshold=F("4.5"), inclusive=True, effect_name="卡兹光"
        )

    # 通用反射规则内核：筛查达标的脆弱攻击者并在满足判定条件时将其击杀
    def _reflect(
        self,
        states: Mapping[int, TurnState],
        result: RoundResult,
        *,
        threshold: Energy,
        inclusive: bool,
        effect_name: str,
    ) -> None:
        for source in states.values():
            if effect_name == "反射镜" and "reflect_lt3" not in source.skill.specials:
                continue
            if effect_name == "卡兹光" and "reflect_le45" not in source.skill.specials:
                continue
            for target in self._enemy_attackers_of(source.player, states):
                if target.skill_name == "雷八" or target.effective_attack <= 0:
                    continue
                matched = (
                    target.effective_attack <= threshold
                    if inclusive
                    else target.effective_attack < threshold
                )
                if matched:
                    self._kill(
                        target.player,
                        result,
                        f"玩家{source.player.player_id} 的{effect_name}反弹并击杀了 玩家{target.player.player_id}",
                    )

    # 规则特判：雷八的闪电特性直接击杀处于特定脆弱状态或使用特定技能的目标
    def _apply_lei_ba_kill(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for source in states.values():
            if source.skill_name != "雷八" or source.effective_attack <= 0:
                continue
            for target in self._enemies_of(source.player, states):
                if "killed_by_lei_ba" in target.skill.specials:
                    self._kill(
                        target.player,
                        result,
                        f"玩家{source.player.player_id} 的雷八直接击杀了 玩家{target.player.player_id} 的 {target.skill_name}",
                    )

    # 基础决战段：将有效攻击与敌方所有有效防御进行数值比对，并分派粉碎或击杀结果
    def _apply_core_combat(
        self, states: Mapping[int, TurnState], result: RoundResult
    ) -> None:
        for attacker in states.values():
            if attacker.effective_attack <= 0 or attacker.player.alive is False:
                continue
            for defender in self._enemies_of(attacker.player, states):
                if not defender.player.alive:
                    continue
                self._resolve_pair(attacker, defender, result)

    # 双人对抗判定：伤害低于防守无事发生，溢出1以内的被粉碎，溢出大于1的被击杀
    def _resolve_pair(
        self, attacker: TurnState, defender: TurnState, result: RoundResult
    ) -> None:
        if attacker.effective_attack <= defender.effective_defense:
            return
        diff = attacker.effective_attack - defender.effective_defense
        if diff < F(1):
            self._smash_skill(
                defender,
                result,
                f"玩家{attacker.player.player_id} 的 {attacker.skill_name} 以微弱优势粉碎了 玩家{defender.player.player_id} 的 {defender.skill_name}",
            )
            return
        self._kill(
            defender.player,
            result,
            f"玩家{attacker.player.player_id} 的 {attacker.skill_name} 击杀了 玩家{defender.player.player_id}",
        )

    # 将指定目标的技能置入“粉碎”状态并强制清零其攻击力
    def _smash_skill(self, state: TurnState, result: RoundResult, log: str) -> None:
        state.player.smashed_skills.add(state.skill_name)
        result.smashed_this_round.setdefault(state.player.player_id, set()).add(
            state.skill_name
        )
        if state.skill.category == "attack":
            state.effective_attack = F(0)
            state.invalidated = True
        result.logs.append(log)

    # 处决指定目标。将其存活状态设为False，并写入战斗阵亡日志
    def _kill(self, player: PlayerState, result: RoundResult, log: str) -> None:
        if not player.alive:
            return
        player.alive = False
        result.dead_players.add(player.player_id)
        result.logs.append(log)

    # 系统梳理：收尾并汇集当回合已经处于死亡状态的玩家名单
    def _finalize_deaths(
        self, players: Sequence[PlayerState], result: RoundResult
    ) -> None:
        for player in players:
            if not player.alive:
                result.dead_players.add(player.player_id)

    # 敌对方筛选：返回排除自身及同队伍以后的敌对阵营目标迭代器
    def _enemies_of(
        self, player: PlayerState, states: Mapping[int, TurnState]
    ) -> Iterable[TurnState]:
        return (
            state
            for state in states.values()
            if state.player.team_id != player.team_id and state.player.alive
        )

    # 敌对攻势筛选：在敌对方中聚焦筛选出采用“攻击类”技能的目标
    def _enemy_attackers_of(
        self, player: PlayerState, states: Mapping[int, TurnState]
    ) -> Iterable[TurnState]:
        return (
            state
            for state in self._enemies_of(player, states)
            if state.skill.category == "attack" and state.player.alive
        )

    # 基于已有锁链与高阶装备状态，动态刷新当前玩家的回合充能加成点数
    def _refresh_charge_bonus(self, player: PlayerState) -> None:
        bonus = 0
        for equip_name, equip_state in player.equipments.items():
            bonus += chain_bonus_for_equipment(equip_name, equip_state.phase)
        if "锁链*1" in player.welfare:
            bonus += 1
        player.charge_bonus = bonus


# 便携工具：快速批量创建处于初始白板状态的玩家集合
def create_players(count: int) -> List[PlayerState]:
    return [
        PlayerState(player_id=index + 1, team_id=index + 1) for index in range(count)
    ]


# 数值美化：将带有分数结构的Energy数值格式化为易读排版输出
def format_energy(value: Energy) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):g}"


if __name__ == "__main__":
    engine = RuleEngine()
    players = create_players(2)
    result = engine.resolve_round(
        players, {1: "蓄", 2: "蓄"}, first_round_of_small_game=True
    )
    print("actions:", result.actions)
    print("dead:", sorted(result.dead_players))
    print("restart:", result.draw_restart)
    for line in result.logs:
        print("-", line)
