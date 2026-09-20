import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { BadgeCheck, Gavel, ListChecks, ShieldAlert, TriangleAlert } from "lucide-react";
import type { ActionType, RiskReport } from "@/types";

const LEVEL_META = {
  low: { label: "低风险", color: "text-risk-low", ring: "#22C55E", glow: "shadow-[0_0_40px_rgba(34,197,94,0.35)]" },
  medium: { label: "中风险", color: "text-risk-mid", ring: "#F59E0B", glow: "shadow-[0_0_40px_rgba(245,158,11,0.35)]" },
  high: { label: "高风险", color: "text-risk-high", ring: "#EF4444", glow: "shadow-[0_0_44px_rgba(239,68,68,0.45)]" },
} as const;

const ACTION_META: Record<ActionType, { label: string; hint: string }> = {
  pass: { label: "通过上架", hint: "内容可正常展示并归档检测记录" },
  review: { label: "转人工复核", hint: "进入人审队列，重点核对标记区域" },
  flag: { label: "警示标记并限流", hint: "添加风险标签并降低推荐权重" },
  takedown: { label: "建议下架并触发合规工单", hint: "下架留证并通知创作者整改" },
};

function AnimatedNumber({ value }: { value: number }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 900);
      setShown(Number((value * (1 - Math.pow(1 - p, 3))).toFixed(1)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{shown.toFixed(1)}</>;
}

export default function RiskReportCard({ report }: { report: RiskReport }) {
  const [executed, setExecuted] = useState<string | null>(null);
  const meta = LEVEL_META[report.risk_level];
  const action = ACTION_META[report.action];
  const circumference = 2 * Math.PI * 54;

  useEffect(() => setExecuted(null), [report]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={`glass p-6 ${meta.glow}`}
    >
      <div className="flex flex-wrap items-center gap-6">
        {/* 风险分环 */}
        <div className="relative h-32 w-32 shrink-0">
          <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
            <circle cx="60" cy="60" r="54" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
            <motion.circle
              cx="60"
              cy="60"
              r="54"
              fill="none"
              stroke={meta.ring}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: circumference * (1 - report.risk_score / 100) }}
              transition={{ duration: 1 }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-[26px] font-bold ${meta.color}`}>
              <AnimatedNumber value={report.risk_score} />
            </span>
            <span className="text-[11px] text-slate-400">风险分 / 100</span>
          </div>
        </div>

        <div className="min-w-[240px] flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-[13px] font-semibold ${meta.color}`}
            >
              {report.risk_level === "low" ? (
                <BadgeCheck className="h-4 w-4" />
              ) : report.risk_level === "medium" ? (
                <ShieldAlert className="h-4 w-4" />
              ) : (
                <TriangleAlert className="h-4 w-4" />
              )}
              {meta.label}
            </span>
            <span className="rounded-full bg-gradient-to-r from-brand-teal/20 to-brand-indigo/20 px-3 py-1 text-[13px] font-semibold text-slate-100">
              处置动作：{action.label}
            </span>
            {report.text?.redline && (
              <span className="rounded-full border border-risk-high/50 bg-risk-high/15 px-3 py-1 text-[12px] text-red-200">
                命中宣称合规红线
              </span>
            )}
            {report.degraded && (
              <span className="rounded-full border border-risk-mid/40 bg-risk-mid/10 px-3 py-1 text-[12px] text-amber-200">
                降级模式 · 本地取证
              </span>
            )}
          </div>
          <p className="mt-3 text-[13px] leading-relaxed text-slate-400">{action.hint}</p>

          <div className="mt-4 rounded-2xl border border-white/10 bg-ink-800/60 p-4">
            <div className="mb-1.5 flex items-center gap-2 text-[12px] text-slate-400">
              <Gavel className="h-3.5 w-3.5 text-brand-teal" /> Agent 决策推理
            </div>
            <p className="text-[13px] leading-relaxed text-slate-200">{report.reasoning}</p>
          </div>
        </div>
      </div>

      {/* 处理建议 + 处置执行 */}
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center gap-2 text-[13px] text-slate-400">
            <ListChecks className="h-4 w-4 text-brand-blue" /> 处理建议
          </div>
          <ul className="space-y-2">
            {report.suggestions.map((s) => (
              <li
                key={s}
                className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-[13px] leading-relaxed text-slate-300"
              >
                {s}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <div className="mb-2 text-[13px] text-slate-400">处置执行（模拟下发）</div>
          <div className="grid grid-cols-3 gap-2">
            {(["review", "flag", "takedown"] as ActionType[]).map((act) => (
              <button
                key={act}
                type="button"
                onClick={() => setExecuted(act)}
                className={`cursor-pointer rounded-xl border px-3 py-3 text-[13px] font-medium transition ${
                  executed === act
                    ? "border-brand-teal bg-brand-teal/20 text-brand-teal"
                    : "border-white/10 bg-white/[0.04] text-slate-300 hover:border-brand-teal/50 hover:bg-white/[0.08]"
                }`}
              >
                {ACTION_META[act].label.split("并")[0]}
              </button>
            ))}
          </div>
          {executed && (
            <motion.p
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-3 rounded-xl border border-brand-teal/30 bg-brand-teal/10 px-3 py-2 text-[12px] text-brand-teal"
            >
              已向内容中台下发「{ACTION_META[executed as ActionType].label}」指令，闭环完成。
            </motion.p>
          )}
          <p className="mt-3 text-[12px] text-slate-500">
            检测耗时 {report.elapsed_ms} ms · 证据 {report.image?.evidence.length ?? 0} +
            {report.text?.evidence.length ?? 0} 条
          </p>
        </div>
      </div>
    </motion.section>
  );
}
