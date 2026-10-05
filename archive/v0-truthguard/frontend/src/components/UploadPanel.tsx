import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { ImagePlus, ScanSearch, Sparkles, Type, X } from "lucide-react";

interface Props {
  file: File | null;
  previewUrl: string;
  text: string;
  loading: boolean;
  onPickFile: (f: File | null) => void;
  onTextChange: (v: string) => void;
  onDetect: () => void;
}

const BAD_TEXT =
  "七天美白，医美级效果，100%有效！专利号ZL202310123456，万人好评，用了都说好，一用就白。";
const GOOD_TEXT =
  "含烟酰胺与透明质酸钠的温和保湿精华，质地清爽易吸收，适合日常护肤使用，具体效果因人而异。";

export default function UploadPanel({
  file,
  previewUrl,
  text,
  loading,
  onPickFile,
  onTextChange,
  onDetect,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const pick = (f: File | null) => onPickFile(f);

  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="glass p-6"
    >
      <div className="mb-5 flex items-center gap-2">
        <ScanSearch className="h-4 w-4 text-brand-teal" />
        <h2 className="text-[15px] font-semibold text-slate-100">
          第一步 · 提交待检测的美妆内容
        </h2>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* 图片上传 */}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) pick(f);
          }}
          className={`group relative flex h-64 w-full cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed transition-all duration-300 ${
            dragging
              ? "border-brand-teal bg-brand-teal/10 shadow-glow"
              : "border-white/15 bg-white/[0.02] hover:border-brand-teal/50 hover:bg-white/[0.05]"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => pick(e.target.files?.[0] ?? null)}
          />

          {previewUrl ? (
            <>
              <img src={previewUrl} alt="待检测内容" className="h-full w-full object-contain" />
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  e.stopPropagation();
                  pick(null);
                }}
                className="absolute right-3 top-3 flex h-8 w-8 cursor-pointer items-center justify-center rounded-full bg-ink-900/80 text-slate-300 transition hover:bg-risk-high hover:text-white"
              >
                <X className="h-4 w-4" />
              </span>
            </>
          ) : (
            <div className="flex flex-col items-center gap-3 text-center">
              <div className="relative">
                <ImagePlus className="h-9 w-9 animate-floaty text-brand-teal" />
                <span className="absolute -inset-3 rounded-full bg-brand-teal/10 blur-md" />
              </div>
              <div className="text-[14px] font-medium text-slate-200">
                拖拽或点击上传美妆商品图 / 达人试色图
              </div>
              <div className="text-[12px] text-slate-500">
                支持 JPG / PNG，将进行 ELA 取证、噪声一致性与元数据检查
              </div>
            </div>
          )}

          {previewUrl && (
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink-900 to-transparent p-3 text-left">
              <div className="truncate text-[12px] text-slate-300">{file?.name}</div>
            </div>
          )}
        </button>

        {/* 文案输入 */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2 text-[13px] text-slate-400">
            <Type className="h-4 w-4 text-brand-blue" />
            商品文案 / 达人笔记正文
          </div>
          <textarea
            value={text}
            onChange={(e) => onTextChange(e.target.value)}
            rows={7}
            placeholder="粘贴待审核的美妆推广文案，例如：七天美白，医美级效果，100%有效……"
            className="w-full flex-1 resize-none rounded-2xl border border-white/10 bg-ink-800/60 p-4 text-[14px] leading-relaxed text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-brand-blue/60 focus:bg-ink-800 focus:shadow-glow-blue"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onTextChange(BAD_TEXT)}
              className="rounded-full border border-risk-high/40 bg-risk-high/10 px-3 py-1.5 text-[12px] text-red-200 transition hover:bg-risk-high/20"
            >
              填充违规文案示例
            </button>
            <button
              type="button"
              onClick={() => onTextChange(GOOD_TEXT)}
              className="rounded-full border border-risk-low/40 bg-risk-low/10 px-3 py-1.5 text-[12px] text-emerald-200 transition hover:bg-risk-low/20"
            >
              填充合规文案示例
            </button>
          </div>
        </div>
      </div>

      <motion.button
        type="button"
        whileHover={{ scale: 1.01 }}
        whileTap={{ scale: 0.99 }}
        onClick={onDetect}
        disabled={loading || (!file && !text.trim())}
        className={`mt-6 flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-brand-teal via-brand-blue to-brand-indigo px-6 py-3.5 text-[15px] font-semibold text-ink-900 shadow-glow transition ${
          loading || (!file && !text.trim())
            ? "cursor-not-allowed opacity-45"
            : "cursor-pointer hover:opacity-95"
        }`}
      >
        <Sparkles className="h-4 w-4" />
        {loading ? "检测中，Agent 正在聚合证据…" : "开始鉴真检测"}
      </motion.button>
    </motion.section>
  );
}
