/**
 * 生成参赛路演 PPT：真鉴 TruthGuard · 美妆内容鉴真 Agent
 * 运行：node scripts/build_pptx.js
 * 依赖：npm install -g pptxgenjs
 */
const pptxgen = require("pptxgenjs");
const path = require("node:path");
const fs = require("node:fs");

const C = {
  bg: "0B1220",
  panel: "16213A",
  card: "1E293B",
  teal: "2DD4BF",
  blue: "0EA5E9",
  indigo: "6366F1",
  text: "F1F5F9",
  muted: "94A3B8",
  low: "22C55E",
  mid: "F59E0B",
  high: "EF4444",
};

const FONT = "Microsoft YaHei";
const OUT = path.resolve(__dirname, "..", "deliverables", "真鉴TruthGuard-路演PPT.pptx");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10" x 5.625"
pres.author = "TruthGuard 战队";
pres.title = "真鉴 TruthGuard · 美妆内容鉴真 Agent";

const shadow = () => ({
  type: "outer",
  color: "000000",
  blur: 10,
  offset: 3,
  angle: 135,
  opacity: 0.35,
});

function shell(slide, { title, kicker, page }) {
  slide.background = { color: C.bg };
  // 顶部装饰色块（视觉母题）
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 10,
    h: 0.06,
    fill: { color: C.teal },
  });
  slide.addShape(pres.shapes.OVAL, {
    x: 8.9,
    y: 0.25,
    w: 0.9,
    h: 0.9,
    fill: { color: C.teal, transparency: 88 },
  });

  if (kicker) {
    slide.addText(kicker, {
      x: 0.55,
      y: 0.38,
      w: 6,
      h: 0.28,
      margin: 0,
      fontFace: FONT,
      fontSize: 11,
      color: C.teal,
      charSpacing: 2,
    });
  }
  slide.addText(title, {
    x: 0.55,
    y: 0.66,
    w: 8.9,
    h: 0.62,
    margin: 0,
    fontFace: FONT,
    fontSize: 28,
    bold: true,
    color: C.text,
  });
  slide.addText(String(page).padStart(2, "0"), {
    x: 9.0,
    y: 4.95,
    w: 0.6,
    h: 0.3,
    margin: 0,
    fontFace: FONT,
    fontSize: 10,
    color: C.muted,
    align: "right",
  });
}

function card(slide, { x, y, w, h, title, body, accent = C.teal, num }) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x,
    y,
    w,
    h,
    fill: { color: C.card },
    line: { color: "FFFFFF", transparency: 92, width: 1 },
    shadow: shadow(),
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x,
    y,
    w: 0.07,
    h,
    fill: { color: accent },
  });
  if (num) {
    slide.addShape(pres.shapes.OVAL, {
      x: x + 0.25,
      y: y + 0.22,
      w: 0.42,
      h: 0.42,
      fill: { color: accent, transparency: 82 },
    });
    slide.addText(num, {
      x: x + 0.25,
      y: y + 0.22,
      w: 0.42,
      h: 0.42,
      margin: 0,
      fontFace: FONT,
      fontSize: 13,
      bold: true,
      color: accent,
      align: "center",
      valign: "middle",
    });
  }
  slide.addText(title, {
    x: x + (num ? 0.8 : 0.25),
    y: y + 0.22,
    w: w - (num ? 1.05 : 0.5),
    h: 0.4,
    margin: 0,
    fontFace: FONT,
    fontSize: 14,
    bold: true,
    color: C.text,
    valign: "middle",
  });
  slide.addText(body, {
    x: x + 0.25,
    y: y + (num ? 0.72 : 0.66),
    w: w - 0.5,
    h: h - (num ? 0.9 : 0.85),
    margin: 0,
    fontFace: FONT,
    fontSize: 11,
    color: C.muted,
    lineSpacingMultiple: 1.25,
  });
}

