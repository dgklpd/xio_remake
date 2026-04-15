import os
import time
from typing import Dict, List, Optional, Tuple

# ===================== 游戏核心常量（100%对齐最终规则） =====================
# 全局装备池（严格按规则固定顺序，大局内唯一，前一件未获取后一件不可解锁）
EQUIPMENT_POOL = [
    "天马", "冰盾", "龙盾", "免疫", "正义", "牛脖", "狼拳"
]

# 基础技能库（所有玩家初始拥有，完全匹配规则）
BASE_SKILLS = {
    "蓄": {
        "type": "特殊",
        "defense": -1,  # 规则明确：防御值-1，会被所有攻击技能击杀
        "energy_cost": 0,
        "special": "add_energy",
        "desc": "防御-1，会被所有攻击击杀，每打出1次，基础蓄能量+1（受锁链额外加成）"
    },
    "地波": {
        "type": "特殊",
        "defense": 0,
        "energy_cost": 0,
        "special": "dun_di",
        "desc": "防御0，获得1回合遁地，免疫劣化对地攻击，回合结束移除"
    },
    "天波": {
        "type": "特殊",
        "defense": 0,
        "energy_cost": 0,
        "special": "fei_tian",
        "desc": "防御0，获得1回合飞天，免疫劣化对空攻击，回合结束移除"
    },
    "波波": {
        "type": "攻击",
        "attack": 2,
        "defense": 2,  # 规则：攻击技能自带与攻击力相同的防御力
        "energy_cost": 1,
        "deteriorate_ground": True,
        "deteriorate_air": True,
        "desc": "攻击2，劣化对地/对空，耗能1"
    },
    "雷八": {
        "type": "攻击",
        "attack": 1,
        "defense": 1,
        "energy_cost": 1/3,
        "deteriorate_ground": True,
        "deteriorate_air": False,
        "special": "lei_ba",
        "desc": "攻击1，劣化对地，耗能1/3，特殊击杀判定，不受粉碎效果影响"
    },
    "超防": {
        "type": "防御",
        "defense": 4.5,
        "energy_cost": 1,
        "desc": "防御4.5，耗能1"
    },
    "三砍": {
        "type": "攻击",
        "attack": 3,
        "defense": 3,
        "energy_cost": 3,
        "special": "smash_mian_yi",
        "desc": "攻击3，耗能3，可直接粉碎初始免疫技能"
    },
    "五合体": {
        "type": "攻击",
        "attack": 4,
        "defense": 4,
        "energy_cost": 5,
        "desc": "攻击4，耗能5"
    },
    "虎合体": {
        "type": "攻击",
        "attack": 5,
        "defense": 5,
        "energy_cost": 10,
        "desc": "攻击5，耗能10"
    }
}

