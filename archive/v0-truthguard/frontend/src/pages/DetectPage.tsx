import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Info } from "lucide-react";
import TopNav from "@/components/TopNav";
import UploadPanel from "@/components/UploadPanel";
import PipelineProgress from "@/components/PipelineProgress";
import EvidencePanel from "@/components/EvidencePanel";
import RiskReportCard from "@/components/RiskReportCard";
import HistoryBar from "@/components/HistoryBar";
import { detectFull } from "@/lib/api";
import { MOCK_REPORT } from "@/lib/mock";
import type { HistoryItem, RiskReport } from "@/types";

export default function DetectPage() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(-1);
  const [report, setReport] = useState<RiskReport | null>(null);
  const [error, setError] = useState("");
  const [offlineDemo, setOfflineDemo] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const pushHistory = (r: RiskReport, label: string) => {
    setHistory((prev) =>
      [
        {
          id: `${Date.now()}`,
          createdAt: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
          label,
          report: r,
        },
        ...prev,
      ].slice(0, 8)
    );
  };

  const runDetect = () => {
    setLoading(true);
    setStage(0);
    setError("");
    setReport(null);
    setOfflineDemo(false);

    timers.current = [
      window.setTimeout(() => setStage(1), 700),
      window.setTimeout(() => setStage(2), 1400),
    ];

    detectFull(file, text)
      .then((r) => {
        setReport(r);
        setStage(3);
        pushHistory(r, file ? file.name : "纯文案检测");
      })
      .catch((err: Error) => {
        console.error("[detect] 检测失败，回退演示数据：", err);
        setError(err.message);
        setOfflineDemo(true);
        setReport(MOCK_REPORT);
        setStage(3);
      })
      .finally(() => {
        timers.current.forEach(clearTimeout);
        setLoading(false);
      });
  };

  return (
    <div className="min-h-screen">
      <TopNav />

      <main className="mx-auto max-w-7xl px-6 pb-16 pt-[88px]">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6"
        >
          <h1 className="text-[26px] font-bold leading-snug md:text-[30px]">
            让每一条美妆内容，<span className="gradient-text">都可被验证</span>
          </h1>
          <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-slate-400">
            像素级取证与语义理解双层证据融合 —— 识别篡改、拼接与 AI 生成痕迹，再由风控 Agent
            完成证据聚合、风险分级与处置建议，形成从「识别」到「决策」的完整闭环。
          </p>
        </motion.div>

        <div className="space-y-6">
          <UploadPanel
            file={file}
            previewUrl={previewUrl}
            text={text}
            loading={loading}
            onPickFile={setFile}
            onTextChange={setText}
            onDetect={runDetect}
          />

          <AnimatePresence>
            {(loading || report) && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
              >
                <div className="mb-4 flex items-center gap-2 text-[14px] font-semibold text-slate-100">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-teal" />
                  第二步 · 三阶段检测流水线
                </div>
                <PipelineProgress stage={stage} running={loading} />
              </motion.div>
            )}
          </AnimatePresence>

          {error && (
            <div className="flex items-start gap-2 rounded-2xl border border-risk-mid/40 bg-risk-mid/10 p-4 text-[13px] text-amber-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                未能连接后端服务（{error}）。当前展示为内置演示样例数据，
                <span className="font-medium">请先启动 backend 后再检测</span>。
              </div>
            </div>
          )}

          {report && (
            <>
              {offlineDemo && (
                <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-[12px] text-slate-400">
                  <Info className="h-4 w-4 text-brand-blue" />
                  以下为演示样例报告，用于无后端环境下的界面展示。
                </div>
              )}

              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4 }}
                className="space-y-6"
              >
                <div>
                  <div className="mb-4 flex items-center gap-2 text-[14px] font-semibold text-slate-100">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-blue" />
                    第三步 · 证据可视化与风险报告
                  </div>
                  <EvidencePanel report={report} previewUrl={previewUrl} />
                </div>

                <RiskReportCard report={report} />
              </motion.div>
            </>
          )}

          <HistoryBar
            items={history}
            onSelect={(item) => setReport(item.report)}
            onClear={() => setHistory([])}
          />
        </div>
      </main>
    </div>
  );
}
