"use client";
// 学生批改页(对照 Figma 08:题目/答案卡 + 五步进度 + 批改结果)
// 真实流程:选图上传(OSS)→ POST /submissions → 轮询进度 → 批改结果
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useI18n } from "@/core/i18n/hooks";
import {
  getGradingResult,
  getStudentHomework,
  getSubmission,
  submitAnswer,
  uploadImage,
} from "@/core/teacher-copilot/api";
import {
  difficultyLabel,
  stageLabel,
  statusLabel,
  stepStatusLabel,
} from "@/core/teacher-copilot/display-labels";
import type { GradingResult } from "@/core/teacher-copilot/types";

const STAGE_KEYS = ["UPLOAD", "OCR", "PARSING", "GRADING", "ASSEMBLING"];

export default function StudentGradingPage() {
  const { t } = useI18n();
  const params = useSearchParams();
  const homeworkId = params.get("homework_id") ?? "";
  const questionId = params.get("question_id") ?? "";

  const [question, setQuestion] = useState<
    Awaited<ReturnType<typeof getStudentHomework>>["questions"][number] | null
  >(null);
  const [submissionId, setSubmissionId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");
  const [stage, setStage] = useState<string>("");
  const [result, setResult] = useState<GradingResult | null>(null);
  const [uploadedUrl, setUploadedUrl] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pageError, setPageError] = useState("");

  const refreshResult = useCallback(async (sid: string) => {
    try {
      const r = await getGradingResult(sid);
      setResult(r);
    } catch {
      /* 结果尚未生成时忽略 */
    }
  }, []);

  // 载入作业题目 + 已有提交
  const loadView = useCallback(async () => {
    setPageError("");
    setError("");
    setQuestion(null);
    if (!homeworkId || !questionId) {
      setPageError("作业和题目不能为空");
      return;
    }
    try {
      const data = await getStudentHomework(homeworkId);
      if (data.homework.homework_id !== homeworkId) {
        throw new Error("作业与请求对象不匹配");
      }
      const q = data.questions.find((it) => it.question_id === questionId);
      if (!q) {
        throw new Error("题目不存在或不属于该作业");
      }
      setQuestion(q);
      if (q.my_submission) {
        setSubmissionId(q.my_submission.submission_id);
        setStatus(q.my_submission.status);
        setStage(q.my_submission.current_stage);
        if (q.my_submission.status === "SUCCEEDED") {
          await refreshResult(q.my_submission.submission_id);
        }
      }
    } catch (e) {
      setPageError((e as Error).message);
    }
  }, [homeworkId, questionId, refreshResult]);

  useEffect(() => {
    void loadView();
  }, [loadView]);

  // 提交后轮询进度(复盘恢复;V1 契约亦支持 SSE events 流)
  useEffect(() => {
    if (!submissionId || status === "SUCCEEDED" || status === "FAILED") return;
    const currentSubmissionId = submissionId;
    async function pollSubmission() {
      try {
        const sub = await getSubmission(currentSubmissionId);
        setStatus(sub.status);
        setStage(sub.current_stage);
        if (sub.status === "SUCCEEDED")
          await refreshResult(currentSubmissionId);
      } catch {
        /* 轮询失败下一轮重试 */
      }
    }
    const timer = setInterval(() => void pollSubmission(), 3000);
    return () => clearInterval(timer);
  }, [submissionId, status, refreshResult]);

  async function handleUpload(file: File) {
    if (!homeworkId || question?.question_id !== questionId) {
      setError("当前题目无效,无法提交答案");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const url = await uploadImage(file);
      const res = await submitAnswer({
        question_id: questionId,
        homework_id: homeworkId,
        image_url: url,
      });
      // 只有提交接口接受后才展示“已上传并提交”,上传成功不代表业务提交成功。
      setUploadedUrl(url);
      setSubmissionId(res.submission_id);
      setStatus(res.status);
      setStage(res.current_stage);
      setResult(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const stageIndex =
    status === "SUCCEEDED"
      ? STAGE_KEYS.length
      : STAGE_KEYS.findIndex((key) => key === stage);
  const isTerminal = status === "SUCCEEDED" || status === "FAILED";

  return (
    <div className="max-w-3xl space-y-5 p-4 sm:p-8">
      <header>
        <h1 className="text-2xl font-bold">
          第 {question?.question_no ?? "-"} 题
          {question?.difficulty
            ? ` · ${difficultyLabel(question.difficulty, t.teacherCopilot)}`
            : ""}
        </h1>
        <p className="text-muted-foreground text-sm">
          上传一张图片 = 一道题 · 由 AI Teacher 批改
        </p>
      </header>

      {pageError ? (
        <section className="rounded-lg border border-red-200 p-4 text-sm text-red-600">
          <p>{pageError}</p>
          <a
            className="mt-3 inline-block underline-offset-2 hover:underline"
            href={`/workspace/teacher-copilot/student/homework${homeworkId ? `?homework_id=${homeworkId}` : ""}`}
          >
            返回我的作业
          </a>
        </section>
      ) : (
        <>
          <section className="rounded-lg border p-4">
            <h2 className="mb-1 text-sm font-semibold">题目</h2>
            <p className="text-sm whitespace-pre-wrap">
              {question?.content ?? "加载中..."}
            </p>
          </section>

          <section className="rounded-lg border p-4">
            <h2 className="mb-2 text-sm font-semibold">你的答案</h2>
            {(!submissionId || isTerminal) && (
              <label className="text-muted-foreground block cursor-pointer rounded border border-dashed p-4 text-center text-sm hover:bg-gray-50">
                {busy
                  ? "上传中..."
                  : submissionId
                    ? "重新选择作答图片并提交(jpg/png, ≤10MB)"
                    : "选择手写作答图片上传(jpg/png, ≤10MB)"}
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) void handleUpload(f);
                  }}
                />
              </label>
            )}
            {(uploadedUrl || submissionId) && (
              <p className="text-muted-foreground text-sm">
                {uploadedUrl
                  ? isTerminal
                    ? "✚ 当前作答已完成,可重新提交新图片"
                    : "✚ 作答图片已上传并提交批改"
                  : `✚ 已提交(${submissionId})`}
              </p>
            )}
          </section>

          {submissionId && (
            <section className="rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">
                  AI Teacher · {statusLabel(status, t.teacherCopilot)}
                </h2>
                <span className="text-muted-foreground text-xs">
                  状态：{statusLabel(status, t.teacherCopilot)} · 阶段：
                  {stageLabel(stage, t.teacherCopilot)}
                </span>
              </div>
              <ul className="mt-3 space-y-1 text-sm">
                {STAGE_KEYS.map((key, i) => (
                  <li key={key} className="flex items-center gap-2">
                    <span className="w-4">
                      {i < stageIndex ? "✓" : i === stageIndex ? "●" : "○"}
                    </span>
                    {stageLabel(key, t.teacherCopilot)}
                  </li>
                ))}
              </ul>
              {status === "FAILED" && (
                <p className="mt-2 text-sm text-red-600">
                  批改失败,请上传重试。
                </p>
              )}
            </section>
          )}

          <section className="rounded-lg border p-4">
            <h2 className="mb-2 font-semibold">
              批改结果{result ? "" : "(完成后展示)"}
            </h2>
            {result ? (
              <ResultView result={result} labels={t.teacherCopilot} />
            ) : (
              <p className="text-muted-foreground text-sm">
                批改完成后展示结果(数学步骤分与错误定位)
              </p>
            )}
          </section>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </>
      )}
    </div>
  );
}