# 装备技能库（完整还原所有阶段、特殊效果、合成机制，严格匹配规则）
EQUIPMENT_SKILLS = {
    "天马": {
        "max_phase": 8,
        "skills": {
            0: {"name": "天马", "type": "攻击", "attack": 2.5, "defense": 2.5, "energy_cost": 1/3,
                "deteriorate_ground": True, "deteriorate_air": False, "desc": "攻击2.5，劣化对地，耗能1/3"},
            1: {"name": "天马流星拳", "type": "攻击", "attack": 3, "defense": 3, "energy_cost": 1,
                "deteriorate_ground": False, "deteriorate_air": True, "desc": "攻击3，劣化对空，耗能1"},
            2: {"name": "天马彗星拳", "type": "攻击", "attack": 3, "defense": 3, "energy_cost": 1,
                "deteriorate_ground": False, "deteriorate_air": True, "desc": "攻击3，劣化对空，耗能1"},
            3: {"name": "天马后空翻", "type": "防御", "defense": 5, "energy_cost": 0,
                "special_limit": "killed_by_lei_ba", "desc": "防御5，耗能0，会被雷八直接击杀"},
            4: {"name": "天马锁链1", "type": "被动", "chain_bonus": 1, "desc": "每使用1次蓄，额外+1能量"},
            5: {"name": "天马锁链2", "type": "被动", "chain_bonus": 2, "desc": "每使用1次蓄，额外+2能量"},
            6: {"name": "天马锁链3", "type": "被动", "chain_bonus": 3, "desc": "每使用1次蓄，额外+3能量"},
            7: {"name": "天马锁链4", "type": "被动", "chain_bonus": 4, "desc": "每使用1次蓄，额外+4能量"},
            8: {"name": "天马锁链5", "type": "被动", "chain_bonus": 5, "desc": "每使用1次蓄，额外+5能量"},
        }
    },
    "冰盾": {
        "max_phase": 3,
        "skills": {
            0: {"name": "冰盾", "type": "防御", "defense": 2.5, "energy_cost": 0, "desc": "防御2.5，耗能0"},
            1: {"name": "爆冰", "type": "防御", "defense": 3.5, "energy_cost": 0,
                "special": "add_bao_bing", "desc": "防御3.5，耗能0，积攒1点爆冰能量"},
            2: {"name": "爆冰拳", "type": "攻击", "attack": 3, "defense": 3, "energy_cost": 1,
                "alt_cost": {"bao_bing": 3}, "deteriorate_ground": True, "deteriorate_air": False,
                "desc": "攻击3，劣化对地，耗能1蓄 或 3点爆冰能量"},
            3: {"name": "凝冰", "type": "防御", "defense": 4.5, "energy_cost": 1/6,
                "special": "add_jing_bing", "special_limit": "smashed_by_jin_long",
                "desc": "防御4.5，耗能1/6，积攒1点晶冰能量，会被金龙拳粉碎"},
            4: {"name": "晶冰拳", "type": "攻击", "attack": 3.5, "defense": 3.5, "energy_cost": 1,
                "alt_cost": {"jing_bing": 3}, "deteriorate_ground": False, "deteriorate_air": True,
                "desc": "攻击3.5，劣化对空，耗能1蓄 或 3点晶冰能量"},
        }
    },
    "龙盾": {
        "max_phase": 2,
        "skills": {
            0: {"name": "龙盾", "type": "防御", "defense": 2.5, "energy_cost": 0, "desc": "防御2.5，耗能0"},
            1: {"name": "爆龙", "type": "防御", "defense": 3.5, "energy_cost": 0,
                "special": "add_bao_long", "desc": "防御3.5，耗能0，积攒1点爆龙能量"},
            2: {"name": "爆龙拳", "type": "攻击", "attack": 3, "defense": 3, "energy_cost": 1,
                "alt_cost": {"bao_long": 3}, "deteriorate_ground": True, "deteriorate_air": False,
                "desc": "攻击3，劣化对地，耗能1蓄 或 3点爆龙能量"},
            3: {"name": "金龙拳", "type": "攻击", "attack": 4.5, "defense": 4.5, "energy_cost": 0,
                "deteriorate_ground": False, "deteriorate_air": True, "special": "smash_ning_bing",
                "desc": "攻击4.5，劣化对空，耗能0，可直接粉碎敌方凝冰技能"},
        }
    },
    "免疫": {
        "max_phase": 3,
        "skills": {
            0: {"name": "免疫", "type": "防御", "defense": 3, "energy_cost": 0,
                "special_limit": "smashed_by_san_kan", "desc": "防御3，耗能0，会被三砍直接粉碎"},
            1: {"name": "小免", "type": "防御", "defense": 3, "energy_cost": 0,
                "special": "smash_shield", "desc": "防御3，耗能0，敌方使用冰盾/龙盾会被直接粉碎"},
            2: {"name": "大免", "type": "防御", "defense": 4, "energy_cost": 0,
                "special_limit": "killed_by_lei_ba", "special": "smash_weak_attack",
                "desc": "防御4，耗能0，会被雷八击杀，敌方攻击<3会被粉碎（雷八除外）"},
            3: {"name": "挪移", "type": "防御", "defense": 5, "energy_cost": 1/3,
                "special": "smash_strong_attack", "desc": "防御5，耗能1/3，敌方攻击≤4.5会被粉碎"},
        }
    },
    "正义": {
        "max_phase": 16,
        "skills": {
            0: {"name": "正义", "type": "攻击", "attack": 3, "defense": 3, "energy_cost": 0,
                "deteriorate_ground": False, "deteriorate_air": True, "special_limit": "killed_by_lei_ba",
                "desc": "攻击3，劣化对空，耗能0，会被雷八直接击杀"},
            1: {"name": "反射镜", "type": "防御", "defense": 3, "energy_cost": 0,
                "special": "reflect_weak", "special_limit": "killed_by_lei_ba",
                "desc": "防御3，耗能0，反弹<3的攻击并击杀使用者（雷八除外），会被雷八击杀"},
            2: {"name": "穿心镜", "type": "攻击", "attack": 3.5, "defense": 3.5, "energy_cost": 0,
                "special_limit": "killed_by_lei_ba", "desc": "攻击3.5，耗能0，会被雷八直接击杀"},
            3: {"name": "卡兹拳", "type": "攻击", "attack": 4, "defense": 4, "energy_cost": 0,
                "special_limit": "killed_by_lei_ba", "desc": "攻击4，耗能0，会被雷八直接击杀"},
            4: {"name": "卡兹光", "type": "防御", "defense": 5, "energy_cost": 0,
                "special": "reflect_strong", "special_limit": "killed_by_lei_ba",
                "desc": "防御5，耗能0，反弹≤4.5的攻击并击杀使用者（雷八除外），会被雷八击杀"},
            5: {"name": "卡兹膜", "type": "防御", "defense": 4, "energy_cost": 0,
                "special_limit": "killed_by_lei_ba", "desc": "防御4，耗能0，会被雷八直接击杀"},
            6: {"name": "正义锁链1", "type": "被动", "chain_bonus": 1, "desc": "每使用1次蓄，额外+1能量"},
            7: {"name": "正义锁链2", "type": "被动", "chain_bonus": 2, "desc": "每使用1次蓄，额外+2能量"},
            8: {"name": "正义锁链3", "type": "被动", "chain_bonus": 3, "desc": "每使用1次蓄，额外+3能量"},
            9: {"name": "正义锁链4", "type": "被动", "chain_bonus": 4, "desc": "每使用1次蓄，额外+4能量"},
            10: {"name": "正义锁链5", "type": "被动", "chain_bonus": 5, "desc": "每使用1次蓄，额外+5能量"},
            11: {"name": "正义锁链6", "type": "被动", "chain_bonus": 6, "desc": "每使用1次蓄，额外+6能量"},
            12: {"name": "正义锁链7", "type": "被动", "chain_bonus": 7, "desc": "每使用1次蓄，额外+7能量"},
            13: {"name": "正义锁链8", "type": "被动", "chain_bonus": 8, "desc": "每使用1次蓄，额外+8能量"},
            14: {"name": "正义锁链9", "type": "被动", "chain_bonus": 9, "desc": "每使用1次蓄，额外+9能量"},
            15: {"name": "正义锁链10", "type": "被动", "chain_bonus": 10, "desc": "每使用1次蓄，额外+10能量"},
            16: {"name": "正义锁链11", "type": "被动", "chain_bonus": 11, "desc": "每使用1次蓄，额外+11能量"},
        }
    },
    "牛脖": {
        "max_phase": 0,
        "skills": {
            0: {"name": "牛盾", "type": "防御", "defense": 4.5, "energy_cost": 1/6, "desc": "防御4.5，耗能1/6"},
            1: {"name": "顶", "type": "攻击", "attack": 3, "defense": 3, "energy_cost": 1/3,
                "deteriorate_ground": False, "deteriorate_air": True, "desc": "攻击3，劣化对空，耗能1/3"},
        }
    },
    "狼拳": {
        "max_phase": 0,  # 基础无超率升级，满足组合条件后解锁合成超率
        "skills": {
            0: {"name": "狼拳", "type": "攻击", "attack": 2.5, "defense": 2.5, "energy_cost": 1/2,
                "deteriorate_ground": True, "deteriorate_air": False, "special": "smash_nuo_yi",
                "desc": "攻击2.5，劣化对地，耗能1/2，可粉碎挪移，不受挪移粉碎影响"},
        },
        # 合成技能规则（严格匹配原文，修正笔误）
        "combo_skills": {
            "冰狼拳": {
                "require": ["冰盾"],
                "require_phase": {"冰盾": 2},  # 超率凝冰（2阶）或晶冰拳（3阶）即可
                "type": "攻击",
                "attack": 3.5,
                "defense": 3.5,
                "energy_cost": 1,
                "alt_cost": {"jing_bing": 3},
                "deteriorate_ground": False,
                "deteriorate_air": True,
                "special": ["smash_nuo_yi", "immune_da_mian_smash"],
                "desc": "冰狼拳：攻击3.5，劣化对空，耗能1蓄/3晶冰，可粉碎挪移，不受大免/挪移粉碎影响"
            },
            "金狼拳": {
                "require": ["龙盾"],
                "require_phase": {"龙盾": 1},  # 超率爆龙/爆龙拳（1阶）或金龙拳（2阶）即可
                "type": "攻击",
                "attack": 4.5,
                "defense": 4.5,
                "energy_cost": 0,
                "deteriorate_ground": False,
                "deteriorate_air": True,
                "special": ["smash_nuo_yi", "smash_ning_bing", "immune_da_mian_smash"],
                "desc": "金狼拳：攻击4.5，劣化对空，耗能0，可粉碎挪移/凝冰，不受大免/挪移粉碎影响"
            }
        }
    }
}