function table(slide, { rows, colW, x, y, w, headerFill = C.indigo }) {
  const data = rows.map((row, i) =>
    row.map((cell) => ({
      text: cell,
      options: {
        fill: { color: i === 0 ? headerFill : i % 2 ? "182338" : C.card },
        color: i === 0 ? "FFFFFF" : C.text,
        bold: i === 0,
        fontSize: i === 0 ? 11.5 : 10.5,
        fontFace: FONT,
        valign: "middle",
      },
    }))
  );
  slide.addTable(data, {
    x,
    y,
    w,
    colW,
    border: { pt: 0.5, color: "FFFFFF", transparency: 90 },
    rowH: 0.34,
    margin: [6, 8, 6, 8],
  });
}

// ============ 01 封面 ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addShape(pres.shapes.OVAL, {
    x: 6.6,
    y: -1.1,
    w: 5.2,
    h: 5.2,
    fill: { color: C.teal, transparency: 90 },
  });
  s.addShape(pres.shapes.OVAL, {
    x: -1.4,
    y: 3.4,
    w: 4.4,
    h: 4.4,
    fill: { color: C.indigo, transparency: 88 },
  });
  s.addText("欧莱雅第二届美妆科技黑客松 · 赛道二 信任守护师", {
    x: 0.7,
    y: 0.85,
    w: 8.6,
    h: 0.35,
    margin: 0,
    fontFace: FONT,
    fontSize: 13,
    color: C.teal,
    charSpacing: 1,
  });
  s.addText("真鉴 TruthGuard", {
    x: 0.7,
    y: 1.4,
    w: 8.6,
    h: 0.95,
    margin: 0,
    fontFace: FONT,
    fontSize: 46,
    bold: true,
    color: C.text,
  });
  s.addText("美妆内容多模态鉴真与风控 Agent", {
    x: 0.7,
    y: 2.42,
    w: 8.6,
    h: 0.5,
    margin: 0,
    fontFace: FONT,
    fontSize: 20,
    color: C.blue,
  });
  s.addText(
    "像素级取证 × 语义理解双层证据，从「识别」到「决策」的完整闭环",
    {
      x: 0.7,
      y: 3.05,
      w: 8.6,
      h: 0.4,
      margin: 0,
      fontFace: FONT,
      fontSize: 13,
      color: C.muted,
    }
  );
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.7,
    y: 3.75,
    w: 1.6,
    h: 0.04,
    fill: { color: C.teal },
  });
  s.addText("战队名称：____________    提交日期：2026.10", {
    x: 0.7,
    y: 4.05,
    w: 8.6,
    h: 0.35,
    margin: 0,
    fontFace: FONT,
    fontSize: 12,
    color: C.muted,
  });
}

// ============ 02 痛点 ============
{
  const s = pres.addSlide();
  shell(s, { title: "美妆内容生态正在被伪造侵蚀", kicker: "背景与痛点", page: 2 });
  const items = [
    ["效果对比图造假", "磨皮、换肤、拼贴「使用前后」对比图，人工审核主观、无法规模化", C.high],
    ["AIGC 虚假测评", "AI 生成「素人使用照」与编造体验文案，肉眼几乎无法分辨", C.indigo],
    ["功效与成分虚假宣传", "「七天美白」「医美级」等表述，关键词规则库容易被规避", C.mid],
    ["盗图与资质伪造", "拼接官方检测报告、伪造专利编号，需要像素级取证证据", C.blue],
  ];
  items.forEach(([t, b, c], i) => {
    const x = 0.55 + (i % 2) * 4.6;
    const y = 1.55 + Math.floor(i / 2) * 1.7;
    card(s, { x, y, w: 4.3, h: 1.5, title: t, body: b, accent: c });
  });
}

