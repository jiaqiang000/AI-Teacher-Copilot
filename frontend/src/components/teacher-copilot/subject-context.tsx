"use client";
// 学科作为"聚合视图的查询上下文"(008 FR-009)。
//
// 学科不是班级属性、也不是部署期配置:它写在 URL 查询参数里,刷新与分享链接都保持,
// 缺省数学。仅 01 工作台 / 02 班级画像 / 03 学生画像 / 09 班级总览 四个聚合视图使用;
// 04—08 是单份作业或单次提交页面,学科是对象自身属性,不提供切换。
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

import { useI18n } from "@/core/i18n/hooks";
import { subjectLabel } from "@/core/teacher-copilot/display-labels";
import type { Subject } from "@/core/teacher-copilot/types";

/** URL 查询参数键名(如 ?subject=math)。 */
export const SUBJECT_PARAM = "subject";

/** 系统当前支持的学科,与 types.Subject 保持一致。 */
export const SUBJECT_OPTIONS: readonly Subject[] = ["math", "english"];

/** 缺省学科。 */
export const DEFAULT_SUBJECT: Subject = "math";

function normalizeSubject(raw: string | null): Subject {
  return (SUBJECT_OPTIONS as readonly string[]).includes(raw ?? "")
    ? (raw as Subject)
    : DEFAULT_SUBJECT;
}

/** 读取当前所选学科(缺省数学),供页面作为查询上下文使用。 */
export function useSubjectParam(): Subject {
  const searchParams = useSearchParams();
  return normalizeSubject(searchParams.get(SUBJECT_PARAM));
}

/** 给跳转链接带上当前所选学科,避免跨页后学科被打回缺省。 */
export function withSubject(href: string, subject: Subject): string {
  const [path, query = ""] = href.split("?");
  const params = new URLSearchParams(query);
  params.set(SUBJECT_PARAM, subject);
  return `${path}?${params.toString()}`;
}

/** 学科切换控件:聚合视图右上角的学科标签(Figma「学科切换」状态帧)。 */
export function SubjectSwitcher() {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = normalizeSubject(searchParams.get(SUBJECT_PARAM));

  const onChange = useCallback(
    (next: string) => {
      // 切换即改写 URL:保留其他查询参数,用 replace 不污染浏览历史
      const params = new URLSearchParams(searchParams.toString());
      params.set(SUBJECT_PARAM, next);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  return (
    <label className="text-muted-foreground inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm">
      <span className="sr-only">选择学科</span>
      <select
        className="bg-transparent font-medium"
        value={current}
        onChange={(e) => onChange(e.target.value)}
      >
        {SUBJECT_OPTIONS.map((option) => (
          <option key={option} value={option}>
            {subjectLabel(option, t.teacherCopilot)}
          </option>
        ))}
      </select>
      <span aria-hidden="true" className="text-xs">
        ▾
      </span>
    </label>
  );
}

/** 空状态提示:所选学科在该对象下没有数据(008 FR-009、SC-006)。 */
export function SubjectEmptyState() {
  return (
    <section className="rounded-lg border border-dashed p-8 text-center">
      <p className="text-muted-foreground text-sm">该学科暂无数据</p>
    </section>
  );
}
