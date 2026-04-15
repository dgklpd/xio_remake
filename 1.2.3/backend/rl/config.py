"""
model/config.py
═══════════════════════════════════════════════════════════════════
所有常量、超参数与空间定义的集中管理模块。
修改本文件即可在不触碰算法代码的情况下调整训练配置。
═══════════════════════════════════════════════════════════════════
"""

from pathlib import Path

# ─── 路径 ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent  # 项目根目录
MODEL_DIR = Path(__file__).parent  # model/ 目录
CHECKPOINT_DIR = MODEL_DIR / "checkpoints"  # 模型检查点存储目录

# ─── 游戏装备常量（与 rules.py 保持一致）────────────────────────────────────
EQUIPMENT_POOL = ["天马", "冰盾", "龙盾", "免疫", "正义", "牛脖", "狼拳"]

# 各装备可超率的最高阶段数
MAX_PHASE_PER_EQUIP = {
    "天马": 8,
    "冰盾": 3,
    "龙盾": 2,
    "免疫": 3,
    "正义": 16,
    "牛脖": 0,
    "狼拳": 0,
}

# 玩家状态中存储特殊能量层数的字段名
COUNTER_KEYS = ["bao_bing", "bao_long", "jing_bing"]

# ─── 动作空间：全部技能名称（顺序固定，不可随意改变！）──────────────────────
# 顺序决定了神经网络输出层的动作索引，必须与 obs.py 中的 ACTION_TO_IDX 对应
ALL_SKILL_NAMES = [
    # 基础局（所有玩家共享）
    "蓄",
    "地波",
    "天波",
    "波波",
    "雷八",
    "超防",
    "三砍",
    "五合体",
    "虎合体",
    # 装备：天马
    "天马",
    "天马流星拳",
    "天马彗星拳",
    "天马后空翻",
    # 装备：冰盾
    "冰盾",
    "爆冰",
    "爆冰拳",
    "凝冰",
    "晶冰拳",
    # 装备：龙盾
    "龙盾",
    "爆龙",
    "爆龙拳",
    "金龙拳",
    # 装备：免疫
    "免疫",
    "小免",
    "大免",
    "挪移",
    # 装备：正义
    "正义",
    "反射镜",
    "穿心镜",
    "卡兹拳",
    "卡兹光",
    "卡兹膜",
    # 装备：牛脖
    "牛盾",
    "顶",
    # 装备：狼拳（含合成技能）
    "狼拳",
    "冰狼拳",
    "金狼拳",
    # 低保技能
    "小盾",
]

# 超率动作（7 件装备各对应一个）
SUPER_RATE_NAMES = [f"超率:{e}" for e in EQUIPMENT_POOL]

# 合并全部动作
ALL_ACTION_NAMES = ALL_SKILL_NAMES + SUPER_RATE_NAMES

# 便捷查找表
N_ACTIONS = len(ALL_ACTION_NAMES)  # 总动作数（≈45）
N_SKILLS = len(ALL_SKILL_NAMES)  # 技能数量（用于 smashed 掩码）
N_EQUIPMENTS = len(EQUIPMENT_POOL)  # 装备数量（=7）

ACTION_TO_IDX = {a: i for i, a in enumerate(ALL_ACTION_NAMES)}
SKILL_TO_IDX = {s: i for i, s in enumerate(ALL_SKILL_NAMES)}
EQUIP_TO_IDX = {e: i for i, e in enumerate(EQUIPMENT_POOL)}

# ─── 观测空间维度 ─────────────────────────────────────────────────────────────
#
# 每名玩家的观测向量构成：
#   energy           (1)  : 当前蓄能量（归一化）
#   charge_bonus     (1)  : 总锁链加成（归一化）
#   has_equipment    (7)  : 是否拥有各装备（二值）
#   phase_norm       (7)  : 各装备当前阶段（归一化）
#   counters         (3)  : 爆冰/爆龙/晶冰层数（归一化）
#   smashed_skills   (38) : 本小局被粉碎的技能掩码（二值）
#   welfare          (2)  : 低保标志（锁链*1 / 小盾）
#
OBS_PER_PLAYER = 1 + 1 + N_EQUIPMENTS + N_EQUIPMENTS + 3 + N_SKILLS + 2

# 额外的对局级上下文（比分、轮次、剩余装备、停滞计数、固定席位 token）
MATCH_CONTEXT_DIM = 9

# 上一回合双方动作 one-hot，帮助策略识别镜像循环并主动换线
PREV_ACTIONS_DIM = N_ACTIONS * 2

OBS_DIM = OBS_PER_PLAYER * 2 + MATCH_CONTEXT_DIM + PREV_ACTIONS_DIM

