"use client";
// 作业创建(对照 Figma 04:作业信息 + 添加题目三来源 + 题目列表 + 发布)
// 交互:手动输入/上传图片(OCR 预填)/题库选择;数学难度预判确认;发布校验
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { WorkspaceHeader } from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import {
  addQuestion,
  createHomework,
  getHomework,
  getTeacherClasses,
  publishHomework,
  recognizeQuestionImage,
  searchQuestionBank,
  uploadImage,
} from "@/core/teacher-copilot/api";
import {
  difficultyLabel,
  questionTypeLabel,
  statusLabel,
  subjectLabel,
} from "@/core/teacher-copilot/display-labels";

type QuestionDraft = {
  question_id?: string;
  question_type: string;
  content: string;
  max_score: number;
  difficulty?: string | null;
};

export default function AuthoringPage() {
  const { t } = useI18n();
  const { homeworkId: routeHomeworkId } = useParams<{ homeworkId: string }>();
  const isNewHomework = routeHomeworkId === "new";
  const [homeworkId, setHomeworkId] = useState<string | null>(
    isNewHomework ? null : routeHomeworkId,
  );
  const [classes, setClasses] = useState<
    Awaited<ReturnType<typeof getTeacherClasses>>
  >([]);
  const [classId, setClassId] = useState("");
  const [subject, setSubject] = useState("math");
  const [questions, setQuestions] = useState<QuestionDraft[]>([]);
  const [name, setName] = useState(isNewHomework ? "八年级数学周末作业" : "");
  const [content, setContent] = useState("");
  const [qtype, setQtype] = useState("calculation");
  const [maxScore, setMaxScore] = useState(10);
  const [difficulty, setDifficulty] = useState("easy");
  const [homeworkStatus, setHomeworkStatus] = useState("");
  const [publishHint, setPublishHint] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getTeacherClasses()
      .then(setClasses)
      .catch((e) => setError((e as Error).message));
  }, []);

  useEffect(() => {
    if (isNewHomework) return;
    getHomework(routeHomeworkId)
      .then((homework) => {
        setHomeworkId(homework.homework_id);
        setHomeworkStatus(homework.status);
        setClassId(homework.class_id);
        setSubject(homework.subject);
        setName(homework.name);
        setQuestions(homework.questions);
      })
      .catch((e) => setError((e as Error).message));
  }, [isNewHomework, routeHomeworkId]);

  const selectedClass = classes.find((item) => item.class_id === classId);

  async function handleCreate() {
    setError("");
    if (!classId) {
      setError("请先选择所属班级");
      return;
    }
    try {
      const res = await createHomework({ name, class_id: classId, subject });
      setHomeworkId(res.homework_id);
      setHomeworkStatus(res.status);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleAdd() {
    if (!homeworkId) {
      setError("请先创建作业");
      return;
    }
    if (!content.trim()) {
      setError("题目内容不能为空");
      return;
    }
    setError("");
    try {
      await addQuestion(homeworkId, {
        subject,
        question_type: qtype,
        content,
        max_score: maxScore,
        difficulty,
      });
      setQuestions([
        ...questions,
        { question_type: qtype, content, max_score: maxScore, difficulty },
      ]);
      setContent("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const fileRef = useRef<HTMLInputElement>(null);
  const [bankItems, setBankItems] = useState<
    Array<{
      question_bank_item_id: string;
      content: string;
      difficulty: string | null;
      question_type: string;
      grade: string | null;
    }>
  >([]);
  const [ocrHint, setOcrHint] = useState("");

  async function handleUploadImage(file: File) {
    setOcrHint("上传中...");
    try {
      const url = await uploadImage(file);
      setOcrHint("图片已上传,OCR 识别中...");
      const res = await recognizeQuestionImage(url);
      if (res.text) {
        setContent(res.text);
        setOcrHint("✓ OCR 已回填(可修改后再添加)");
      } else {
        setOcrHint("OCR 未识别到文本,请手动输入(密钥未配置时为演示模式)");
      }
    } catch (e) {
      setOcrHint(`上传/识别失败:${(e as Error).message}`);
    }
  }

  async function handleLoadBank() {
    if (!homeworkId) {
      setError("请先创建作业");
      return;
    }
    setError("");
    try {
      const items = await searchQuestionBank(homeworkId, { subject });
      setBankItems(items);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handlePublish() {
    if (!homeworkId) return;
    setPublishHint("发布中...");
    try {
      const res = await publishHomework(homeworkId);
      setHomeworkStatus(res.status);
      setPublishHint("已发布 ✓");
    } catch (e) {
      setPublishHint("");
      setError((e as Error).message);
    }
  }

  return (
    <div className="min-h-full w-full">
      <WorkspaceHeader />
      <main className="space-y-6 p-4 sm:p-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold">
              {isNewHomework ? "创建作业" : name || "编辑作业"}
            </h1>
            <p className="text-muted-foreground text-sm">
              {homeworkId
                ? homeworkStatus
                  ? statusLabel(homeworkStatus, t.teacherCopilot)
                  : "加载中..."
                : "未创建草稿"}{" "}
              · {selectedClass?.name ?? "请选择班级"} ·{" "}
              {subjectLabel(subject, t.teacherCopilot)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/workspace/teacher-copilot/homeworks"
              className="rounded border px-4 py-2 text-sm hover:bg-gray-50"
            >
              返回作业管理
            </Link>
            <button
              className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
              disabled={!homeworkId}
              onClick={handlePublish}
            >
              发布作业
            </button>
          </div>
        </header>

        {!homeworkId && (
          <section className="max-w-md space-y-3 rounded-lg border p-4">
            <label className="text-sm font-medium" htmlFor="homework-name">
              作业信息
            </label>
            <input
              id="homework-name"
              className="w-full rounded border px-2 py-1"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <label className="text-sm font-medium" htmlFor="homework-class">
              所属班级
            </label>
            <select
              id="homework-class"
              className="w-full rounded border px-2 py-1"
              value={classId}
              onChange={(e) => setClassId(e.target.value)}
            >
              <option value="">请选择班级</option>
              {classes.map((item) => (
                <option key={item.class_id} value={item.class_id}>
                  {item.name} ({item.student_count} 人)
                </option>
              ))}
            </select>
            <button
              className="rounded bg-gray-800 px-3 py-1 text-sm text-white disabled:opacity-50"
              disabled={!classId}
              onClick={handleCreate}
            >
              创建草稿作业
            </button>
          </section>
        )}

        <section className="space-y-3 rounded-lg border p-4">
          <h2 className="font-semibold">添加题目(三种来源)</h2>
          <div className="field">
            <textarea
              className="w-full rounded border p-2"
              rows={2}
              placeholder="题目文本(手动输入 / 图片 OCR 后确认)"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <button
                className="rounded border px-3 py-1 hover:bg-gray-100"
                onClick={() => fileRef.current?.click()}
              >
                上传题目图(OCR 回填)
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleUploadImage(f);
                  e.target.value = "";
                }}
              />
              <button
                className="rounded border px-3 py-1 hover:bg-gray-100"
                onClick={handleLoadBank}
              >
                从题库挑选
              </button>
              {ocrHint && (
                <span className="text-muted-foreground text-xs">{ocrHint}</span>
              )}
            </div>
            <div className="flex items-center gap-3 text-sm">
              <select value={qtype} onChange={(e) => setQtype(e.target.value)}>
                <option value="calculation">
                  {questionTypeLabel("calculation", t.teacherCopilot)}
                </option>
                <option value="solution">
                  {questionTypeLabel("solution", t.teacherCopilot)}
                </option>
              </select>
              <label>
                满分{" "}
                <input
                  className="w-16 rounded border px-1"
                  type="number"
                  value={maxScore}
                  onChange={(e) => setMaxScore(Number(e.target.value))}
                />
              </label>
              <label>
                难度(数学)
                <select
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                >
                  <option value="easy">
                    {difficultyLabel("easy", t.teacherCopilot)}
                  </option>
                  <option value="medium">
                    {difficultyLabel("medium", t.teacherCopilot)}
                  </option>
                  <option value="hard">
                    {difficultyLabel("hard", t.teacherCopilot)}
                  </option>
                </select>
              </label>
              <button
                className="rounded bg-gray-800 px-3 py-1 text-white disabled:opacity-50"
                disabled={!homeworkId}
                onClick={handleAdd}
              >
                添加题目
              </button>
            </div>
          </div>
        </section>

        {bankItems.length > 0 && (
          <section className="space-y-2 rounded-lg border p-4">
            <h2 className="font-semibold">题库选择(点击回填)</h2>
            {bankItems.map((it) => (
              <button
                key={it.question_bank_item_id}
                className="block w-full rounded border px-3 py-2 text-left text-sm hover:bg-gray-50"
                onClick={() => setContent(it.content)}
              >
                [{difficultyLabel(it.difficulty, t.teacherCopilot)}]{" "}
                {it.content.slice(0, 60)}
                {it.content.length > 60 ? "..." : ""}
              </button>
            ))}
          </section>
        )}

        <section>
          <h2 className="mb-2 text-lg font-semibold">题目列表</h2>
          {questions.length === 0 ? (
            <p className="text-muted-foreground text-sm">暂无题目</p>
          ) : (
            questions.map((q, i) => (
              <div
                key={q.question_id ?? i}
                className="mb-2 flex justify-between rounded border px-3 py-2 text-sm"
              >
                <span>
                  第 {i + 1} 题 ·{" "}
                  {questionTypeLabel(q.question_type, t.teacherCopilot)} ·{" "}
                  {difficultyLabel(q.difficulty, t.teacherCopilot)} ·{" "}
                  {q.max_score}分
                </span>
                <span className="text-muted-foreground">
                  {q.content.slice(0, 40)}
                </span>
              </div>
            ))
          )}
        </section>

        {publishHint && <p className="text-sm text-green-600">{publishHint}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </main>
    </div>
  );
}