// ============ 03 方案定位 ============
{
  const s = pres.addSlide();
  shell(s, { title: "一句话定位与三层架构", kicker: "方案总览", page: 3 });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.55,
    y: 1.42,
    w: 8.9,
    h: 0.72,
    fill: { color: C.panel },
    line: { color: C.teal, transparency: 60, width: 1 },
  });
  s.addText(
    "真鉴 TruthGuard：输入一张商品图 + 一段推广文案，输出「证据链 + 风险等级 + 处置建议」的闭环决策报告",
    {
      x: 0.8,
      y: 1.42,
      w: 8.4,
      h: 0.72,
      margin: 0,
      fontFace: FONT,
      fontSize: 13,
      bold: true,
      color: C.text,
      valign: "middle",
    }
  );

  const layers = [
    ["L3 演示层", "React 界面：上传 → 流水线动效 → 热力图 → 风险报告", C.teal],
    ["L2 决策层", "RiskAgent：证据聚合 → 风险分级 → 处置动作 → 推理与建议", C.blue],
    ["L1 检测层", "图像取证引擎（ELA/噪声/EXIF） + 文案合规引擎（规则/LLM）", C.indigo],
  ];
  layers.forEach(([t, b, c], i) => {
    const y = 2.4 + i * 0.85;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.55,
      y,
      w: 8.9,
      h: 0.68,
      fill: { color: C.card },
      shadow: shadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.55,
      y,
      w: 0.09,
      h: 0.68,
      fill: { color: c },
    });
    s.addText(t, {
      x: 0.8,
      y,
      w: 1.5,
      h: 0.68,
      margin: 0,
      fontFace: FONT,
      fontSize: 13,
      bold: true,
      color: c,
      valign: "middle",
    });
    s.addText(b, {
      x: 2.4,
      y,
      w: 6.9,
      h: 0.68,
      margin: 0,
      fontFace: FONT,
      fontSize: 12,
      color: C.text,
      valign: "middle",
    });
  });
}

// ============ 04 创新点一：双层证据 ============
{
  const s = pres.addSlide();
  shell(s, { title: "创新点一：像素取证 + 语义理解的双层证据融合", kicker: "技术创新", page: 4 });
  table(s, {
    x: 0.55,
    y: 1.5,
    w: 8.9,
    colW: [1.5, 2.5, 2.4, 2.5],
    rows: [
      ["证据层", "技术手段", "强项", "在方案中的作用"],
      ["硬证据（像素层）", "ELA 误差分析、噪声一致性、EXIF 元数据", "客观可量化、可可视化、无需 GPU", "定位「哪里被改了」，生成篡改热力图"],
      ["软证据（语义层）", "多模态视觉模型 + 文本大模型", "理解美妆常识与合规语义", "判断「这句话是否越界」，补充隐性风险"],
    ],
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.55,
    y: 3.15,
    w: 8.9,
    h: 1.55,
    fill: { color: C.panel },
    shadow: shadow(),
  });
  s.addText("为什么不是单一模型？", {
    x: 0.85,
    y: 3.3,
    w: 8.3,
    h: 0.35,
    margin: 0,
    fontFace: FONT,
    fontSize: 14,
    bold: true,
    color: C.teal,
  });
  s.addText(
    [
      { text: "纯深度学习检测网络：需大量标注数据与 GPU，一个月周期难以稳定产出，且不可解释。", options: { bullet: true, breakLine: true } },
      { text: "纯大模型调用：黑箱、无法定位篡改区域、API 抖动影响演示。", options: { bullet: true, breakLine: true } },
      { text: "我们的选择：双层证据加权融合 —— 硬证据可解释、软证据补语义，API 不可用时自动降级为纯本地取证。", options: { bullet: true } },
    ],
    {
      x: 0.85,
      y: 3.7,
      w: 8.3,
      h: 0.95,
      margin: 0,
      fontFace: FONT,
      fontSize: 11.5,
      color: C.muted,
      paraSpaceAfter: 6,
    }
  );
}