# 低保技能（不算装备，允许多人同时持有）
WELFARE_SKILLS = {
    "锁链*1": {"type": "被动", "chain_bonus": 1, "desc": "每使用1次蓄，额外+1能量"},
    "小盾": {"type": "防御", "defense": 0, "special": "immune_deteriorate",
             "desc": "防御0，免疫所有带有劣化对地/劣化对空效果的攻击"}
}

# ===================== 玩家类（核心修改：粉碎规则适配） =====================
class Player:
    def __init__(self, player_id: int, team_id: int):
        self.player_id = player_id
        self.team_id = team_id
        self.is_alive = True
        self.energy = 0.0  # 蓄能量，小局结束清空
        # 装备与超率管理
        self.equipments: List[str] = []
        self.equip_phase: Dict[str, int] = {}  # 装备: 当前超率阶段
        # 【规则修改】粉碎技能：本小局无法使用，小局结束后刷新
        self.smashed_skills: set = set()
        # 技能选择
        self.selected_skill: Optional[Dict] = None
        self.selected_skill_name: str = ""
        # 回合临时状态
        self.fei_tian = False  # 飞天效果，免疫劣化对空
        self.dun_di = False    # 遁地效果，免疫劣化对地
        # 特殊能量
        self.bao_bing = 0
        self.bao_long = 0
        self.jing_bing = 0
        # 被动加成
        self.chain_bonus = 0  # 锁链总加成，自动刷新
        self.welfare: List[str] = []  # 低保技能列表

    # 获取可超率的装备列表（严格匹配规则：仅自己拥有、未到最高阶段的装备）
    def get_super_rate_available_equips(self) -> List[str]:
        available = []
        for equip in self.equipments:
            current_phase = self.equip_phase[equip]
            max_phase = EQUIPMENT_SKILLS[equip]["max_phase"]
            # 狼拳特殊处理：满足合成条件时视为可超率
            if equip == "狼拳":
                combo_skills = EQUIPMENT_SKILLS[equip].get("combo_skills", {})
                for combo in combo_skills.values():
                    meet = True
                    for req_equip in combo["require"]:
                        if req_equip not in self.equipments:
                            meet = False
                            break
                        req_p = combo["require_phase"].get(req_equip, 0)
                        if self.equip_phase.get(req_equip, 0) < req_p:
                            meet = False
                            break
                    if meet:
                        available.append(equip)
                        break
            # 常规装备超率判定
            elif current_phase < max_phase:
                available.append(equip)
        return available

    # 计算总可用技能（过滤本小局被粉碎的技能）
    def get_available_skills(self) -> Dict:
        skills = BASE_SKILLS.copy()
        # 1. 添加已解锁的装备技能
        for equip in self.equipments:
            equip_data = EQUIPMENT_SKILLS[equip]
            max_phase = self.equip_phase[equip]
            # 解锁当前阶段及以下的所有技能
            for phase in range(0, max_phase + 1):
                if phase in equip_data["skills"]:
                    skill = equip_data["skills"][phase]
                    skills[skill["name"]] = skill
            # 2. 添加满足条件的合成技能（狼拳专属）
            if equip == "狼拳" and "combo_skills" in equip_data:
                for combo_name, combo_skill in equip_data["combo_skills"].items():
                    # 检查合成条件
                    meet_require = True
                    for req_equip in combo_skill["require"]:
                        if req_equip not in self.equipments:
                            meet_require = False
                            break
                        req_phase = combo_skill["require_phase"].get(req_equip, 0)
                        if self.equip_phase.get(req_equip, 0) < req_phase:
                            meet_require = False
                            break
                    if meet_require:
                        skills[combo_name] = combo_skill
        # 3. 添加低保技能
        for welfare_name in self.welfare:
            skills[welfare_name] = WELFARE_SKILLS[welfare_name]
        # 【规则修改】过滤本小局被粉碎的技能、被动技能
        available_skills = {}
        for name, skill in skills.items():
            if name not in self.smashed_skills and skill["type"] != "被动":
                available_skills[name] = skill
        return available_skills

    # 刷新锁链总加成（装备+低保）
    def refresh_chain_bonus(self):
        total_bonus = 0
        # 装备锁链加成
        for equip in self.equipments:
            equip_data = EQUIPMENT_SKILLS[equip]
            max_phase = self.equip_phase[equip]
            for phase in range(0, max_phase + 1):
                skill = equip_data["skills"].get(phase, {})
                if skill.get("type") == "被动" and "chain_bonus" in skill:
                    total_bonus += skill["chain_bonus"]
        # 低保锁链加成
        for welfare_name in self.welfare:
            skill = WELFARE_SKILLS[welfare_name]
            if skill.get("type") == "被动" and "chain_bonus" in skill:
                total_bonus += skill["chain_bonus"]
        self.chain_bonus = total_bonus

    # 【规则修改】回合结束刷新：不再清空粉碎技能
    def round_end_refresh(self):
        self.fei_tian = False
        self.dun_di = False
        self.selected_skill = None
        self.selected_skill_name = ""

    # 【规则修改】小局结束全刷新：清空粉碎技能，严格遵循规则
    def small_round_end_refresh(self):
        self.energy = 0.0  # 规则：每小局结束蓄能量清空
        self.smashed_skills.clear()  # 规则：粉碎技能小局结束后刷新
        self.round_end_refresh()
        self.bao_bing = 0
        self.bao_long = 0
        self.jing_bing = 0
        self.is_alive = True

    # 大局结束完全重置
    def full_reset(self):
        self.small_round_end_refresh()
        self.equipments.clear()
        self.equip_phase.clear()
        self.welfare.clear()
        self.chain_bonus = 0