function ResultView({
  result,
  labels,
}: {
  result: GradingResult;
  labels: ReturnType<typeof useI18n>["t"]["teacherCopilot"];
}) {
  return (
    <div>
      <div className="text-3xl font-bold">
        {result.score.earned} / {result.score.max}
        <span className="text-muted-foreground ml-2 text-sm">
          ({Math.round(result.score.rate * 100)}%)
        </span>
      </div>
      <p className="mt-2 text-sm">{result.feedback.summary}</p>
      {result.math_detail && (
        <ul className="mt-3 space-y-1 text-sm">
          {result.math_detail.steps.map((s) => (
            <li
              key={s.step_index}
              className="flex justify-between border-b py-1"
            >
              <span>{s.description}</span>
              <span className="text-muted-foreground">
                {stepStatusLabel(s.status, labels)} · {s.earned_score}/
                {s.max_score}
              </span>
            </li>
          ))}
        </ul>
      )}
      {result.english_essay_detail && (
        <ul className="mt-3 space-y-1 text-sm">
          {Object.entries(result.english_essay_detail.dimension_scores).map(
            ([k, v]) => (
              <li key={k} className="flex justify-between border-b py-1">
                <span>{k}</span>
                <span>
                  {v.score}/{v.max_score}
                </span>
              </li>
            ),
          )}
        </ul>
      )}
    </div>
  );
}
