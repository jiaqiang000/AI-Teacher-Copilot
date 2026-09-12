"use client";
// 学生批改页(对照 Figma 08:题目/答案卡 + 五步进度 + 批改结果)
// 真实流程:选图上传(OSS)→ POST /submissions → 轮询进度 → 批改结果
import { CheckIcon, CircleIcon, LoaderCircleIcon } from "lucide-react";
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
  // 后端记录的批改失败详情:直接展示后端内容,不做失败码到友好文案的映射(FR-004a)
  const [failure, setFailure] = useState<{
    code: string | null;
    message: string | null;
  } | null>(null);

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
    setFailure(null);
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
        // 失败详情取自后端已存字段,替换写死的通用提示(FR-004a)
        if (sub.status === "FAILED") {
          setFailure({ code: sub.error_code, message: sub.error_message });
        }
        if (sub.status === "SUCCEEDED")
          await refreshResult(currentSubmissionId);
      } catch {
        /* 轮询失败下一轮重试 */
      }
    }
    const timer = setInterval(() => void pollSubmission(), 3000);
    return () => clearInterval(timer);
  }, [submissionId, status, refreshResult]);

  // 刷新后恢复的历史失败提交不会进入轮询,单独补拉一次失败详情(FR-004a)
  useEffect(() => {
    if (!submissionId || status !== "FAILED" || failure) return;
    let cancelled = false;
    void (async () => {
      try {
        const sub = await getSubmission(submissionId);
        if (!cancelled) {
          setFailure({ code: sub.error_code, message: sub.error_message });
        }
      } catch {
        /* 取不到详情时只显示“批改失败”,不编造失败原因 */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [submissionId, status, failure]);

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
      setFailure(null);
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
  const isRunning = !isTerminal;
  // 失败详情直接拼接后端记录的内容(code/message),不建立文案映射表(FR-004a)
  const failureText = failure
    ? [failure.code, failure.message].filter(Boolean).join(":")
    : "";

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
                    <span className="flex size-4 shrink-0 items-center justify-center">
                      {/* 阶段图标只反映已有提交状态：当前运行阶段旋转，已完成阶段静态勾选。 */}
                      {i < stageIndex ? (
                        <CheckIcon
                          aria-hidden="true"
                          className="size-4 text-emerald-600"
                        />
                      ) : isRunning && i === stageIndex ? (
                        <LoaderCircleIcon
                          aria-hidden="true"
                          className="text-primary size-4 animate-spin"
                        />
                      ) : (
                        <CircleIcon
                          aria-hidden="true"
                          className="text-muted-foreground size-4"
                        />
                      )}
                    </span>
                    {stageLabel(key, t.teacherCopilot)}
                  </li>
                ))}
              </ul>
              {status === "FAILED" && (
                <p className="mt-2 text-sm text-red-600">
                  {failureText ? `批改失败：${failureText}` : "批改失败"}
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
      {/* 历史批改里 summary 可能为空(当时数学 prompt 没要求它),显式说明而不是留白行 */}
      <p className="mt-2 text-sm">{result.feedback.summary || "暂无评语"}</p>
      {/* 优点 / 改进建议:后端一直有这两个字段,此前界面从未展示(008 T040)。
          按"可能不完整"读:历史数据里存在 feedback={} 的行,直接 .length 会打崩页面(008 T044) */}
      {(result.feedback.strengths ?? []).length > 0 && (
        <p className="text-muted-foreground mt-1 text-xs">
          优点:{(result.feedback.strengths ?? []).join(";")}
        </p>
      )}
      {(result.feedback.improvements ?? []).length > 0 && (
        <p className="text-muted-foreground mt-1 text-xs">
          改进建议:{(result.feedback.improvements ?? []).join(";")}
        </p>
      )}
      {result.math_detail && (
        <ul className="mt-3 space-y-1 text-sm">
          {result.math_detail.steps.map((s) => (
            <li key={s.step_index} className="border-b py-1">
              <div className="flex justify-between">
                <span>{s.description}</span>
                <span className="text-muted-foreground">
                  {stepStatusLabel(s.status, labels)} · {s.earned_score}/
                  {s.max_score}
                </span>
              </div>
              {/* 每步评语:模型一直在产出,此前界面只显示总评语、把它丢掉了(008 T040) */}
              {s.feedback && (
                <p className="text-muted-foreground mt-0.5 text-xs">
                  {s.feedback}
                </p>
              )}
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