# ===================== 工具函数 =====================
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_divider(title: str = ""):
    print("\n" + "="*50)
    if title:
        print(f"{title:^50}")
        print("="*50)

# ===================== 游戏核心逻辑 =====================
# 超率处理（严格匹配规则：选装备解锁，仅对选中装备生效，无装备/全满不可超率）
def handle_super_rate(player: Player, game_state: Dict) -> bool:
    # 规则校验：无装备/无可用超率装备，无法超率
    available_equips = player.get_super_rate_available_equips()
    if not available_equips:
        print("无可用超率的装备（无装备或所有装备已超率至最高阶段），无法使用超率！")
        time.sleep(1)
        return False
    # 规则校验：蓄能量不足3
    if player.energy < 3:
        print(f"蓄能量不足3（当前{player.energy:.2f}），无法超率！")
        time.sleep(1)
        return False
    
    # 选择超率装备（规则：在自己拥有的全部装备中选择一件）
    print_divider(f"玩家{player.player_id} 超率操作")
    print("规则：超率仅对选中的装备生效，解锁其下一阶段技能，本回合防御力无限大")
    print("可超率的装备：")
    for i, equip in enumerate(available_equips, 1):
        current = player.equip_phase[equip]
        max_p = EQUIPMENT_SKILLS[equip]["max_phase"]
        print(f"{i}. {equip} (当前阶段{current}/{max_p})")
    
    while True:
        try:
            idx = int(input("请选择要超率的装备编号：")) - 1
            if 0 <= idx < len(available_equips):
                target_equip = available_equips[idx]
                break
            else:
                print("无效编号，请重新输入！")
        except ValueError:
            print("请输入有效数字！")
    
    # 执行超率
    player.energy -= 3
    player.equip_phase[target_equip] += 1
    player.refresh_chain_bonus()
    print(f"超率成功！【{target_equip}】阶段提升至 {player.equip_phase[target_equip]}")
    print("超率本身为防御力无限的防御技能，本回合免疫所有常规攻击")
    # 规则：超率本身视为防御力无限的防御技能
    player.selected_skill = {"type": "防御", "defense": float("inf"), "name": "超率"}
    player.selected_skill_name = "超率"
    time.sleep(2)
    return True

