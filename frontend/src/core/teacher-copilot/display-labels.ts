"use client";

// 教师业务页面的有限枚举展示转换；分类名称由后端从业务字典提供。
import type { Translations } from "@/core/i18n/locales";

export type TeacherCopilotLabels = Translations["teacherCopilot"];

function labelFrom(
  value: string | null | undefined,
  labels: Record<string, string>,
  fallback: string,
) {
  if (!value) return fallback;
  return labels[value] ?? `${fallback}（${value}）`;
}

export function subjectLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return labelFrom(value, labels.subjects, labels.unknownSubject);
}

export function statusLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return labelFrom(value, labels.statuses, labels.unknownStatus);
}

export function stageLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return labelFrom(value, labels.stages, labels.unknownStage);
}

export function questionTypeLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return labelFrom(value, labels.questionTypes, labels.unknownQuestionType);
}

export function difficultyLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  if (!value) return "—";
  return labelFrom(value, labels.difficulties, labels.unknownDifficulty);
}

export function trendLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return labelFrom(value, labels.trends, labels.unknownTrend);
}

export function stepStatusLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return labelFrom(value, labels.stepStatuses, labels.unknownStepStatus);
}

export function reasonLabels(values: string[], labels: TeacherCopilotLabels) {
  return values.map((value) =>
    labelFrom(value, labels.reasons, labels.unknownReason),
  );
}

export function knowledgePointLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return value ?? labels.unknownKnowledgePoint;
}

export function errorTypeLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  return value ?? labels.unknownErrorType;
}

export function algorithmVersionLabel(
  value: string | null | undefined,
  labels: TeacherCopilotLabels,
) {
  if (value === "profile_v1" || value === "ProfileAlgorithmV1") {
    return labels.algorithmVersion;
  }
  return value ?? "—";
}
