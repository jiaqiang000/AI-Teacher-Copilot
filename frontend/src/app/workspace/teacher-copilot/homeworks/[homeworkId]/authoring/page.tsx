"use client"
// 作业创建(对照 Figma 04:作业信息 + 添加题目三来源 + 题目列表 + 发布)
// 交互:手动输入/上传图片(OCR 预填)/题库选择;数学难度预判确认;发布校验
import { useRef, useState } from "react"
import { addQuestion, createHomework, publishHomework, recognizeQuestionImage, searchQuestionBank, uploadImage } from "@/core/teacher-copilot/api"

const CLASS_ID = "class_03"
const SUBJECT = "math"

type QuestionDraft = {
  question_type: string
  content: string
  max_score: number
  difficulty?: string | null
}

export default function AuthoringPage() {
  const [homeworkId, setHomeworkId] = useState<string | null>(null)
  const [questions, setQuestions] = useState<QuestionDraft[]>([])
  const [name, setName] = useState("八年级数学周末作业")
  const [content, setContent] = useState("")
  const [qtype, setQtype] = useState("calculation")
  const [maxScore, setMaxScore] = useState(10)
  const [difficulty, setDifficulty] = useState("easy")
  const [publishHint, setPublishHint] = useState("")
  const [error, setError] = useState("")

  async function handleCreate() {
    setError("")
    try {
      const res = await createHomework({ name, class_id: CLASS_ID, subject: SUBJECT })
      setHomeworkId(res.homework_id)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function handleAdd() {
    if (!homeworkId) {
      setError("请先创建作业")
      return
    }
    if (!content.trim()) {
      setError("题目内容不能为空")
      return
    }
    setError("")
    try {
      await addQuestion(homeworkId, {
        subject: SUBJECT,
        question_type: qtype,
        content,
        max_score: maxScore,
        difficulty,
      })
      setQuestions([...questions, { question_type: qtype, content, max_score: maxScore, difficulty }])
      setContent("")
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const fileRef = useRef<HTMLInputElement>(null)
  const [bankItems, setBankItems] = useState<Array<{
    question_bank_item_id: string; content: string; difficulty: string | null;
    question_type: string; grade: string | null;
  }>>([])
  const [ocrHint, setOcrHint] = useState("")

  async function handleUploadImage(file: File) {
    setOcrHint("上传中...")
    try {
      const url = await uploadImage(file)
      setOcrHint("图片已上传,OCR 识别中...")
      const res = await recognizeQuestionImage(url)
      if (res.text) {
        setContent(res.text)
        setOcrHint("✓ OCR 已回填(可修改后再添加)")
      } else {
        setOcrHint("OCR 未识别到文本,请手动输入(密钥未配置时为演示模式)")
      }
    } catch (e) {
      setOcrHint(`上传/识别失败:${(e as Error).message}`)
    }
  }

  async function handleLoadBank() {
    if (!homeworkId) {
      setError("请先创建作业")
      return
    }
    setError("")
    try {
      const items = await searchQuestionBank(homeworkId, { subject: SUBJECT })
      setBankItems(items)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function handlePublish() {
    if (!homeworkId) return
    setPublishHint("发布中...")
    try {
      await publishHomework(homeworkId)
      setPublishHint("已发布 ✓")
    } catch (e) {
      setPublishHint("")
      setError((e as Error).message)
    }
  }

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">创建作业</h1>
          <p className="text-muted-foreground text-sm">DRAFT · 八三班 · 数学</p>
        </div>
        <button
          className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
          disabled={!homeworkId}
          onClick={handlePublish}
        >
          发布作业
        </button>
      </header>

      {!homeworkId && (
        <section className="rounded-lg border p-4 max-w-md space-y-2">
          <label className="text-sm font-medium">作业信息</label>
          <input className="w-full border rounded px-2 py-1" value={name} onChange={(e) => setName(e.target.value)} />
          <button className="rounded bg-gray-800 text-white px-3 py-1 text-sm" onClick={handleCreate}>
            创建草稿作业
          </button>
        </section>
      )}

      <section className="rounded-lg border p-4 space-y-3">
        <h2 className="font-semibold">添加题目(三种来源)</h2>
        <div className="field">
          <textarea
            className="w-full border rounded p-2"
            rows={2}
            placeholder="题目文本(手动输入 / 图片 OCR 后确认)"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <div className="flex gap-3 items-center text-sm">
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
                const f = e.target.files?.[0]
                if (f) void handleUploadImage(f)
                e.target.value = ""
              }}
            />
            <button className="rounded border px-3 py-1 hover:bg-gray-100" onClick={handleLoadBank}>
              从题库挑选
            </button>
            {ocrHint && <span className="text-xs text-muted-foreground">{ocrHint}</span>}
          </div>
          <div className="flex gap-3 items-center text-sm">
            <select value={qtype} onChange={(e) => setQtype(e.target.value)}>
              <option value="calculation">calculation</option>
              <option value="solution">solution</option>
            </select>
            <label>满分 <input className="w-16 border rounded px-1" type="number" value={maxScore} onChange={(e) => setMaxScore(Number(e.target.value))} /></label>
            <label>难度(数学)
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                <option value="easy">easy</option>
                <option value="medium">medium</option>
                <option value="hard">hard</option>
              </select>
            </label>
            <button className="rounded bg-gray-800 text-white px-3 py-1" onClick={handleAdd}>添加题目</button>
          </div>
        </div>
      </section>

      {bankItems.length > 0 && (
        <section className="rounded-lg border p-4 space-y-2">
          <h2 className="font-semibold">题库选择(点击回填)</h2>
          {bankItems.map((it) => (
            <button
              key={it.question_bank_item_id}
              className="block w-full text-left border rounded px-3 py-2 text-sm hover:bg-gray-50"
              onClick={() => setContent(it.content)}
            >
              [{it.difficulty ?? "?"}] {it.content.slice(0, 60)}
              {it.content.length > 60 ? "..." : ""}
            </button>
          ))}
        </section>
      )}

      <section>
        <h2 className="text-lg font-semibold mb-2">题目列表</h2>
        {questions.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无题目</p>
        ) : (
          questions.map((q, i) => (
            <div key={i} className="rounded border px-3 py-2 mb-2 text-sm flex justify-between">
              <span>第 {i + 1} 题 · {q.question_type} · {q.difficulty} · {q.max_score}分</span>
              <span className="text-muted-foreground">{q.content.slice(0, 40)}</span>
            </div>
          ))
        )}
      </section>

      {publishHint && <p className="text-green-600 text-sm">{publishHint}</p>}
      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}