# 技能选择处理（新增粉碎技能提示）
def select_skill(player: Player, is_first_round: bool, game_state: Dict):
    print_divider(f"玩家{player.player_id} 回合操作")
    print(f"当前状态：存活={player.is_alive} | 蓄能量={player.energy:.2f}")
    print(f"持有装备：{player.equipments if player.equipments else '无'}")
    print(f"特殊能量：爆冰={player.bao_bing} 爆龙={player.bao_long} 晶冰={player.jing_bing}")
    # 【新增】显示本小局已被粉碎的技能
    if player.smashed_skills:
        print(f"⚠️  本小局已被粉碎的技能：{', '.join(player.smashed_skills)}")
    print("-"*30)

    # 规则：小局第一回合强制出蓄
    if is_first_round:
        print("【规则强制：小局第一回合必须出蓄】")
        player.selected_skill = BASE_SKILLS["蓄"]
        player.selected_skill_name = "蓄"
        print(f"已使用【蓄】，能量加成将在技能效果阶段结算")
        time.sleep(2)
        return

    # 显示可用技能
    available_skills = player.get_available_skills()
    print("可用技能：")
    skill_list = list(available_skills.items())
    for i, (name, skill) in enumerate(skill_list, 1):
        print(f"{i}. {name} | {skill['desc']}")
    
    # 规则：仅当有可超率装备时，显示超率选项
    can_super_rate = len(player.get_super_rate_available_equips()) > 0 and player.energy >= 3
    if can_super_rate:
        print(f"{len(skill_list)+1}. 超率 | 消耗3蓄能量，选择一件装备解锁下一阶段，本回合防御力无限大")

    # 选择操作
    max_choice = len(skill_list) + (1 if can_super_rate else 0)
    while True:
        try:
            choice = int(input("请选择技能/操作编号："))
            if 1 <= choice <= max_choice:
                break
            else:
                print(f"请输入1-{max_choice}之间的数字！")
        except ValueError:
            print("请输入有效数字！")

    # 处理超率
    if can_super_rate and choice == len(skill_list) + 1:
        success = handle_super_rate(player, game_state)
        if not success:
            select_skill(player, is_first_round, game_state)
        return

    # 处理技能选择
    skill_name, skill = skill_list[choice-1]
    # 检查能量消耗
    cost = skill["energy_cost"]
    alt_cost = skill.get("alt_cost", {})
    can_pay = False
    use_alt = False

    # 优先检查替代消耗（爆冰/爆龙/晶冰）
    for cost_type, need in alt_cost.items():
        if getattr(player, cost_type, 0) >= need:
            use_alt = True
            can_pay = True
            break
    # 检查蓄能量消耗
    if not use_alt and player.energy >= cost:
        can_pay = True

    if not can_pay:
        print("能量不足，无法使用该技能！请重新选择")
        time.sleep(1)
        select_skill(player, is_first_round, game_state)
        return

    # 扣除对应消耗
    if use_alt:
        for cost_type, need in alt_cost.items():
            current = getattr(player, cost_type, 0)
            setattr(player, cost_type, current - need)
            print(f"扣除{cost_type}能量{need}，剩余{getattr(player, cost_type, 0)}")
    else:
        player.energy -= cost
        print(f"扣除蓄能量{cost:.2f}，剩余{player.energy:.2f}")

    # 记录选中的技能
    player.selected_skill = skill
    player.selected_skill_name = skill_name
    print(f"已使用【{skill_name}】")
    time.sleep(1)

# 技能即时效果处理（统一处理蓄的能量增加，保证仅触发1次）
def handle_skill_effect(player: Player, game_state: Dict):
    skill = player.selected_skill
    if not skill:
        return
    special = skill.get("special", "")
    # 兼容列表格式的特殊效果
    if isinstance(special, list):
        for sp in special:
            handle_skill_effect_single(player, sp)
    else:
        handle_skill_effect_single(player, special)
    time.sleep(0.5)

# 单个特殊效果处理
def handle_skill_effect_single(player: Player, special: str):
    if special == "add_energy":
        # 规则：基础1点 + 锁链额外加成，仅此处触发1次
        base_add = 1
        bonus_add = player.chain_bonus
        total_add = base_add + bonus_add
        player.energy += total_add
        print(f"玩家{player.player_id}【蓄】生效：基础+{base_add}，锁链额外+{bonus_add}，总计+{total_add}")
        print(f"当前蓄能量：{player.energy:.2f}")
    elif special == "fei_tian":
        player.fei_tian = True
        print(f"玩家{player.player_id}获得【飞天】效果，本回合免疫劣化对空攻击")
    elif special == "dun_di":
        player.dun_di = True
        print(f"玩家{player.player_id}获得【遁地】效果，本回合免疫劣化对地攻击")
    elif special == "add_bao_bing":
        player.bao_bing += 1
        print(f"玩家{player.player_id}积攒1爆冰能量，当前{player.bao_bing}")
    elif special == "add_bao_long":
        player.bao_long += 1
        print(f"玩家{player.player_id}积攒1爆龙能量，当前{player.bao_long}")
    elif special == "add_jing_bing":
        player.jing_bing += 1
        print(f"玩家{player.player_id}积攒1晶冰能量，当前{player.jing_bing}")

