#!/usr/bin/env python3
"""提交信息自查(宪法 XIII)。

用法:
    python scripts/check_commit_msg.py                 # 检查 HEAD 的提交信息
    python scripts/check_commit_msg.py --range A..B     # 检查区间内每个提交
    python scripts/check_commit_msg.py --message-file F # 检查文件内容(供 commit-msg 钩子)
    python scripts/check_commit_msg.py --specs-dir P    # 指定 specs/ 目录(默认自动探测)

只做机械可判定的部分,语义质量仍需人保证:
1. 首行格式:`<spec 标识> <任务号>：…` / `<spec 标识> 收口：…` / `chore：…`;
2. 首行必须是中文,且不得是"修复bug""优化"这类无信息量表述;
3. spec 标识必须对应 specs/ 下真实存在的功能目录(探测不到 specs/ 时跳过该项);
4. 五要素段落齐全且都不为空:【溯源】【原因】【改动】【验证】【影响与后续】;
5. 【溯源】里必须同时出现 spec 与 task;
6. 【验证】段落内不得出现"应该没问题""理论上可行"这类无法证实的措辞。

退出码:0 全部通过;1 存在不合规项;2 用法或环境错误。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 首行语法:三种合法形态(带任务号 / 收口 / 仓库维护)
_SPEC_ID = r"\d{3}-[a-z0-9][a-z0-9-]*"
_TITLE_RE = re.compile(
    r"^(?:"
    rf"(?P<spec>{_SPEC_ID}) (?P<task>T\d{{3}}(?:、T\d{{3}})*|无)"
    rf"|(?P<close>{_SPEC_ID}) 收口"
    r"|(?P<chore>chore)"
    r")：\S"
)

# 无信息量首行(去掉空格后比对)
_MEANINGLESS = {
    "修复bug",
    "修复问题",
    "优化",
    "优化代码",
    "更新",
    "修改",
    "调整",
    "fix",
    "fixbug",
    "update",
}

# 无法证实的措辞:出现即视为"未验证却当成已验证"
_VAGUE = ("应该没问题", "应该可以", "应该能", "理论上可行", "理论上应该", "大概没问题", "估计没问题")

# 五要素段落(原则 XIII 规定,缺一不可且不得为空)
_SECTIONS = ("【溯源】", "【原因】", "【改动】", "【验证】", "【影响与后续】")


def _resolve_specs_dir(explicit: str | None) -> Path | None:
    """定位 specs/ 目录:显式指定优先,否则按脚本位置向上探测,找不到返回 None。"""
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_dir() else None
    # scripts/ 位于仓库内,specs/ 通常在其上一级(本项目 specs/ 与仓库平级)
    for base in Path(__file__).resolve().parents:
        candidate = base / "specs"
        if candidate.is_dir():
            return candidate
    return None


def _git_messages(rev_range: str | None) -> list[tuple[str, str]]:
    """读取待检查的提交信息,返回 [(短 sha, 正文)]。"""
    fmt = "%H%x1f%B%x1e"
    cmd = ["git", "log", f"--format={fmt}", rev_range or "-1"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git log 执行失败: {result.stderr.strip()}")
    messages: list[tuple[str, str]] = []
    for record in result.stdout.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        sha, _, body = record.partition("\x1f")
        messages.append((sha.strip()[:12], body.strip("\n")))
    return messages


def _has_cjk(text: str) -> bool:
    """是否含中日韩统一表意文字(用于判断"首行必须中文")。"""
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _is_marker_line(line: str) -> str | None:
    """该行是否为五要素段落标记行,是则返回标记。

    只认"行首即标记"的行:列表项里的 `- 【验证】…` 属于正文引用,不算段落起点——
    否则一段解释"这条禁令作用于哪个段落"的文字会被误判成新段落的开始。
    """
    stripped = line.strip()
    if stripped.startswith(("-", "*", "+")):
        return None
    for marker in _SECTIONS:
        if stripped.startswith(marker):
            return marker
    return None


def _split_sections(body: str) -> dict[str, str]:
    """把提交信息正文按行首段落标记切分,返回 ``{标记: 该段内容}``。"""
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for line in body.splitlines():
        marker = _is_marker_line(line)
        if marker is not None:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = marker
            buffer = [line.strip()[len(marker):]]
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def _check_one(label: str, message: str, specs_dir: Path | None) -> list[str]:
    """检查单个提交信息,返回问题清单(空表示通过)。"""
    problems: list[str] = []
    lines = message.splitlines()
    title = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""

    # 1) 首行格式
    match = _TITLE_RE.match(title)
    if not match:
        problems.append(
            "首行格式不合规。应为 `<spec 标识> <任务号>：说明`(例:008-remove-silent-mocks "
            "T040、T041：…),或 `<spec 标识> 收口：…`,或 `chore：…`;"
            "任务号多个用顿号分隔"
        )
    else:
        # 2) spec 目录必须真实存在
        spec_id = match.group("spec") or match.group("close")
        if spec_id and specs_dir is not None:
            if not (specs_dir / spec_id).is_dir():
                problems.append(
                    f"spec 标识 `{spec_id}` 在 {specs_dir} 下不存在;请填写真实的 spec 目录名"
                )

    # 3) 首行必须是中文且不得无信息量
    if not _has_cjk(title):
        problems.append("首行必须使用中文")
    summary = title.split("：", 1)[1] if "：" in title else title
    if summary.replace(" ", "").lower() in _MEANINGLESS:
        problems.append(f"首行说明无信息量(`{summary}`):请写清做了什么 + 达到什么效果")

    # 4) 五要素段落齐全且都不为空
    sections = _split_sections(body)
    for marker in _SECTIONS:
        if marker not in sections:
            problems.append(f"缺少段落 {marker}")
        elif not sections[marker].strip():
            problems.append(f"段落 {marker} 内容为空;不适用时请显式写\"无\"或\"不适用(原因:…)\"")

    # 5) 【溯源】必须同时给出 spec 与 task
    trace = sections.get("【溯源】", "")
    for keyword in ("spec", "task"):
        if trace and keyword not in trace.lower():
            problems.append(f"【溯源】缺少 `{keyword}`,须写明属于哪个 spec、哪些任务号")

    # 6) 禁止无法证实的措辞
    # 只在【验证】段内检查:该禁令针对的是"声称已验证"的表述,而这条表述本身需要在
    # 别处被引用(宪法条文、本脚本说明、讨论该规则的提交),全文匹配会造成元引用假阳性
    verify = sections.get("【验证】", "")
    for phrase in _VAGUE:
        if phrase in verify:
            problems.append(
                f"【验证】出现无法证实的措辞 `{phrase}`;无法证实即视为未验证,须写清实际情况"
            )

    return problems


def main() -> int:
    """CLI 入口:逐个提交检查并汇总输出。"""
    parser = argparse.ArgumentParser(
        description="按宪法 XIII 自查提交信息(机械可判定部分)",
    )
    parser.add_argument("--range", dest="rev_range", help="检查 git 区间,如 main..HEAD")
    parser.add_argument("--message-file", help="直接检查该文件内容(供 commit-msg 钩子)")
    parser.add_argument("--specs-dir", help="specs/ 目录路径(默认自动探测)")
    args = parser.parse_args()

    if args.message_file:
        text = Path(args.message_file).read_text(encoding="utf-8")
        messages = [(Path(args.message_file).name, text.strip("\n"))]
    else:
        try:
            messages = _git_messages(args.rev_range)
        except RuntimeError as exc:
            print(f"错误:{exc}", file=sys.stderr)
            return 2

    if not messages:
        print("没有需要检查的提交。", file=sys.stderr)
        return 2

    specs_dir = _resolve_specs_dir(args.specs_dir)
    if specs_dir is None:
        print("提示:未探测到 specs/ 目录,跳过\"spec 标识是否存在\"的检查。", file=sys.stderr)

    failed = 0
    for label, message in messages:
        problems = _check_one(label, message, specs_dir)
        if problems:
            failed += 1
            print(f"✗ {label}")
            for item in problems:
                print(f"    - {item}")
        else:
            print(f"✅ {label} 通过")

    print(f"\n共检查 {len(messages)} 个提交,不合规 {failed} 个。")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