// ============ 05 创新点二：合规规则库 ============
{
  const s = pres.addSlide();
  shell(s, { title: "创新点二：美妆垂类宣称合规知识库", kicker: "技术创新", page: 5 });
  const rules = [
    ["医疗功效宣称", "治疗 / 医美级 / 抗炎杀菌", "红线", C.high],
    ["时限与效果承诺", "七天美白 / 立竿见影 / 永久", "高", C.mid],
    ["绝对化用语", "100% / 第一 / 最强 / 顶级", "中", C.blue],
    ["无来源背书", "权威认证 / 专利号 / 检测报告", "红线", C.high],
    ["成分伪概念", "食品级 / 纯天然 / 干细胞", "中", C.blue],
    ["编造使用体验", "万人好评 / 0 差评 / 用了都说好", "中", C.indigo],
  ];
  rules.forEach(([t, b, sev, c], i) => {
    const x = 0.55 + (i % 3) * 3.03;
    const y = 1.5 + Math.floor(i / 3) * 1.6;
    card(s, { x, y, w: 2.85, h: 1.4, title: t, body: `${b}`, accent: c });
    s.addText(`严重度：${sev}`, {
      x: x + 0.25,
      y: y + 1.02,
      w: 2.4,
      h: 0.28,
      margin: 0,
      fontFace: FONT,
      fontSize: 10.5,
      bold: true,
      color: c,
    });
  });
  s.addText(
    "规则依据《化妆品监督管理条例》《化妆品标签管理办法》《广告法》中可机读的宣称红线整理，命中红线直接升级处置等级。",
    {
      x: 0.55,
      y: 4.75,
      w: 8.9,
      h: 0.35,
      margin: 0,
      fontFace: FONT,
      fontSize: 11,
      color: C.muted,
    }
  );
}

// ============ 06 创新点三：闭环 Agent ============
{
  const s = pres.addSlide();
  shell(s, { title: "创新点三：从「识别」到「决策」的闭环 Agent", kicker: "技术创新", page: 6 });
  table(s, {
    x: 0.55,
    y: 1.5,
    w: 8.9,
    colW: [1.5, 1.3, 2.2, 3.9],
    rows: [
      ["风险总分", "等级", "处置动作", "面向平台/创作者的建议"],
      ["< 30", "低风险", "通过上架", "正常展示，报告归档，纳入例行抽检"],
      ["30 ~ 60", "中风险", "转人工复核", "优先查看热力图标记区域，核对功效与成分表"],
      ["60 ~ 80", "高风险", "警示标记并限流", "添加风险标签降权，要求补充资质证明"],
      ["≥ 80 或命中红线", "高风险", "建议下架并触发合规工单", "下架留证，推送整改通知，历史内容批量复检"],
    ],
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.55,
    y: 3.75,
    w: 8.9,
    h: 0.95,
    fill: { color: C.panel },
  });
  s.addText(
    "红线优先原则：命中「医疗功效宣称」或「伪造资质背书」时，无视统计分数直接判高风险并建议下架 —— 业务规则优先于模型分数，这才是可用的风控 Agent。",
    {
      x: 0.85,
      y: 3.75,
      w: 8.3,
      h: 0.95,
      margin: 0,
      fontFace: FONT,
      fontSize: 12,
      color: C.text,
      valign: "middle",
    }
  );
}

// ============ 07 创新点四：可视化 ============
{
  const s = pres.addSlide();
  shell(s, { title: "创新点四：可解释的证据可视化", kicker: "技术创新", page: 7 });
  const vis = [
    ["ELA 热力图", "重压缩误差叠加原图，青→黄→红标注篡改概率，可疑区域自动框选", C.high],
    ["证据卡片链", "每条证据含来源标签、置信度条与文字说明，逐条渐入呈现", C.blue],
    ["流水线动效", "图像取证 → 语义分析 → Agent 决策，三阶段实时进度可视化", C.teal],
    ["风险仪表盘", "风险分环 + 等级徽章 + 处置按钮，一键下发中台指令", C.indigo],
  ];
  vis.forEach(([t, b, c], i) => {
    card(s, { x: 0.55, y: 1.5 + i * 0.82, w: 8.9, h: 0.72, title: t, body: b, accent: c, num: String(i + 1) });
  });
}