# 归一化分母——避免超常数值导致梯度爆炸
ENERGY_NORM = 20.0  # 基础局最高合理能量上限（超出后截断）
CHARGE_BONUS_NORM = 17.0  # 天马(5)+正义(11)+牛脖低保(1) 的理论最大锁链加成
COUNTER_NORM = 9.0  # 特殊能量层数的合理上限
# 各装备阶段归一化分母（各自除以自己的 max_phase，max_phase=0 时设为1防止除零）
PHASE_NORM = {e: max(p, 1) for e, p in MAX_PHASE_PER_EQUIP.items()}

# ─── MaskablePPO 超参数 ───────────────────────────────────────────────────────
# 参考：Schulman et al. (2017) PPO 论文推荐初始值
# v2: 修复熵坍塌 — ent_coef 0.01→0.05, lr 3e-4→1e-4, gamma 0.99→0.995
PPO_KWARGS = dict(
    learning_rate=1e-4,  # Adam 学习率（降低以防策略振荡）
    n_steps=1024,  # 每次 rollout 收集的步数（缩小匹配短训练）
    batch_size=128,  # mini-batch 大小（匹配缩小的 n_steps）
    n_epochs=10,  # 每次 rollout 更新的轮次
    gamma=0.995,  # 折扣因子（拍手游戏对局较长，需要更远视）
    gae_lambda=0.95,  # GAE-λ
    clip_range=0.2,  # PPO clip 系数
    ent_coef=0.05,  # 熵正则系数（大幅提升以对抗熵坍塌）
    vf_coef=0.5,  # 价值函数损失权重
    max_grad_norm=0.5,  # 梯度裁剪上限
    verbose=1,
)

# ─── 训练流程参数 ─────────────────────────────────────────────────────────────
TOTAL_TIMESTEPS = 5_000_000  # 以“大局”为单位的训练步数
SELF_PLAY_UPDATE_FREQ = 50_000  # 每隔多少步保存一次检查点并更新对手
SELF_PLAY_POOL_SIZE = 8  # 自我博弈历史模型池的最大容量
SELF_PLAY_RANDOM_OPP_PROB = 0.15  # 训练中保留随机对手，避免早期过拟合镜像策略
SELF_PLAY_RULE_OPP_PROB = 0.15  # 训练中混入规则 AI，持续提供主动施压样本
MAX_TURNS_PER_SMALL_ROUND = 20  # 单个小局的最大回合数
MATCH_ROUND_LIMIT = 9  # 一个大局最多打 9 个小局
N_EVAL_EPISODES = 300  # 评估时使用的大局数量
STATS_REPORT_FREQ = 50  # 每多少局输出一次招式分布统计

# ─── 奖励塑形系数 ─────────────────────────────────────────────────────────────
# 小局塑形奖励
REWARD_ROUND_WIN = 0.2
REWARD_ROUND_LOSE = -0.2
REWARD_DRAW = 0.0  # 平局（全员同归于尽→重开，不记入轮次）

# 大局胜负奖励
REWARD_MATCH_WIN = 2.0
REWARD_MATCH_LOSE = -2.0

# 中间奖励（幅度较小，防止掩盖终局信号）
REWARD_SMASH_ENEMY = 0.1  # 粉碎对方技能（施压成功）
REWARD_SMASH_SELF = -0.1  # 自己技能被粉碎（被压制）
REWARD_SUPER_RATE = 0.05  # 超率成功（投资未来）

# v2 新增：能量管理与消极行为塑形
REWARD_CHARGE_WHEN_SAFE = 0.01  # 对手能量=0时蓄能的正激励
REWARD_KILL_ATTEMPT = 0.05  # 发动攻击且对手能量较低
REWARD_PASSIVE_PENALTY = -0.03  # 连续多回合不出攻击的惩罚
REWARD_STALEMATE_PENALTY = -0.02  # 回合无击杀/无粉碎/无超率的停滞惩罚
REWARD_STALEMATE_ESCALATION = -0.03  # 连续停滞时逐回合加重惩罚
REWARD_MIRROR_STALEMATE = -0.08  # 双方镜像且无进展时的额外惩罚
REWARD_TRUNCATION = -1.0  # 小局打满仍无结果的重罚，逼迫策略主动破局
PASSIVE_THRESHOLD = 1  # 连续多少回合无攻击算消极
REWARD_STEP_COST = -0.001  # 每个回合的时间成本
MAX_NO_PROGRESS_STREAK = 6  # 连续无进展达到阈值后，提前判定为停滞超时
MAX_MIRROR_STREAK = 4  # 连续镜像无进展达到阈值后，提前判定为停滞超时
