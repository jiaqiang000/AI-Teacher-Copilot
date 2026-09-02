"use client"
// Teacher Copilot Chat(06)- 功能版
import { useState } from "react"

const QUICK = ["分析八三班长期学情", "看看 hw_004 怎么讲评", "诊断张三近期数学情况"]

export default function ChatPage() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([])
  const [input, setInput] = useState("")

  function send(text: string) {
    if (!text) return
    const userMsg = text
    setMessages((prev) => [...prev, { role: "user", content: userMsg }])
    const reply = demoReply(text)
    setMessages((prev) => [...prev, { role: "assistant", content: reply }])
    setInput("")
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="pt-8 pb-4 text-center">
        <h1 className="text-2xl font-bold">今天想先看什么？</h1>
        <p className="text-sm text-gray-500 mt-1">
          我可以查询班级画像、分析作业、诊断学生,必要时调用 DeerFlow Skill / Sub-Agent。
        </p>
        <div className="mt-3 flex justify-center gap-2">
          {QUICK.map((q) => (
            <button key={q} className="rounded-full border px-3 py-1 text-sm hover:bg-gray-50" onClick={() => send(q)}>
              {q}
            </button>
          ))}
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-6 space-y-3 pb-20">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div className={"inline-block max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap " + (m.role === "user" ? "bg-gray-900 text-white" : "border border-gray-200")}>
              {m.content}
            </div>
          </div>
        ))}
      </div>

      <div className="fixed bottom-0 left-0 right-0 border-t bg-white px-6 py-3 flex gap-2">
        <input className="flex-1 rounded border px-3 py-2 text-sm" placeholder="继续提问..." value={input}
          onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send(input)} />
        <button className="rounded bg-black text-white px-4 py-2 text-sm" onClick={() => send(input)}>发送</button>
      </div>
    </div>
  )
}

function demoReply(q: string): string {
  if (q.includes("讲评")) return "正在使用 homework-review Skill:\n✓ get_homework_analysis\n✓ get_question_analysis · 第8题\n✓ get_class_profile\n建议先讲:① 移项符号错误 ② 第8题典型错误 ③ 函数图像读取。第8题错误率 66.67%,且\"移项\"同时属于班级长期薄弱知识点。"
  if (q.includes("诊断")) return "正在使用 student-diagnosis Skill:\n✓ get_student_profile\n✓ get_student_grading_history\n(接入 DeerFlow 后此处展示真实执行过程与结果。)"
  if (q.includes("学情")) return "正在使用 class-learning-analysis Skill:\n✓ get_class_profile\n(接入 DeerFlow 后此处展示真实执行过程与结果。)"
  return "已收到,正在处理(接入 DeerFlow Thread 后由真实 Agent 回答)。"
}