# 核心攻防判定（【规则修改】粉碎提示语更新为「本小局无法使用」）
def battle_judge(players: List[Player], game_state: Dict):
    print_divider("攻防判定阶段")
    # 1. 收集所有玩家的攻防基础数值
    player_atk: Dict[int, float] = {}
    player_def: Dict[int, float] = {}
    attack_players: List[Player] = []
    defend_players: List[Player] = []

    for p in players:
        skill = p.selected_skill
        atk = skill.get("attack", 0)
        defe = skill.get("defense", 0)
        player_atk[p.player_id] = atk
        player_def[p.player_id] = defe
        if skill["type"] == "攻击":
            attack_players.append(p)
        else:
            defend_players.append(p)

    # 2. 前置特殊效果判定（粉碎类、特殊击杀类）
    print("\n【前置特殊效果判定】")
    # 2.1 小免：粉碎冰盾/龙盾
    for def_p in defend_players:
        def_skill = def_p.selected_skill
        def_special = def_skill.get("special", "")
        if def_special == "smash_shield":
            for target_p in players:
                if target_p == def_p:
                    continue
                target_skill_name = target_p.selected_skill_name
                if target_skill_name in ["冰盾", "龙盾"]:
                    target_p.smashed_skills.add(target_skill_name)
                    print(f"玩家{def_p.player_id}【小免】生效，玩家{target_p.player_id}的{target_skill_name}被粉碎！本小局无法使用")
    # 2.2 大免：粉碎<3的攻击（雷八除外，冰狼拳/金狼拳除外）
    for def_p in defend_players:
        def_skill = def_p.selected_skill
        def_special = def_skill.get("special", "")
        if def_special == "smash_weak_attack":
            for atk_p in attack_players:
                if atk_p == def_p:
                    continue
                atk_val = player_atk[atk_p.player_id]
                atk_name = atk_p.selected_skill_name
                atk_skill = atk_p.selected_skill
                # 规则：雷八除外，合成狼拳免疫大免粉碎
                immune = False
                if "immune_da_mian_smash" in atk_skill.get("special", []):
                    immune = True
                if atk_val < 3 and atk_name != "雷八" and not immune:
                    atk_p.smashed_skills.add(atk_name)
                    print(f"玩家{def_p.player_id}【大免】生效，玩家{atk_p.player_id}的{atk_name}被粉碎！本小局无法使用")
    # 2.3 挪移：粉碎≤4.5的攻击（狼拳/冰狼拳/金狼拳反粉碎挪移）
    for def_p in defend_players:
        def_skill = def_p.selected_skill
        def_special = def_skill.get("special", "")
        if def_special == "smash_strong_attack":
            for atk_p in attack_players:
                if atk_p == def_p:
                    continue
                atk_val = player_atk[atk_p.player_id]
                atk_name = atk_p.selected_skill_name
                atk_skill = atk_p.selected_skill
                # 规则：狼拳系列可粉碎挪移，不受挪移粉碎影响
                if "smash_nuo_yi" in atk_skill.get("special", []) or atk_skill.get("special") == "smash_nuo_yi":
                    def_p.smashed_skills.add(def_p.selected_skill_name)
                    print(f"玩家{atk_p.player_id}【{atk_name}】生效，玩家{def_p.player_id}的挪移被粉碎！本小局无法使用")
                    continue
                # 常规粉碎判定
                if atk_val <= 4.5:
                    atk_p.smashed_skills.add(atk_name)
                    print(f"玩家{def_p.player_id}【挪移】生效，玩家{atk_p.player_id}的{atk_name}被粉碎！本小局无法使用")
    # 2.4 金龙拳/金狼拳：粉碎凝冰
    for atk_p in attack_players:
        atk_skill = atk_p.selected_skill
        atk_special = atk_skill.get("special", [])
        if not isinstance(atk_special, list):
            atk_special = [atk_special]
        if "smash_ning_bing" in atk_special:
            for target_p in players:
                if target_p == atk_p:
                    continue
                target_skill_name = target_p.selected_skill_name
                if target_skill_name == "凝冰":
                    target_p.smashed_skills.add(target_skill_name)
                    print(f"玩家{atk_p.player_id}【{atk_p.selected_skill_name}】生效，玩家{target_p.player_id}的凝冰被粉碎！本小局无法使用")
    # 2.5 三砍：粉碎初始免疫
    for atk_p in attack_players:
        atk_skill_name = atk_p.selected_skill_name
        if atk_skill_name == "三砍":
            for target_p in players:
                if target_p == atk_p:
                    continue
                target_skill_name = target_p.selected_skill_name
                if target_skill_name == "免疫":
                    target_p.smashed_skills.add(target_skill_name)
                    print(f"玩家{atk_p.player_id}【三砍】生效，玩家{target_p.player_id}的免疫被粉碎！本小局无法使用")
    time.sleep(1)

    # 3. 攻击生效判定（被粉碎的攻击无效、劣化豁免、小盾免疫）
    print("\n【攻击生效判定】")
    valid_attack: Dict[int, float] = {}
    for atk_p in attack_players:
        atk_id = atk_p.player_id
        atk_name = atk_p.selected_skill_name
        # 被粉碎的攻击直接无效
        if atk_name in atk_p.smashed_skills:
            valid_attack[atk_id] = 0
            print(f"玩家{atk_id}的【{atk_name}】已被粉碎，攻击无效")
            continue
        # 基础攻击值
        atk_val = player_atk[atk_id]
        valid_attack[atk_id] = atk_val
        print(f"玩家{atk_id}【{atk_name}】攻击{atk_val}生效")
    time.sleep(1)

    # 4. 反弹效果判定（反射镜/卡兹光）
    print("\n【反弹效果判定】")
    for def_p in defend_players:
        def_skill = def_p.selected_skill
        def_special = def_skill.get("special", "")
        if def_special not in ["reflect_weak", "reflect_strong"]:
            continue
        # 反弹阈值
        threshold = 3 if def_special == "reflect_weak" else 4.5
        for atk_p in attack_players:
            if atk_p == def_p:
                continue
            atk_val = valid_attack.get(atk_p.player_id, 0)
            atk_name = atk_p.selected_skill_name
            # 规则：雷八除外
            if atk_name == "雷八":
                continue
            if atk_val <= threshold and atk_val > 0:
                atk_p.is_alive = False
                print(f"玩家{def_p.player_id}【{def_p.selected_skill_name}】反弹生效！玩家{atk_p.player_id}被击杀！")
    time.sleep(1)

    # 5. 雷八特殊击杀判定（优先于常规攻防）
    print("\n【雷八特殊击杀判定】")
    def check_lei_ba_kill(atk_p: Player, def_p: Player, atk_val: float):
        if atk_p.selected_skill_name != "雷八" or atk_val == 0:
            return
        def_skill_name = def_p.selected_skill_name
        # 规则内会被雷八直接击杀的技能列表
        killed_skill_list = [
            "天马后空翻", "大免", "正义", "反射镜",
            "穿心镜", "卡兹拳", "卡兹光", "卡兹膜"
        ]
        if def_skill_name in killed_skill_list:
            def_p.is_alive = False
            print(f"玩家{atk_p.player_id}的【雷八】触发特殊击杀！玩家{def_p.player_id}的{def_skill_name}被直接击破，玩家阵亡！")

    # 2人局双向判定
    p1, p2 = players[0], players[1]
    p1_atk = valid_attack.get(p1.player_id, 0)
    p2_atk = valid_attack.get(p2.player_id, 0)
    check_lei_ba_kill(p1, p2, p1_atk)
    check_lei_ba_kill(p2, p1, p2_atk)
    time.sleep(0.5)

    # 6. 劣化豁免与小盾免疫判定
    print("\n【劣化/免疫效果判定】")
    # p1攻击p2的生效判定
    p1_skill = p1.selected_skill
    if p1_atk > 0:
        # 小盾免疫：所有劣化攻击无效
        if p2.selected_skill_name == "小盾" and (p1_skill.get("deteriorate_ground", False) or p1_skill.get("deteriorate_air", False)):
            p1_atk = 0
            print(f"玩家{p2.player_id}【小盾】生效，免疫玩家{p1.player_id}的劣化攻击")
        # 飞天免疫劣化对空
        elif p1_skill.get("deteriorate_air", False) and p2.fei_tian:
            p1_atk = 0
            print(f"玩家{p2.player_id}处于飞天状态，免疫玩家{p1.player_id}的劣化对空攻击")
        # 遁地免疫劣化对地
        elif p1_skill.get("deteriorate_ground", False) and p2.dun_di:
            p1_atk = 0
            print(f"玩家{p2.player_id}处于遁地状态，免疫玩家{p1.player_id}的劣化对地攻击")
    # p2攻击p1的生效判定
    p2_skill = p2.selected_skill
    if p2_atk > 0:
        if p1.selected_skill_name == "小盾" and (p2_skill.get("deteriorate_ground", False) or p2_skill.get("deteriorate_air", False)):
            p2_atk = 0
            print(f"玩家{p1.player_id}【小盾】生效，免疫玩家{p2.player_id}的劣化攻击")
        elif p2_skill.get("deteriorate_air", False) and p1.fei_tian:
            p2_atk = 0
            print(f"玩家{p1.player_id}处于飞天状态，免疫玩家{p2.player_id}的劣化对空攻击")
        elif p2_skill.get("deteriorate_ground", False) and p1.dun_di:
            p2_atk = 0
            print(f"玩家{p1.player_id}处于遁地状态，免疫玩家{p2.player_id}的劣化对地攻击")
    time.sleep(0.5)

    # 7. 核心攻防对拼判定（严格匹配最终规则）
    print("\n【核心攻防对拼判定】")
    p1_def = player_def[p1.player_id]
    p2_def = player_def[p2.player_id]

    # 规则核心判定逻辑
    def judge_attack(atk_val: float, def_val: float, atk_p: Player, def_p: Player):
        if atk_val <= 0:
            return
        # 规则1：攻击力 ≤ 防御力，无效果
        if atk_val <= def_val:
            print(f"玩家{atk_p.player_id}攻击{atk_val} ≤ 玩家{def_p.player_id}防御{def_val}，无效果")
            return
        # 计算攻防差值
        diff = atk_val - def_val
        # 规则2：攻击力>防御力，且差值<1 → 数值更低者技能被粉碎
        if diff < 1:
            if atk_val < def_val:
                atk_p.smashed_skills.add(atk_p.selected_skill_name)
                print(f"攻防差值{diff}<1，玩家{atk_p.player_id}的【{atk_p.selected_skill_name}】被粉碎！本小局无法使用")
            else:
                def_p.smashed_skills.add(def_p.selected_skill_name)
                print(f"攻防差值{diff}<1，玩家{def_p.player_id}的【{def_p.selected_skill_name}】被粉碎！本小局无法使用")
        # 规则3：攻击力>防御力，且差值≥1 → 数值更低者直接阵亡
        else:
            def_p.is_alive = False
            print(f"攻防差值{diff}≥1，玩家{def_p.player_id}防御不足，被直接击杀！")

    # 双向攻防判定
    judge_attack(p1_atk, p2_def, p1, p2)
    judge_attack(p2_atk, p1_def, p2, p1)
    time.sleep(2)

