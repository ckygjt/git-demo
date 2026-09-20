import { motion } from "framer-motion";
import { History } from "lucide-react";
import type { HistoryItem } from "@/types";

const DOT: Record<string, string> = {
  low: "bg-risk-low",
  medium: "bg-risk-mid",
  high: "bg-risk-high",
};

export default function HistoryBar({
  items,
  onSelect,
  onClear,
}: {
  items: HistoryItem[];
  onSelect: (item: HistoryItem) => void;
  onClear: () => void;
}) {
  return (
    <section className="glass p-5">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[14px] font-semibold text-slate-100">
          <History className="h-4 w-4 text-brand-indigo" /> 检测历史
        </div>
        {items.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            className="cursor-pointer rounded-full border border-white/10 px-3 py-1 text-[12px] text-slate-400 transition hover:border-risk-high/40 hover:text-red-300"
          >
            清空
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="text-[12px] text-slate-500">
          暂无记录。完成一次检测后，可在此快速回看历史报告。
        </p>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-1">
          {items.map((item) => (
            <motion.button
              key={item.id}
              type="button"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={() => onSelect(item)}
              className="glass glass-hover min-w-[220px] cursor-pointer p-3 text-left"
            >
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${DOT[item.report.risk_level]}`} />
                <span className="text-[13px] font-medium text-slate-100">{item.label}</span>
              </div>
              <div className="mt-1 text-[11px] text-slate-500">{item.createdAt}</div>
              <div className="mt-1 text-[12px] text-slate-400">
                风险分 {item.report.risk_score.toFixed(1)} ·{" "}
                {item.report.risk_level === "high"
                  ? "高风险"
                  : item.report.risk_level === "medium"
                    ? "中风险"
                    : "低风险"}
              </div>
            </motion.button>
          ))}
        </div>
      )}
    </section>
  );
}
