"use client"
// Teacher Copilot Chat(对照 Figma 06:快捷引导 + 对话/执行过程展示)
// 真实 Agent:POST /api/runs/wait(assistant_id=teacher-copilot),经 next.config
// /api/:path* 代理到 Gateway;展示工具/技能执行步骤与真实回答。
import { useCallback, useState } from "react"
import { fetch as apiFetch } from "@/core/api/fetcher"

const QUICK = [
  "分析八三班长期学情",
  "看看 hw_004 怎么讲评",
  "诊断张三近期数学情况",
]

type Msg =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; steps?: string[] }

function extractText(message: unknown): string {
  const content = (message as { content?: unknown } | null)?.content
  if (typeof content === "string") {
    const trimmed = content.trim()
    if (trimmed.startsWith("[")) {
      try {
        const arr = JSON.parse(trimmed)
        const text = arr
          .filter((m: Record<string, unknown>) => typeof m?.text === "string")
          .map((m: Record<string, unknown>) => m.text as string)
          .join("\n")
        if (text) return text
        const thinking = arr
          .filter((m: Record<string, unknown>) => typeof m?.thinking === "string")
          .map((m: Record<string, unknown>) => m.thinking as string)
          .join("\n")
        return thinking ? `(思考过程已省略)\n${thinking.slice(0, 120)}` : ""
      } catch {
        /* 非 JSON 一律作为纯文本 */
      }
    }
    return trimmed
  }
  if (Array.isArray(content)) {
    return content
      .filter((m) => typeof m?.text === "string" && m.text)
      .map((m) => m.text)
      .join("\n")
  }
  return ""
}

function extractToolSteps(messages: unknown[]): string[] {
  const steps: string[] = []
  for (const m of messages) {
    const msg = m as { type?: string; name?: string; content?: unknown }
    if (
      (msg.type === "tool" || msg.type === "tool_use" || msg.type === "tool_result") &&
      msg.name
    ) {
      const detail = typeof msg.content === "string" ? msg.content : ""
      steps.push(`✓ ${msg.name}${detail ? " · " + detail.slice(0, 60).replace(/\n/g, " ") : ""}`)
    }
  }
  return steps
}

export default function CopilotChatPage() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || busy) return
      setMessages((m) => [...m, { role: "user", content: text }])
      setInput("")
      setBusy(true)
      setError("")
      try {
        const res = await apiFetch("/api/runs/wait", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            assistant_id: "teacher-copilot",
            // 允许委派 Sub-Agent(diagnosis-worker/practice-worker/reviewer),
            // 是否委派仍由模型按 SOUL 规则决定(Single-Agent First)
            config: { subagent_enabled: true },
            input: { messages: [{ role: "user", content: text }] },
          }),
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(
            body?.detail?.message || body?.detail?.code || `请求失败 ${res.status}`,
          )
        }
        const data = await res.json()
        const replyMsgs: unknown[] =
          data?.output?.messages || data?.messages || data?.result?.messages || []
        const answer =
          extractText(replyMsgs.at(-1)) || "Agent 未返回文本,请查看页面日志。"
        const steps = extractToolSteps(replyMsgs)
        setMessages((m) => [...m, { role: "assistant", content: answer, steps }])
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e))
        setMessages((m) => [
          ...m,
          { role: "assistant", content: `调用失败:${e instanceof Error ? e.message : e}` },
        ])
      } finally {
        setBusy(false)
      }
    },
    [busy],
  )

  return (
    <div className="flex flex-col h-full">
      <header className="py-6 text-center">
        <h1 className="text-2xl font-bold">今天想先看什么？</h1>
        <p className="text-sm text-muted-foreground mt-1">
          我可以查询班级画像、分析作业、诊断学生,必要时调用 DeerFlow Skill / Sub-Agent。
        </p>
        <div className="flex gap-2 justify-center mt-3">
          {QUICK.map((q) => (
            <button
              key={q}
              className="rounded-full border px-3 py-1 text-sm hover:bg-gray-100"
              onClick={() => send(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </header>

      <div className="flex-1 space-y-4 px-8 overflow-y-auto">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className={`inline-block rounded-lg px-4 py-2 text-sm max-w-[75%] whitespace-pre-wrap ${
                m.role === "user" ? "bg-gray-900 text-white" : "border"
              }`}
            >
              {m.content}
            </div>
            {m.role === "assistant" && m.steps && m.steps.length > 0 && (
              <div className="mt-1 text-xs text-muted-foreground">{m.steps.join(" → ")}</div>
            )}
          </div>
        ))}
        {busy && (
          <div className="text-muted-foreground text-sm">
            AI Teacher 正在处理(首次约 30s)...
          </div>
        )}
        {error && (
          <div className="text-red-500 text-sm">
            提示:{error}(请确认已登录教师体验账号)
          </div>
        )}
      </div>

      <div className="p-4 flex gap-2">
        <input
          className="flex-1 border rounded px-3 py-2 text-sm"
          placeholder="继续提问..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
        />
        <button className="rounded bg-black text-white px-4" onClick={() => send(input)}>
          发送
        </button>
      </div>
    </div>
  )
}
