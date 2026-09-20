"""文案鉴伪引擎：美妆垂类宣称合规规则库（硬规则）+ LLM 语义判定（软证据）。

规则库依据《化妆品监督管理条例》《化妆品标签管理办法》《广告法》中可机读的宣称红线整理。
"""
from __future__ import annotations

import re

from .. import config
from ..schemas import Evidence, TextAnalysis
from . import llm_client

# category, 标签, 严重度, 基础分数, 是否红线, 正则, 修改建议
RULES: list[dict] = [
    {
        "key": "medical",
        "label": "医疗功效宣称",
        "severity": "high",
        "score": 0.9,
        "redline": True,
        "patterns": [
            r"治疗|治愈|疗效|根治",
            r"抗炎|消炎|杀菌|灭菌|抗菌",
            r"医用|医美级|药用|处方|激素",
            r"肉毒素|水光针|激光|针剂",
        ],
        "advice": "删除涉及疾病治疗、医疗器械与医美项目的表述，化妆品不得宣称医疗功效。",
    },
    {
        "key": "time_promise",
        "label": "时限与效果承诺",
        "severity": "high",
        "score": 0.78,
        "redline": False,
        "patterns": [
            r"[一二三两四五六七八九十\d]+\s*天(?:美白|祛斑|见效|逆龄|淡纹|瘦脸)",
            r"一夜(?:回春|变白|祛皱)|立竿见影|瞬间(?:变白|祛皱)|秒变",
            r"永久|永远(?:不反弹|有效)|一劳永逸",
        ],
        "advice": "删除对见效时间或永久效果的承诺，改为描述使用感受与成分作用机理。",
    },
    {
        "key": "absolute",
        "label": "绝对化用语",
        "severity": "medium",
        "score": 0.6,
        "redline": False,
        "patterns": [
            r"100\s*%|百分百|100%有效",
            r"全网(?:第一|最低|最全)|行业第一|销量第一|no\.?1",
            r"最好|最佳|最强|最有效|顶级|极致|无敌",
        ],
        "advice": "避免使用最高级与绝对化表述，改用可验证的数据或第三方测评结果。",
    },
    {
        "key": "fake_endorsement",
        "label": "无来源背书与伪造资质",
        "severity": "high",
        "score": 0.72,
        "redline": True,
        "patterns": [
            r"权威(?:认证|机构)认证|国家(?:级)?认证|官方认证",
            r"三甲医院|皮肤科医生(?:推荐|认证)|临床医学验证",
            r"专利号?[:：]?\s*[A-Z]{0,2}\d{6,}",
            r"检测报告(?:编号)?[:：]?\s*[A-Z0-9-]{6,}",
        ],
        "advice": "补充可核验的资质编号、检测机构与报告链接，无法提供请删除相关表述。",
    },
    {
        "key": "ingredient_fake",
        "label": "成分虚假与伪概念",
        "severity": "medium",
        "score": 0.66,
        "redline": False,
        "patterns": [
            r"食品级|可食用|纯天然|无添加(?:剂)?(?!表)|0添加|零添加",
            r"不含任何化学成分|无任何化学",
            r"干细胞|基因(?:修复|抗衰)|量子(?:美肤|渗透)",
        ],
        "advice": "核对实际成分表，删除'食品级''纯天然''干细胞'等监管点名的伪概念表述。",
    },
    {
        "key": "fabricated_review",
        "label": "编造使用体验",
        "severity": "medium",
        "score": 0.55,
        "redline": False,
        "patterns": [
            r"万人好评|全网疯抢|回购率\s*\d{2,}\s*%|0差评|零差评|无一差评",
            r"用了都说好|所有人都说|身边朋友都在用",
            r"用了(?:一|两|三|几)次就(?:白了|祛了|好了)",
        ],
        "advice": "补充真实使用周期、肤质前提与个体差异说明，避免群体性夸张表述。",
    },
]

LLM_SYSTEM = (
    "你是美妆内容合规审核专家。请判断文案是否存在虚假宣传、夸大功效或编造使用体验，"
    "只输出 JSON：risk(0~1)、findings(字符串数组，每条不超过30字)、advice(字符串数组)。"
)


def _rule_hits(text: str) -> list[tuple[dict, list[str]]]:
    hits: list[tuple[dict, list[str]]] = []
    for rule in RULES:
        matched: list[str] = []
        for pat in rule["patterns"]:
            matched.extend(m.group(0) for m in re.finditer(pat, text))
        if matched:
            hits.append((rule, sorted(set(matched))[:6]))
    return hits


def analyze(text: str, use_llm: bool = True) -> TextAnalysis:
    """文案检测主入口：规则命中优先，LLM 补充隐性风险。"""
    evidence: list[Evidence] = []
    hits_desc: list[str] = []
    advice: list[str] = []
    redline = False
    rule_score = 0.0

    for rule, matched in _rule_hits(text):
        sev = rule["severity"]
        score = rule["score"]
        rule_score = max(rule_score, score if sev == "high" else score * 0.9)
        redline = redline or bool(rule["redline"])
        hits_desc.append(f"{rule['label']}：命中「{'/'.join(matched[:3])}」")
        advice.append(rule["advice"])
        evidence.append(
            Evidence(
                source="text_rule",
                name=f"宣称合规命中 · {rule['label']}",
                score=score,
                weight=config.EVIDENCE_WEIGHT["text_rule"],
                description=f"命中敏感表述：{'、'.join(matched[:4])}",
                severity=sev,
            )
        )

    if not hits_desc:
        evidence.append(
            Evidence(
                source="text_rule",
                name="宣称合规规则库扫描",
                score=0.08,
                weight=config.EVIDENCE_WEIGHT["text_rule"],
                description="未命中绝对化用语、医疗功效、时限承诺等已知宣称红线",
                severity="low",
            )
        )

    # ---- LLM 语义补充 ----
    if use_llm and config.ENABLE_LLM:
        payload = llm_client.chat_json(
            [
                {"role": "system", "content": LLM_SYSTEM},
                {"role": "user", "content": f"待审核文案：\n{text}"},
            ],
            model=config.TEXT_MODEL,
            max_tokens=400,
        )
        if payload:
            try:
                llm_risk = max(0.0, min(1.0, float(payload.get("risk", 0.0))))
            except (TypeError, ValueError):
                llm_risk = 0.0
            findings = [str(x) for x in payload.get("findings", [])][:4]
            advice.extend(str(x) for x in payload.get("advice", [])[:3])
            evidence.append(
                Evidence(
                    source="text_llm",
                    name="文案语义风险分析",
                    score=round(llm_risk, 3),
                    weight=config.EVIDENCE_WEIGHT["text_llm"],
                    description=(
                        "；".join(findings) if findings else
                        f"语义模型评估可疑度 {llm_risk:.2f}"
                    ),
                    severity="high" if llm_risk >= 0.6 else "medium" if llm_risk >= 0.35 else "low",
                )
            )

    text_score = 100.0 * max([e.score for e in evidence], default=0.0)
    return TextAnalysis(
        evidence=evidence,
        hits=hits_desc,
        text_score=round(text_score, 2),
        redline=redline,
        advice=list(dict.fromkeys(advice)),
    )