// ============ 08 演示流程 ============
{
  const s = pres.addSlide();
  shell(s, { title: "系统演示：一条内容 4 步走完闭环", kicker: "产品演示", page: 8 });
  const steps = [
    ["01 提交内容", "拖拽上传商品图，粘贴推广文案，支持一键填充示例"],
    ["02 三阶段检测", "图像取证、语义分析、Agent 决策流水线依次执行"],
    ["03 证据呈现", "原图/热力图切换查看，右侧展示逐条证据与置信度"],
    ["04 处置执行", "输出风险等级与处置建议，一键下发复核/警示/下架"],
  ];
  steps.forEach(([t, b], i) => {
    const x = 0.55 + i * 2.32;
    card(s, { x, y: 1.55, w: 2.1, h: 2.1, title: t, body: b, accent: i === 3 ? C.mid : C.teal });
    if (i < 3) {
      s.addShape(pres.shapes.RECTANGLE, {
        x: x + 2.12,
        y: 2.5,
        w: 0.2,
        h: 0.06,
        fill: { color: C.muted, transparency: 40 },
      });
    }
  });
  s.addText(
    "演示三连击：① 明显篡改图 + 违规文案 → 高风险/下架；② 正常图 + 合规文案 → 低风险/通过；③ 灰色地带 → 中风险/人工复核。",
    {
      x: 0.55,
      y: 4.05,
      w: 8.9,
      h: 0.6,
      margin: 0,
      fontFace: FONT,
      fontSize: 12,
      color: C.muted,
    }
  );
}

// ============ 09 实验结果 ============
{
  const s = pres.addSlide();
  shell(s, { title: "实验结果：规则层基线可量化、可复现", kicker: "效果验证", page: 9 });
  const stats = [
    ["93.3%", "违规文案召回率", "15 条违规样本命中 14 条", C.low],
    ["0%", "合规文案误报率", "10 条合规样本零误报", C.teal],
    ["100%", "告警精确率", "告警样本全部为真实违规", C.blue],
    ["0/5", "灰色地带误杀", "轻度夸大未被一刀切", C.mid],
  ];
  stats.forEach(([n, t, b, c], i) => {
    const x = 0.55 + i * 2.32;
    s.addShape(pres.shapes.RECTANGLE, {
      x,
      y: 1.5,
      w: 2.1,
      h: 1.55,
      fill: { color: C.card },
      shadow: shadow(),
    });
    s.addText(n, {
      x,
      y: 1.62,
      w: 2.1,
      h: 0.6,
      margin: 0,
      fontFace: FONT,
      fontSize: 30,
      bold: true,
      color: c,
      align: "center",
    });
    s.addText(t, {
      x,
      y: 2.25,
      w: 2.1,
      h: 0.3,
      margin: 0,
      fontFace: FONT,
      fontSize: 11.5,
      bold: true,
      color: C.text,
      align: "center",
    });
    s.addText(b, {
      x: x + 0.12,
      y: 2.58,
      w: 1.86,
      h: 0.4,
      margin: 0,
      fontFace: FONT,
      fontSize: 10,
      color: C.muted,
      align: "center",
    });
  });
  s.addText(
    "图像取证对照：真实商品图风险分 5.9（低风险/通过），含拼接区域样本 55.7（高风险/下架）；合成样本用于验证链路，后续将补充真实素材扩大评测集。",
    {
      x: 0.55,
      y: 3.35,
      w: 8.9,
      h: 0.5,
      margin: 0,
      fontFace: FONT,
      fontSize: 11.5,
      color: C.muted,
    }
  );
  s.addText(
    [
      { text: "定位清晰：辅助决策而非终审，机器初筛高危 + 人审复核，与人协同而非替代人。", options: { bullet: true } },
    ],
    { x: 0.55, y: 3.95, w: 8.9, h: 0.35, margin: 0, fontFace: FONT, fontSize: 11.5, color: C.text }
  );
}

