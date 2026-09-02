"use client"
// HITL 澄清卡(对照 Figma 澄清卡视觉;复用 DeerFlow Human Input UI 概念)
// ask_clarification 弹出候选,教师选择后继续(参考文档 06-07 §2.5 HITL 链路)
import { useState } from "react"

export type ClarificationOption = { id: string; label: string; extra?: string }

export function ClarificationCard({
  question,
  options,
  onResolve,
}: {
  question: string
  options: ClarificationOption[]
  onResolve: (choice: ClarificationOption) => void
}) {
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="rounded-lg border p-4 max-w-md bg-white">
      <div className="text-sm font-medium">{question}</div>
      <p className="text-xs text-muted-foreground mt-1">存在多个候选,请确认:</p>
      <div className="mt-3 space-y-2">
        {options.map((opt) => (
          <button
            key={opt.id}
            className={`w-full rounded border px-3 py-2 text-left text-sm ${selected === opt.id ? "border-black bg-gray-50" : ""}`}
            onClick={() => setSelected(opt.id)}
          >
            <span className="font-medium">{opt.label}</span>
            {opt.extra && <span className="text-muted-foreground ml-2">{opt.extra}</span>}
          </button>
        ))}
      </div>
      <button
        className="mt-3 rounded bg-black text-white px-4 py-1.5 text-sm disabled:opacity-50"
        disabled={!selected}
        onClick={() => {
          const choice = options.find((o) => o.id === selected)
          if (choice) onResolve(choice)
        }}
      >
        确认
      </button>
    </div>
  )
}