# 小局流程（规则对齐：开局蓄能量强制为0）
def run_small_round(players: List[Player], game_state: Dict) -> Optional[Player]:
    round_num = 1
    # 小局开始前重置所有玩家状态，严格保证蓄能量为0
    for p in players:
        p.small_round_end_refresh()
    print_divider("新小局开始")
    print("规则：小局第一回合强制出蓄，开局蓄能量为0；一方阵亡则小局结束；全员阵亡则小局无效重开")
    print("⚠️  重要：被粉碎的技能本小局全程无法使用，仅小局结束后刷新")
    time.sleep(2)

    while True:
        clear_screen()
        print_divider(f"第 {round_num} 回合")
        is_first_round = (round_num == 1)

        # 1. 存活玩家依次选择技能
        for p in players:
            if p.is_alive:
                select_skill(p, is_first_round, game_state)
                clear_screen()

        # 2. 处理技能即时效果
        print_divider("技能即时效果触发")
        for p in players:
            if p.is_alive:
                handle_skill_effect(p, game_state)
        time.sleep(1)

        # 3. 核心攻防判定
        battle_judge(players, game_state)

        # 4. 小局结束条件检查
        alive_players = [p for p in players if p.is_alive]
        # 全员阵亡，小局无效重开
        if len(alive_players) == 0:
            print_divider("本回合所有玩家阵亡，小局无效，重新开始")
            time.sleep(2)
            return run_small_round(players, game_state)
        # 仅剩1人存活，小局结束
        if len(alive_players) == 1:
            winner = alive_players[0]
            print_divider(f"小局结束！玩家{winner.player_id} 获胜！")
            time.sleep(2)
            return winner

        # 5. 回合结束刷新
        for p in players:
            p.round_end_refresh()
        round_num += 1
        print("\n回合结束，按回车进入下一回合")
        input()