// ============ 10 技术架构 ============
{
  const s = pres.addSlide();
  shell(s, { title: "工程实现：模块清晰、可降级、易协作", kicker: "技术架构", page: 10 });
  table(s, {
    x: 0.55,
    y: 1.45,
    w: 8.9,
    colW: [1.9, 2.3, 4.7],
    rows: [
      ["模块", "技术栈", "职责"],
      ["图像取证", "OpenCV + Pillow + NumPy", "ELA 误差分析、噪声一致性、EXIF/元数据检查、热力图生成"],
      ["文案检测", "规则库 + 大模型 API", "美妆宣称合规红线命中与隐性夸大、编造体验的语义判定"],
      ["Agent 决策", "Python + 大模型结构化输出", "证据加权聚合、风险分级、处置动作与角色化建议"],
      ["服务与接口", "FastAPI + Uvicorn", "统一检测入口、自动接口文档、超时降级与并发处理"],
      ["演示界面", "React 18 + Vite + Tailwind", "上传、流水线动效、证据可视化与处置闭环"],
    ],
  });
  s.addText(
    "工程细节：API Key 经 .env 注入且不入库；图像处理前缩放至 1024px；LLM 超时 30s 自动降级为本地取证；Git 分支策略与文件所有权保障 5 人并行开发。",
    {
      x: 0.55,
      y: 4.0,
      w: 8.9,
      h: 0.6,
      margin: 0,
      fontFace: FONT,
      fontSize: 11.5,
      color: C.muted,
    }
  );
}

// ============ 11 落地价值 ============
{
  const s = pres.addSlide();
  shell(s, { title: "为什么这对欧莱雅有价值", kicker: "商业价值", page: 11 });
  const values = [
    ["降低合规风险", "自动拦截违规宣称，规避监管处罚与舆情风险", C.high],
    ["保护品牌信任", "遏制盗图与假测评，守护创作者与消费者之间的真实", C.teal],
    ["审核降本增效", "全量人审变为「机器初筛 + 人审高危」，审核产能提升", C.blue],
    ["能力可复制", "取证 + 规则 + Agent 框架可迁移至护肤、彩妆、香氛各品类", C.indigo],
  ];
  values.forEach(([t, b, c], i) => {
    const x = 0.55 + (i % 2) * 4.6;
    const y = 1.55 + Math.floor(i / 2) * 1.7;
    card(s, { x, y, w: 4.3, h: 1.5, title: t, body: b, accent: c });
  });
}

// ============ 12 路线图 ============
{
  const s = pres.addSlide();
  shell(s, { title: "落地路线图：三阶段演进", kicker: "未来规划", page: 12 });
  const phases = [
    ["第一阶段 · 0-3 月", "接入内容审核中台，做人机协同初筛；沉淀真实篡改样本库", C.teal],
    ["第二阶段 · 3-6 月", "用积累数据训练美妆专用检测模型，接入品牌自有商品图库做盗图比对", C.blue],
    ["第三阶段 · 6-12 月", "覆盖直播切片与短视频，扩展到香氛、洗护品类，输出品牌信任指数", C.indigo],
  ];
  phases.forEach(([t, b, c], i) => {
    const y = 1.55 + i * 1.15;
    s.addShape(pres.shapes.RECTANGLE, {
      x: 0.55,
      y,
      w: 8.9,
      h: 0.95,
      fill: { color: C.card },
      shadow: shadow(),
    });
    s.addShape(pres.shapes.OVAL, { x: 0.78, y: y + 0.26, w: 0.42, h: 0.42, fill: { color: c } });
    s.addText(String(i + 1), {
      x: 0.78,
      y: y + 0.26,
      w: 0.42,
      h: 0.42,
      margin: 0,
      fontFace: FONT,
      fontSize: 13,
      bold: true,
      color: "0B1220",
      align: "center",
      valign: "middle",
    });
    s.addText(t, {
      x: 1.4,
      y: y + 0.1,
      w: 7.9,
      h: 0.35,
      margin: 0,
      fontFace: FONT,
      fontSize: 13,
      bold: true,
      color: c,
    });
    s.addText(b, {
      x: 1.4,
      y: y + 0.45,
      w: 7.9,
      h: 0.4,
      margin: 0,
      fontFace: FONT,
      fontSize: 11.5,
      color: C.muted,
    });
  });
}

