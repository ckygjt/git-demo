import { useState } from "react";
import { motion } from "framer-motion";
import { Eye, Flame, ImageOff } from "lucide-react";
import type { Evidence, RiskReport } from "@/types";

const SOURCE_LABEL: Record<string, string> = {
  forensics: "像素取证",
  vision_llm: "视觉语义",
  text_rule: "合规规则",
  text_llm: "文案语义",
};

const SEVERITY_STYLE: Record<string, string> = {
  high: "border-risk-high/40 bg-risk-high/10 text-red-200",
  medium: "border-risk-mid/40 bg-risk-mid/10 text-amber-200",
  low: "border-risk-low/40 bg-risk-low/10 text-emerald-200",
};

function barColor(score: number) {
  if (score >= 0.6) return "from-risk-mid to-risk-high";
  if (score >= 0.35) return "from-brand-blue to-risk-mid";
  return "from-brand-teal to-brand-blue";
}

function EvidenceCard({ item, index }: { item: Evidence; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06, duration: 0.35 }}
      className="glass glass-hover p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="rounded-md border border-white/10 bg-white/[0.06] px-2 py-0.5 text-[11px] text-slate-300">
            {SOURCE_LABEL[item.source] ?? item.source}
          </span>
          <span className="truncate text-[13px] font-medium text-slate-100">{item.name}</span>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] ${
            SEVERITY_STYLE[item.severity] ?? SEVERITY_STYLE.low
          }`}
        >
          {item.severity === "high" ? "高" : item.severity === "medium" ? "中" : "低"}
        </span>
      </div>

      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(item.score * 100)}%` }}
          transition={{ duration: 0.8, delay: index * 0.06 }}
          className={`h-full rounded-full bg-gradient-to-r ${barColor(item.score)}`}
        />
      </div>

      <div className="mt-2 flex items-center justify-between text-[12px] text-slate-400">
        <span className="line-clamp-2 pr-3">{item.description}</span>
        <span className="shrink-0 font-semibold text-slate-200">
          {(item.score * 100).toFixed(0)}
        </span>
      </div>
    </motion.div>
  );
}

export default function EvidencePanel({
  report,
  previewUrl,
}: {
  report: RiskReport;
  previewUrl: string;
}) {
  const [view, setView] = useState<"origin" | "heatmap">("origin");
  const image = report.image;
  const region = image?.evidence.find((e) => e.region)?.region ?? null;

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      {/* 左：证据可视化 */}
      <div className="glass p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-[14px] font-semibold text-slate-100">篡改证据可视化</h3>
          <div className="flex gap-1 rounded-full border border-white/10 bg-white/[0.04] p-1">
            <button
              type="button"
              onClick={() => setView("origin")}
              className={`flex cursor-pointer items-center gap-1 rounded-full px-3 py-1 text-[12px] transition ${
                view === "origin" ? "bg-brand-teal/20 text-brand-teal" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Eye className="h-3 w-3" /> 原图
            </button>
            <button
              type="button"
              onClick={() => setView("heatmap")}
              disabled={!image?.heatmap}
              className={`flex items-center gap-1 rounded-full px-3 py-1 text-[12px] transition ${
                !image?.heatmap
                  ? "cursor-not-allowed text-slate-600"
                  : view === "heatmap"
                    ? "cursor-pointer bg-risk-high/20 text-red-300"
                    : "cursor-pointer text-slate-400 hover:text-slate-200"
              }`}
            >
              <Flame className="h-3 w-3" /> ELA 热力图
            </button>
          </div>
        </div>

        <div className="relative flex h-[340px] items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-ink-800/50">
          {!previewUrl && !image?.heatmap ? (
            <div className="flex flex-col items-center gap-2 text-slate-500">
              <ImageOff className="h-7 w-7" />
              <span className="text-[12px]">本次未上传图片，仅展示文案侧证据</span>
            </div>
          ) : (
            <img
              src={
                view === "heatmap" && image?.heatmap
                  ? `data:image/jpeg;base64,${image.heatmap}`
                  : previewUrl
              }
              alt="证据视图"
              className="max-h-full max-w-full object-contain"
            />
          )}

          {view === "heatmap" && region && (
            <div
              className="pointer-events-none absolute rounded-lg border-2 border-risk-high shadow-glow-red"
              style={{
                left: `${region[0] * 100}%`,
                top: `${region[1] * 100}%`,
                width: `${region[2] * 100}%`,
                height: `${region[3] * 100}%`,
              }}
            >
              <span className="absolute -top-6 left-0 whitespace-nowrap rounded bg-risk-high px-1.5 py-0.5 text-[11px] text-white">
                可疑篡改区域
              </span>
            </div>
          )}
        </div>

        {image && (
          <div className="mt-4 space-y-1.5">
            {image.findings.map((f) => (
              <div key={f} className="text-[12px] text-slate-400">
                · {f}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 右：证据链 */}
      <div className="space-y-3">
        <h3 className="text-[14px] font-semibold text-slate-100">
          证据链（{report.image?.evidence.length ?? 0} 条图像 + {report.text?.evidence.length ?? 0} 条文案）
        </h3>
        <div className="max-h-[430px] space-y-3 overflow-y-auto pr-1">
          {(report.image?.evidence ?? []).map((e, i) => (
            <EvidenceCard key={`img-${e.name}`} item={e} index={i} />
          ))}
          {(report.text?.evidence ?? []).map((e, i) => (
            <EvidenceCard
              key={`txt-${e.name}`}
              item={e}
              index={(report.image?.evidence.length ?? 0) + i}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
