import type { RiskReport } from "@/types";

/** 后端不可用时用于界面演示的样例报告（明确标注为演示数据）。 */
export const MOCK_REPORT: RiskReport = {
  risk_level: "high",
  risk_score: 67.2,
  action: "takedown",
  reasoning:
    "命中宣称合规红线，综合 7 条证据加权聚合得风险分 67.2，主要依据：噪声一致性分析（置信度 1.00）；医疗功效宣称（置信度 0.90）；时限与效果承诺（置信度 0.78）。判定为高风险，处置动作：建议下架并触发合规工单。",
  suggestions: [
    "立即下架该内容并留存取证快照，作为后续申诉依据",
    "向创作者推送合规整改通知，说明具体违规条款",
    "将同账号历史内容纳入批量复检队列",
    "删除涉及疾病治疗、医疗器械与医美项目的表述，化妆品不得宣称医疗功效",
  ],
  degraded: true,
  elapsed_ms: 0,
  image: {
    width: 960,
    height: 960,
    format: "JPEG",
    heatmap: null,
    image_score: 56.9,
    findings: ["JPEG 图像缺少 EXIF 拍摄参数，通常经过二次导出或编辑"],
    evidence: [
      {
        source: "forensics",
        name: "ELA 误差级别分析",
        score: 0.46,
        weight: 0.25,
        description: "重压缩误差分布不均，局部异常区域置信度 0.46",
        severity: "medium",
        region: [0.5, 0.3, 0.36, 0.3],
      },
      {
        source: "forensics",
        name: "噪声一致性分析",
        score: 1.0,
        weight: 0.15,
        description: "分块噪声方差离散，疑似存在拼接或外来区域（1.00）",
        severity: "high",
      },
      {
        source: "forensics",
        name: "EXIF / 元数据检查",
        score: 0.25,
        weight: 0.1,
        description: "JPEG 图像缺少 EXIF 拍摄参数，通常经过二次导出或编辑",
        severity: "low",
      },
    ],
  },
  text: {
    text_score: 90,
    redline: true,
    hits: [
      "医疗功效宣称：命中「医美级」",
      "时限与效果承诺：命中「七天美白」",
      "绝对化用语：命中「100%」",
    ],
    advice: ["删除涉及疾病治疗、医疗器械与医美项目的表述，化妆品不得宣称医疗功效"],
    evidence: [
      {
        source: "text_rule",
        name: "宣称合规命中 · 医疗功效宣称",
        score: 0.9,
        weight: 0.15,
        description: "命中敏感表述：医美级",
        severity: "high",
      },
      {
        source: "text_rule",
        name: "宣称合规命中 · 时限与效果承诺",
        score: 0.78,
        weight: 0.15,
        description: "命中敏感表述：七天美白",
        severity: "high",
      },
      {
        source: "text_rule",
        name: "宣称合规命中 · 绝对化用语",
        score: 0.6,
        weight: 0.15,
        description: "命中敏感表述：100%",
        severity: "medium",
      },
    ],
  },
};
