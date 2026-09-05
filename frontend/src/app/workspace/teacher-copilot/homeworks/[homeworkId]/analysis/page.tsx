"use client"
// 作业分析(对照 Figma 05):按 homeworkId 展示分析,题目行可进入同一作业的下钻视图。
import Link from "next/link"
import { useParams, useSearchParams } from "next/navigation"
import { useEffect, useState } from "react"

import { WorkspaceHeader } from "@/components/workspace/workspace-container"
import { useI18n } from "@/core/i18n/hooks"
import {
  getHomework,
  getHomeworkAnalysis,
  getQuestionAnalysis,
} from "@/core/teacher-copilot/api"
import {
  errorTypeLabel,
  knowledgePointLabel,
  subjectLabel,
  type TeacherCopilotLabels,
} from "@/core/teacher-copilot/display-labels"

type Homework = Awaited<ReturnType<typeof getHomework>>
type Analysis = Awaited<ReturnType<typeof getHomeworkAnalysis>>
type QuestionDetail = Awaited<ReturnType<typeof getQuestionAnalysis>>

export default function AnalysisPage() {
  const { t } = useI18n()
  const { homeworkId } = useParams<{ homeworkId: string }>()
  const searchParams = useSearchParams()
  const requestedClassId = searchParams.get("class_id") ?? ""
  const questionId = searchParams.get("question_id") ?? ""
  const [homework, setHomework] = useState<Homework | null>(null)
  const [data, setData] = useState<Analysis | null>(null)
  const [questionDetail, setQuestionDetail] = useState<QuestionDetail | null>(null)
  const [resolvedClassId, setResolvedClassId] = useState(requestedClassId)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [questionError, setQuestionError] = useState("")

  useEffect(() => {
    let active = true
    setLoading(true)
    setError("")
    setHomework(null)
    setData(null)
    void (async () => {
      try {
        const nextHomework = await getHomework(homeworkId)
        const classId = requestedClassId || nextHomework.class_id
        const nextAnalysis = await getHomeworkAnalysis(homeworkId, classId)
        if (!active) return
        setHomework(nextHomework)
        setResolvedClassId(classId)
        setData(nextAnalysis)
      } catch (e) {
        if (active) setError((e as Error).message)
      } finally {
        if (active) setLoading(false)
      }
    })()
    return () => {
      active = false
    }
  }, [homeworkId, requestedClassId])

  useEffect(() => {
    if (!questionId) {
      setQuestionDetail(null)
      setQuestionError("")
      return
    }
    const selected = data?.questions.find((question) => question.question_id === questionId)
    if (!selected || !resolvedClassId) {
      setQuestionDetail(null)
      setQuestionError("题目不存在或与当前作业不匹配")
      return
    }
    let active = true
    setQuestionDetail(null)
    setQuestionError("")
    void getQuestionAnalysis(questionId, homeworkId, resolvedClassId)
      .then((detail) => {
        if (active) setQuestionDetail(detail)
      })
      .catch((e) => {
        if (active) setQuestionError((e as Error).message)
      })
    return () => {
      active = false
    }
  }, [data, homeworkId, questionId, resolvedClassId])

  const questions = data?.questions ?? []
  const selectedQuestion = questions.find((question) => question.question_id === questionId)
  const backHref = `/workspace/teacher-copilot/homeworks/${homeworkId}/analysis?class_id=${resolvedClassId}`
  const highestErrorQuestion = [...questions]
    .filter((question) => question.error_rate != null)
    .sort((left, right) => (right.error_rate ?? -1) - (left.error_rate ?? -1))[0]

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-6 p-4 sm:p-8">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">
              {questionId
                ? `第 ${questionDetail?.question_no ?? selectedQuestion?.question_no ?? "-"} 题 · 题目详情`
                : `${homework?.name ?? homeworkId} · 作业分析`}
            </h1>
            <p className="text-muted-foreground text-sm">
              {homework?.class_id ?? resolvedClassId} · {subjectLabel(homework?.subject ?? "math", t.teacherCopilot)}
            </p>
          </div>
          <Link href="/workspace/teacher-copilot/homeworks" className="rounded border px-3 py-1.5 text-sm hover:bg-gray-50">
            返回作业管理
          </Link>
        </header>

        {loading && <p className="text-muted-foreground text-sm">正在加载作业分析...</p>}
        {!loading && error && (
          <section className="rounded-lg border border-red-200 p-4 text-sm text-red-600">
            加载失败: {error}
          </section>
        )}
        {!loading && !error && data && (
          questionId ? (
            <QuestionDetailView
              detail={questionDetail}
              selectedQuestion={selectedQuestion}
              error={questionError}
              backHref={backHref}
              labels={t.teacherCopilot}
            />
          ) : (
            <AnalysisOverview
              data={data}
              highestErrorQuestion={highestErrorQuestion}
              homeworkId={homeworkId}
              classId={resolvedClassId}
              labels={t.teacherCopilot}
            />
          )
        )}
      </main>
    </div>
  )
}