# 中局流程（2人局1小局=1中局，严格匹配规则）
def run_mid_round(players: List[Player], game_state: Dict) -> Optional[Player]:
    print_divider("新中局开始")
    # 运行小局
    winner = run_small_round(players, game_state)
    if not winner:
        return None

    # 发放装备（严格按固定顺序，大局内唯一，前一件未获取后一件不可解锁）
    if game_state["next_equip_idx"] < len(EQUIPMENT_POOL):
        equip_name = EQUIPMENT_POOL[game_state["next_equip_idx"]]
        winner.equipments.append(equip_name)
        winner.equip_phase[equip_name] = 0
        winner.refresh_chain_bonus()
        game_state["next_equip_idx"] += 1
        print(f"玩家{winner.player_id} 获得装备【{equip_name}】！")
        # 低保发放规则：有玩家获得牛脖，无装备玩家获得低保一
        if equip_name == "牛脖":
            for p in players:
                if len(p.equipments) == 0:
                    p.welfare = ["锁链*1", "小盾"]
                    p.refresh_chain_bonus()
                    print(f"玩家{p.player_id} 无装备，获得低保一！")
    else:
        print("全局装备池已全部发放，无新装备可获取")
    # 胜利积分增加
    game_state[f"player_{winner.player_id}_score"] += 1
    print(f"当前胜利积分：玩家1={game_state['player_1_score']} | 玩家2={game_state['player_2_score']}")
    time.sleep(3)
    return winner

# 主游戏循环
def main():
    clear_screen()
    print_divider("《蓄》回合制对战游戏 规则最终版")
    print("⚠️  核心规则更新：粉碎效果改为【本小局无法使用】，仅小局结束后刷新")
    print("核心规则说明：")
    print("1. 攻防判定：攻击>防御，差值<1→技能粉碎；差值≥1→直接阵亡")
    print("2. 蓄防御值-1，会被所有攻击击杀，每使用1次基础蓄能量+1（锁链额外加成）")
    print("3. 超率：3蓄能量选择1件装备解锁下一阶段，本回合防御力无限大")
    print("4. 2人本地对战，率先获得3胜的玩家获得大局最终胜利")
    print("\n按回车开始游戏")
    input()

    # 初始化玩家与游戏状态
    player1 = Player(1, 1)
    player2 = Player(2, 2)
    players = [player1, player2]
    game_state = {
        "next_equip_idx": 0,  # 下一个发放的装备索引（严格按顺序）
        "player_1_score": 0,
        "player_2_score": 0,
        "win_score": 3  # 大局胜利所需积分
    }

    # 大局主循环
    while True:
        clear_screen()
        # 检查大局结束条件
        if game_state["player_1_score"] >= game_state["win_score"]:
            print_divider("大局结束！玩家1 获得最终胜利！")
            break
        if game_state["player_2_score"] >= game_state["win_score"]:
            print_divider("大局结束！玩家2 获得最终胜利！")
            break
        
        # 运行中局
        run_mid_round(players, game_state)
    
    # 游戏结束
    print("\n游戏结束，按回车退出程序")
    input()

# 启动游戏
if __name__ == "__main__":
    main()
