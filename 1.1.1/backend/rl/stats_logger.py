"""
model/stats_logger.py
═══════════════════════════════════════════════════════════════════
训练过程中的自博弈对局统计收集与格式化输出模块。

负责聚合多局数据并输出可读的招式分布表、胜负统计和对局健康指标，
用于诊断策略退化（如天波循环）等问题。

使用方式：
  collector = EpisodeStatsCollector()
  collector.record_episode(action_counts, result, n_rounds)
  ...
  collector.report_and_reset()   # 输出统计并清零
═══════════════════════════════════════════════════════════════════
"""

from collections import Counter, defaultdict
from typing import Dict, List, Optional

from .config import ALL_ACTION_NAMES


# 技能按类别分组，用于报告中的分类展示
_SKILL_CATEGORIES = {
    "蓄能/闪避": {"蓄", "地波", "天波"},
    "基础攻击": {"波波", "雷八"},
    "高级攻击": {
        "三砍", "五合体", "虎合体",
        "天马", "天马流星拳", "天马彗星拳",
        "爆冰拳", "晶冰拳", "爆龙拳", "金龙拳",
        "穿心镜", "卡兹拳", "顶", "狼拳", "冰狼拳", "金狼拳", "正义",
    },
    "防御/护盾": {
        "超防", "天马后空翻",
        "冰盾", "爆冰", "凝冰",
        "龙盾", "爆龙",
        "免疫", "小免", "大免", "挪移",
        "反射镜", "卡兹光", "卡兹膜",
        "牛盾", "小盾",
    },
    "超率": {f"超率:{e}" for e in ["天马", "冰盾", "龙盾", "免疫", "正义", "牛脖", "狼拳"]},
}


class EpisodeStatsCollector:
    """
    聚合多个 episode 的招式使用分布和胜负结果，
    在调用 report_and_reset() 时输出格式化统计报告。
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        """清零所有累计统计数据。"""
        self._agent_action_counts: Counter = Counter()
        self._opp_action_counts: Counter = Counter()
        self._total_episodes: int = 0
        self._wins: int = 0
        self._losses: int = 0
        self._draws: int = 0
        self._truncated: int = 0
        self._total_rounds: int = 0
        self._round_counts: List[int] = []

    def record_episode(
        self,
        agent_action_counts: Dict[str, int],
        opp_action_counts: Dict[str, int],
        result: str,  # "win" | "loss" | "draw" | "truncated"
        n_rounds: int,
    ) -> None:
        """
        记录一局的统计数据。

        参数：
          agent_action_counts: 本局中 agent 各招式的使用次数
          opp_action_counts:   本局中 opponent 各招式的使用次数
          result:              本局结果
          n_rounds:            本局持续的回合数
        """
        self._agent_action_counts.update(agent_action_counts)
        self._opp_action_counts.update(opp_action_counts)
        self._total_episodes += 1
        self._total_rounds += n_rounds
        self._round_counts.append(n_rounds)

        if result == "win":
            self._wins += 1
        elif result == "loss":
            self._losses += 1
        elif result == "draw":
            self._draws += 1
        elif result == "truncated":
            self._truncated += 1

    @property
    def total_episodes(self) -> int:
        return self._total_episodes

    def report_and_reset(self, label: str = "") -> str:
        """
        生成格式化的统计报告字符串，然后清零计数器。

        参数：
          label: 报告标题中的额外标签（如步数信息）

        返回：
          多行格式化字符串，可直接 print 输出
        """
        if self._total_episodes == 0:
            return "[Stats] 暂无对局数据。\n"

        lines: List[str] = []
        sep = "─" * 60

        lines.append(f"\n{sep}")
        lines.append(f"  📊 自博弈对局统计 {label}")
        lines.append(sep)

        # ── 1. 胜负统计 ──────────────────────────────────────────────────────
        total = self._total_episodes
        wr = self._wins / max(self._wins + self._losses, 1)
        avg_rounds = self._total_rounds / total

        lines.append(f"  总局数: {total}  |  平均回合数: {avg_rounds:.1f}")
        lines.append(
            f"  胜: {self._wins} ({100*self._wins/total:.1f}%)  "
            f"负: {self._losses} ({100*self._losses/total:.1f}%)  "
            f"平: {self._draws} ({100*self._draws/total:.1f}%)  "
            f"超时: {self._truncated} ({100*self._truncated/total:.1f}%)"
        )
        lines.append(f"  净胜率: {wr:.1%}")

        # ── 2. 回合数分布 ────────────────────────────────────────────────────
        if self._round_counts:
            sorted_rc = sorted(self._round_counts)
            median_r = sorted_rc[len(sorted_rc) // 2]
            min_r = sorted_rc[0]
            max_r = sorted_rc[-1]
            lines.append(f"  回合数分布: min={min_r}  median={median_r}  max={max_r}")

        # ── 3. Agent 招式分布 ────────────────────────────────────────────────
        lines.append(f"\n  {'Agent 招式分布':─^54}")
        lines.extend(
            self._format_action_distribution(self._agent_action_counts)
        )

        # ── 4. Opponent 招式分布 ─────────────────────────────────────────────
        lines.append(f"\n  {'Opponent 招式分布':─^52}")
        lines.extend(
            self._format_action_distribution(self._opp_action_counts)
        )

        lines.append(sep + "\n")

        report = "\n".join(lines)
        self.reset()
        return report

    # ── 内部辅助 ─────────────────────────────────────────────────────────────

    def _format_action_distribution(
        self, counts: Counter
    ) -> List[str]:
        """将招式计数格式化为分类排列的表格行。"""
        total = sum(counts.values())
        if total == 0:
            return ["    (无数据)"]

        lines: List[str] = []

        # 按类别分组输出
        for cat_name, cat_skills in _SKILL_CATEGORIES.items():
            cat_counts = {s: counts.get(s, 0) for s in cat_skills if counts.get(s, 0) > 0}
            if not cat_counts:
                continue
            cat_total = sum(cat_counts.values())
            lines.append(f"    [{cat_name}] 合计 {cat_total} 次 ({100*cat_total/total:.1f}%)")
            # 按频次降序排列
            for skill, cnt in sorted(cat_counts.items(), key=lambda x: -x[1]):
                pct = 100 * cnt / total
                bar = "█" * int(pct / 2) + "░" * max(0, 25 - int(pct / 2))
                lines.append(f"      {skill:　<8s}  {cnt:>5d} ({pct:5.1f}%)  {bar}")

        # Top-5 最常用招式
        lines.append(f"    ── Top 5 ──")
        for skill, cnt in counts.most_common(5):
            pct = 100 * cnt / total
            lines.append(f"      #{skill}  {cnt} ({pct:.1f}%)")

        return lines
