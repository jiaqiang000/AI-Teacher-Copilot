"""Teacher Copilot 示例配置守门测试(007 诊断后的补强)。

背景:config.teacher-copilot.example.yaml 自提交 beb52220 起,因
`eval-diagnoser` 块缩进错位(游离在 `extensions:` 之后、失去 `custom_agents` 父级)
而不再是合法 YAML,直到 007 诊断才发现,期间一直没有任何解析检查。

本测试确保示例配置始终可解析,且教师 Agent / Sub-Agent 声明与设计一致:
- Skill 为 3 个(differentiated-practice 已下线);
- Sub-Agent 含诊断与一致性审核,practice-worker / reviewer 不再存在;
- eval-diagnoser 必须声明在 custom_agents 下(否则该块会再次成为孤儿)。
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = REPO_ROOT / "config.teacher-copilot.example.yaml"

# 当前设计:三 Skill(007 下线 differentiated-practice)
EXPECTED_SKILLS = ["student-diagnosis", "class-learning-analysis", "homework-review"]
# 必须存在的 Sub-Agent
REQUIRED_SUBAGENTS = {"diagnosis-worker", "consistency-reviewer", "eval-diagnoser"}
# 007 已移除的 Sub-Agent
REMOVED_SUBAGENTS = {"practice-worker", "reviewer"}


def _load() -> dict:
    """读取示例配置(解析失败会直接暴露为测试错误)。"""
    data = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "示例配置顶层应为映射"
    return data


def test_example_config_is_valid_yaml() -> None:
    """示例配置必须能被 YAML 解析。"""
    _load()


def test_example_config_teacher_agent_skills() -> None:
    """教师 Agent 的 Skill 声明应为当前三个。"""
    data = _load()
    agents = {a["name"]: a for a in data["agents"]}
    assert agents["teacher-copilot"]["skills"] == EXPECTED_SKILLS


def test_example_config_subagents_declaration() -> None:
    """Sub-Agent 声明:必需项在、已下线项不在。"""
    data = _load()
    custom = set(data["subagents"]["custom_agents"].keys())
    assert REQUIRED_SUBAGENTS <= custom, f"缺少必需 Sub-Agent: {REQUIRED_SUBAGENTS - custom}"
    assert not (REMOVED_SUBAGENTS & custom), f"仍存在已下线 Sub-Agent: {REMOVED_SUBAGENTS & custom}"
