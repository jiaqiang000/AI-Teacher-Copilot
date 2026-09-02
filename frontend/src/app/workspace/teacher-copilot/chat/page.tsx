"use client"
// Teacher Copilot Chat(对照 Figma 06:快捷引导 + 对话/执行过程展示)
// 说明:完整对话与 Tool/Skill 流式执行复用 DeerFlow chat-page(见 ui 文档 §9.2);
// 本页提供可演示的最小容器(消息列表 + 快捷提问),后端运行时接入后展示执行过程。
import { useState } from "react"

const QUICK = [
  "分析八三班长期学情",
  "看看 hw_004 怎么讲评",
  "诊断张三近期数学情况",
]

type Msg = { role: "user" | "assistant"; content: string }

export default function CopilotChatPage() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)

  async function send(text: string) {
    if (!text.trim() || busy) return
    setMessages((m) => [...m, { role: "user", content: text }])
    setInput("")
    setBusy(true)
    // MVP:占位回复,说明执行方式(接入 DeerFlow Thread 后由真实 Agent 回答)
    await new Promise((r) => setTimeout(r, 600))
    const reply = describeExecution(text)
    setMessages((m) => [...m, { role: "assistant", content: reply }])
    setBusy(false)
  }

  return (
    <div className="flex flex-col h-full">
      <header className="py-6 text-center">
        <h1 className="text-2xl font-bold">今天想先看什么？</h1>
        <p className="text-sm text-muted-foreground mt-1">
          我可以查询班级画像、分析作业、诊断学生,必要时调用 DeerFlow Skill / Sub-Agent。
        </p>
        <div className="flex gap-2 justify-center mt-3">
          {QUICK.map((q) => (
            <button key={q} className="rounded-full border px-3 py-1 text-sm" onClick={() => send(q)}>
              {q}
            </button>
          ))}
        </div>
      </header>

      <div className="flex-1 space-y-4 px-8 overflow-y-auto">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div className={`inline-block rounded-lg px-4 py-2 text-sm max-w-[75%] ${m.role === "user" ? "bg-gray-900 text-white" : "border"}`}>
              {m.content}
            </div>
          </div>
        ))}
        {busy && <div className="text-muted-foreground text-sm">AI Teacher 正在处理...</div>}
      </div>

      <div className="p-4 flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2 text-sm"
          placeholder="继续提问..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
        />
        <button className="rounded bg-black text-white px-4" onClick={() => send(input)}>发送</button>
      </div>
    </div>
  )
}

function describeExecution(q: string): string {
  // MVP 占位:说明将采用的技能/工具(接入真实 Agent 后由执行过程替代)
  if (q.includes("讲评")) {
    return "正在使用 homework-review Skill:\n✓ get_homework_analysis\n✓ get_question_analysis · 第8题\n✓ get_class_profile\n建议先讲:① 移项符号错误 ② 第8题典型错误 ③ 函数图像读取。第8题错误率 66.67%,且\"移项\"同时属于班级长期薄弱知识点。"
  }
  if (q.includes("诊断")) {
    return "正在使用 student-diagnosis Skill:\n✓ get_student_profile\n✓ get_student_grading_history\n(接入 DeerFlow 后此处展示真实执行过程与结果。)"
  }
  if (q.includes("学情")) {
    return "正在使用 class-learning-analysis Skill:\n✓ get_class_profile\n(接入 DeerFlow 后此处展示真实执行过程与结果。)"
  }
  return "已收到,正在处理(接入 DeerFlow Thread 后由真实 Agent 回答)。"
}
