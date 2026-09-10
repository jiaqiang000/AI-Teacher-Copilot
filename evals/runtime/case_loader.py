"""评测用例文件读取(JSONL 约定:一行一条用例)。

集中在此避免多处重复实现漂移:此前 run.py 与 eval_world.py 各有一份读取逻辑,
其中一份跳过 `#` 注释行、另一份没有,导致 core_cases.jsonl 长期无法加载
(007 诊断发现:跨行格式与注释行两个缺陷叠加)。

约定:
- 一行一个 JSON 对象(JSONL),不使用跨行对象;
- 空行与 `#` 开头的注释行跳过;
- 解析失败时报出"文件名:行号",避免只抛笼统的 JSONDecodeError。
"""

from __future__ import annotations

import json
from pathlib import Path


def parse_cases(text: str, *, source: str = "<cases>") -> list[dict]:
    """把 JSONL 文本解析为用例列表。

    空行与 `#` 注释行跳过;某行不是合法 JSON 对象时抛 ValueError,
    并在消息中带上 `source:行号`,便于定位格式漂移。
    """
    cases: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{source}:{lineno} 用例解析失败: {exc}") from exc
        if not isinstance(obj, dict):
            raise ValueError(
                f"{source}:{lineno} 用例必须是 JSON 对象,实际为 {type(obj).__name__}"
            )
        cases.append(obj)
    return cases


def load_case_file(path: str | Path) -> list[dict]:
    """读取单个用例文件(如 core_cases.jsonl)。"""
    p = Path(path)
    return parse_cases(p.read_text(encoding="utf-8"), source=p.name)


def load_case_dir(cases_dir: str | Path) -> list[dict]:
    """读取目录下全部 .jsonl 用例,按文件名排序累加。"""
    d = Path(cases_dir)
    if not d.is_dir():
        return []
    cases: list[dict] = []
    for path in sorted(d.glob("*.jsonl")):
        cases.extend(load_case_file(path))
    return cases
