"""对外输出形状归一(HTTP 路由与 Agent 工具共用)。

同一份业务数据往往经多个出口暴露给不同消费方(学生/教师 HTTP 接口、Agent 工具)。
各出口自己拼装字段极易漂移:历史上 ``feedback`` 就只在一个出口做了补齐,另两个
仍原样返回,导致同一份数据形状不一致(008 T046)。

约定:凡要把某类业务对象暴露出去的出口,MUST 复用本模块的归一函数,不要各自拼装;
新增出口若忘了复用,消费方就会重新面对"形状不确定"的老问题。
"""

from __future__ import annotations


def normalize_feedback(raw: object) -> dict:
    """把 ``GradingResult.feedback`` 归一成稳定形状。

    历史数据里存在 ``{}``(实测 1092 条里有 1089 条):早期写入时未补齐字段。
    缺失字段一律补空串 / 空数组,使所有消费方拿到的形状一致,不必各自防御——
    前端曾按"三字段必有"读 ``strengths.length``,在这些行上抛 TypeError 打崩页面。

    只归一"读出来的样子",不改数据库里的既有行(FR-013)。
    """
    fb = raw if isinstance(raw, dict) else {}
    summary = fb.get("summary")
    strengths = fb.get("strengths")
    improvements = fb.get("improvements")
    return {
        "summary": summary if isinstance(summary, str) else "",
        "strengths": list(strengths) if isinstance(strengths, list) else [],
        "improvements": list(improvements) if isinstance(improvements, list) else [],
    }