function AnalysisOverview({
  data,
  highestErrorQuestion,
  homeworkId,
  classId,
  labels,
}: {
  data: Analysis
  highestErrorQuestion: Analysis["questions"][number] | undefined
  homeworkId: string
  classId: string
  labels: TeacherCopilotLabels
}) {
  const completion = data.completion
  const perf = data.performance
  const dist = perf.score_distribution

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="完成率"
          value={completion.completion_rate != null ? `${Math.round(completion.completion_rate * 100)}%` : "—"}
          sub={`${completion.submitted_student_count}/${completion.assigned_student_count}`}
        />
        <Stat label="完整批改" value={String(perf.graded_student_count)} sub="学生" />
        <Stat
          label="平均得分率"
          value={perf.avg_score_rate != null ? `${Math.round(perf.avg_score_rate * 100)}%` : "—"}
          sub="有效批改结果"
        />
        <Stat
          label="最高错题"
          value={highestErrorQuestion ? `第 ${highestErrorQuestion.question_no} 题` : "—"}
          sub={highestErrorQuestion?.error_rate != null ? `错误率 ${Math.round(highestErrorQuestion.error_rate * 100)}%` : "暂无数据"}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-2 text-lg font-semibold">成绩分布</h2>
          <p className="text-muted-foreground mb-2 text-xs">按完整批改学生统计</p>
          {dist ? (
            <ul className="space-y-1 text-sm">
              <li>&lt;60&nbsp;&nbsp;{dist.below_60} 人</li>
              <li>60-79&nbsp;&nbsp;{dist.from_60_to_79} 人</li>
              <li>80-89&nbsp;&nbsp;{dist.from_80_to_89} 人</li>
              <li>90-100&nbsp;&nbsp;{dist.from_90_to_100} 人</li>
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">暂无数据</p>
          )}
        </section>
        <section>
          <h2 className="mb-2 text-lg font-semibold">本次低表现知识点</h2>
          <p className="text-muted-foreground mb-2 text-xs">即时分析,不等同于长期薄弱点</p>
          {data.knowledge_points.length === 0 ? (
            <p className="text-muted-foreground text-sm">无</p>
          ) : (
            data.knowledge_points.slice(0, 3).map((knowledgePoint) => (
              <div key={knowledgePoint.knowledge_point_key} className="mb-2 rounded border px-3 py-2 text-sm">
                {knowledgePointLabel(knowledgePoint.knowledge_point_name, labels)} · {labels.averagePerformance} {knowledgePoint.avg_performance != null ? Math.round(knowledgePoint.avg_performance * 100) : "—"}%
              </div>
            ))
          )}
        </section>
      </div>

      <section>
        <h2 className="mb-2 text-lg font-semibold">题目表现</h2>
        <p className="text-muted-foreground mb-2 text-xs">点击有有效作答的题目进入{labels.questionAnalysis}</p>
        {data.questions.length === 0 ? (
          <p className="text-muted-foreground text-sm">暂无题目</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {data.questions.map((question) => {
              const content = (
                <>
                  <span>第 {question.question_no} 题</span>
                  <span className="text-muted-foreground">
                    {question.attempt_count > 0
                      ? `错误率 ${question.error_rate != null ? `${Math.round(question.error_rate * 100)}%` : "—"}${question.common_errors[0] ? ` · ${errorTypeLabel(question.common_errors[0].error_name, labels)}` : ""}`
                      : "暂无有效作答"}
                  </span>
                </>
              )
              return question.attempt_count > 0 ? (
                <li key={question.question_id}>
                  <Link
                    href={`/workspace/teacher-copilot/homeworks/${homeworkId}/analysis?class_id=${classId}&question_id=${question.question_id}`}
                    className="flex items-center justify-between gap-3 rounded border px-3 py-2 hover:bg-gray-50"
                  >
                    {content}
                  </Link>
                </li>
              ) : (
                <li key={question.question_id} className="flex items-center justify-between gap-3 rounded border px-3 py-2">
                  {content}
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </>
  )
}

function QuestionDetailView({
  detail,
  selectedQuestion,
  error,
  backHref,
  labels,
}: {
  detail: QuestionDetail | null
  selectedQuestion: Analysis["questions"][number] | undefined
  error: string
  backHref: string
  labels: TeacherCopilotLabels
}) {
  if (error) {
    return (
      <section className="rounded-lg border border-red-200 p-4 text-sm text-red-600">
        <p>{error}</p>
        <Link className="mt-3 inline-block underline-offset-2 hover:underline" href={backHref}>
          返回作业分析
        </Link>
      </section>
    )
  }
  if (!detail) {
    return <p className="text-muted-foreground text-sm">正在加载题目分析...</p>
  }

  return (
    <section className="space-y-4">
      <Link href={backHref} className="inline-block text-sm underline-offset-2 hover:underline">
        ← 返回作业分析
      </Link>
      <div className="rounded-lg border p-4">
        <h2 className="mb-2 font-semibold">题干</h2>
        <p className="whitespace-pre-wrap text-sm">{detail.content}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="作答人数" value={String(detail.attempt_count)} sub="有效提交" />
        <Stat label="平均得分率" value={detail.avg_score_rate != null ? `${Math.round(detail.avg_score_rate * 100)}%` : "—"} sub="本题" />
        <Stat label="错误人数" value={String(detail.error_student_count)} sub="有诊断错误" />
        <Stat label="错误率" value={detail.error_rate != null ? `${Math.round(detail.error_rate * 100)}%` : "—"} sub="本题" />
      </div>
      <div className="rounded-lg border p-4">
        <h2 className="mb-2 font-semibold">共性错误</h2>
        {detail.common_errors.length === 0 ? (
          <p className="text-muted-foreground text-sm">暂无共性错误</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {detail.common_errors.map((item) => (
              <li key={`${item.error_code}-${item.knowledge_point_key}`} className="rounded border px-3 py-2">
                {errorTypeLabel(item.error_name, labels)} · {item.affected_student_count} 人 · {knowledgePointLabel(item.knowledge_point_name, labels)}
              </li>
            ))}
          </ul>
        )}
      </div>
      {selectedQuestion && detail.question_no !== selectedQuestion.question_no && (
        <p className="text-sm text-red-600">题目编号与入口不一致,请返回后重试。</p>
      )}
    </section>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-muted-foreground text-sm">{label}</div>
      <div className="my-1 text-2xl font-bold">{value}</div>
      <div className="text-muted-foreground text-xs">{sub}</div>
    </div>
  )
}