// ============ 13 团队与进度 ============
{
  const s = pres.addSlide();
  shell(s, { title: "团队分工与当前进度", kicker: "团队", page: 13 });
  table(s, {
    x: 0.55,
    y: 1.45,
    w: 8.9,
    colW: [1.9, 3.6, 1.6, 1.8],
    rows: [
      ["角色", "主要职责", "负责人", "状态"],
      ["队长 / 产品", "方案设计、文档、路演与对外对接", "待填", "进行中"],
      ["算法 A", "图像取证引擎与视觉模型接入", "待填", "已完成"],
      ["算法 B", "文案合规规则库与样本集", "待填", "已完成"],
      ["后端 / Agent", "决策层、接口与降级策略", "待填", "已完成"],
      ["前端", "演示界面与交互实现", "待填", "已完成"],
    ],
  });
  s.addText(
    "里程碑：仓库与方案 → 检测模块 → Agent 决策 → 演示界面 → 样本与评测 → 路演提交，全部通过 Git 分支协作同步。",
    {
      x: 0.55,
      y: 4.0,
      w: 8.9,
      h: 0.5,
      margin: 0,
      fontFace: FONT,
      fontSize: 11.5,
      color: C.muted,
    }
  );
}

// ============ 14 Q&A ============
{
  const s = pres.addSlide();
  shell(s, { title: "可能被问到的问题，我们准备好了", kicker: "问答准备", page: 14 });
  const qa = [
    ["检测准确率到底多少？", "规则层基线召回 93.3%、误报 0%；定位为辅助决策，机器初筛 + 人审高危。", C.blue],
    ["为什么不训练专用检测模型？", "周期内数据与算力受限；取证特征可解释性更强，更契合风控场景。", C.teal],
    ["大模型幻觉怎么处理？", "规则库兜底 + 双通道交叉验证 + 证据权重设计，API 异常自动降级。", C.mid],
    ["如何落地到真实业务？", "先接内容审核中台做人机协同，再累积数据训练专用模型，最后扩展品类。", C.indigo],
  ];
  qa.forEach(([t, b, c], i) => {
    const x = 0.55 + (i % 2) * 4.6;
    const y = 1.5 + Math.floor(i / 2) * 1.65;
    card(s, { x, y, w: 4.3, h: 1.45, title: t, body: b, accent: c });
  });
}

// ============ 15 结尾 ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s.addShape(pres.shapes.OVAL, {
    x: 3.2,
    y: 0.6,
    w: 3.6,
    h: 3.6,
    fill: { color: C.teal, transparency: 90 },
  });
  s.addText("让每一条美妆内容，都可被验证", {
    x: 1,
    y: 1.75,
    w: 8,
    h: 0.8,
    margin: 0,
    fontFace: FONT,
    fontSize: 34,
    bold: true,
    color: C.text,
    align: "center",
  });
  s.addText("真鉴 TruthGuard · 守护创作者与消费者之间的真实", {
    x: 1,
    y: 2.7,
    w: 8,
    h: 0.5,
    margin: 0,
    fontFace: FONT,
    fontSize: 16,
    color: C.teal,
    align: "center",
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 4.35, y: 3.45, w: 1.3, h: 0.04, fill: { color: C.teal } });
  s.addText("感谢聆听 · 欢迎提问", {
    x: 1,
    y: 3.75,
    w: 8,
    h: 0.4,
    margin: 0,
    fontFace: FONT,
    fontSize: 13,
    color: C.muted,
    align: "center",
  });
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });

pres
  .writeFile({ fileName: OUT })
  .then(() => console.log("PPT 已生成：" + OUT))
  .catch((e) => console.error("生成失败：", e));
