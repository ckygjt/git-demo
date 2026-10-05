import { motion } from "framer-motion";
import { BrainCircuit, Check, Grid3x3, ScanLine } from "lucide-react";

interface Props {
  stage: number; // 0~2 进行中，3 表示全部完成
  running: boolean;
}

const STEPS = [
  { icon: Grid3x3, title: "图像取证", desc: "ELA 误差 / 噪声一致性 / EXIF 元数据" },
  { icon: ScanLine, title: "语义分析", desc: "视觉模型与文案合规规则库并行扫描" },
  { icon: BrainCircuit, title: "Agent 决策", desc: "证据聚合、风险分级与处置建议" },
];

export default function PipelineProgress({ stage, running }: Props) {
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {STEPS.map((step, idx) => {
        const done = stage > idx;
        const active = running && stage === idx;
        const Icon = step.icon;

        return (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.08, duration: 0.4 }}
            className={`relative overflow-hidden rounded-2xl border p-4 transition-all duration-300 ${
              done
                ? "border-brand-teal/50 bg-brand-teal/[0.08]"
                : active
                  ? "border-brand-blue/60 bg-brand-blue/[0.08] shadow-glow-blue"
                  : "border-white/10 bg-white/[0.02]"
            }`}
          >
            {active && (
              <div className="pointer-events-none absolute inset-x-0 top-0 h-full">
                <div className="h-1 w-full animate-scanline bg-gradient-to-r from-transparent via-brand-teal to-transparent" />
              </div>
            )}

            <div className="flex items-start gap-3">
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition ${
                  done
                    ? "border-brand-teal/60 bg-brand-teal/20 text-brand-teal"
                    : active
                      ? "border-brand-blue/60 bg-brand-blue/20 text-brand-blue"
                      : "border-white/10 bg-white/[0.04] text-slate-500"
                }`}
              >
                {done ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
              </div>
              <div className="min-w-0">
                <div className="text-[14px] font-semibold text-slate-100">
                  <span className="mr-2 text-[12px] text-slate-500">0{idx + 1}</span>
                  {step.title}
                </div>
                <div className="mt-1 text-[12px] leading-relaxed text-slate-400">
                  {step.desc}
                </div>
              </div>
            </div>

            {active && (
              <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-white/10">
                <div className="h-full w-1/2 animate-shimmer bg-gradient-to-r from-transparent via-brand-teal to-transparent bg-[length:200%_100%]" />
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
