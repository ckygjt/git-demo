import { useEffect, useState } from "react";
import { Cpu, ShieldCheck } from "lucide-react";
import { fetchHealth } from "@/lib/api";
import type { HealthInfo } from "@/types";

export default function TopNav() {
  const [health, setHealth] = useState<HealthInfo | null>(null);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err) => console.error("[health] 后端未连接：", err));
  }, []);

  const llmOn = Boolean(health?.llm_enabled);

  return (
    <header className="fixed inset-x-0 top-0 z-50 h-16 border-b border-white/10 bg-ink-900/70 backdrop-blur-xl">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-teal via-brand-blue to-brand-indigo shadow-glow">
            <ShieldCheck className="h-5 w-5 text-ink-900" />
            <span className="absolute inset-0 animate-pulseRing rounded-xl border border-brand-teal/60" />
          </div>
          <div className="leading-tight">
            <div className="text-[17px] font-bold tracking-wide">
              真鉴 <span className="gradient-text">TruthGuard</span>
            </div>
            <div className="text-[11px] text-slate-400">美妆内容多模态鉴真 Agent</div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden rounded-full border border-brand-indigo/40 bg-brand-indigo/10 px-3 py-1 text-[12px] text-indigo-200 md:inline">
            欧莱雅黑客松 · 赛道二 信任守护师
          </span>
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5">
            <span
              className={`h-2 w-2 rounded-full ${
                llmOn ? "bg-risk-low shadow-[0_0_10px_#22C55E]" : "bg-risk-mid shadow-[0_0_10px_#F59E0B]"
              }`}
            />
            <Cpu className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-[12px] text-slate-300">
              {health
                ? llmOn
                  ? `大模型已接入 · ${health.llm_provider}`
                  : "降级模式 · 本地取证"
                : "后端未连接"}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
