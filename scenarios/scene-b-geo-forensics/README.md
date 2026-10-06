# 场景B · 美妆 GEO 伪造信源核验 Agent

判断一张美妆图片（证书图、检测报告图、专家头像）或一段文案（功效宣称、专家/机构背书、数据引用、排名话术）是否存在**伪造 GEO 信源**的可能，并输出可举证、可复核的核验报告。

> 判定对象是信源伪造风险，不是产品质量优劣，不作司法终局定论。

工作流设计见 [`docs/scene-b-geo-forensics/01-工作流设计.md`](../../docs/scene-b-geo-forensics/01-工作流设计.md)。

## 快速开始

```powershell
pip install -r requirements.txt
cd backend
python -m uvicorn app.main:app --reload --port 8001
```

打开 http://127.0.0.1:8001 使用控制台；接口文档 http://127.0.0.1:8001/docs 。

不想开浏览器时，用命令行冒烟跑通三个示例案例：

```powershell
cd backend
python run_smoke.py
```

## 目录结构

```
scenarios/scene-b-geo-forensics/
├── requirements.txt
├── backend/
│   ├── run_smoke.py                命令行冒烟（无需浏览器）
│   ├── config/
│   │   ├── thresholds.yaml         阈值、证据权重、红线开关、词表
│   │   └── mock_sources.yaml       虚构信源库 + OCR 回放 + 示例案例
│   └── app/
│       ├── config.py               路径与运行模式（AGENT_MODE）
│       ├── schemas.py              数据契约（Evidence / Claim / Verdict / Report）
│       ├── orchestrator.py         S0–S6 编排，逐步产出步骤事件
│       ├── repo.py                 上传落盘、案例读写
│       ├── main.py                 FastAPI 接口 + SSE + 静态控制台
│       ├── tools/                  工具适配层（备案库/证书/机构/专家/检索/传播）
│       └── fusion/                 规则裁决（rules）与处置建议（disposition）
├── web/                            单页控制台（原生 HTML/CSS/JS）
└── data/                           uploads/ 上传件、cases/ 案例落盘
```

## 运行模式

| 模式 | 条件 | 行为 |
| --- | --- | --- |
| `mock` | 未配置任何 Key，或 `AGENT_MODE=mock` | 走 `config/mock_sources.yaml` 回放，流程完整可演示 |
| `real` | `AGENT_MODE=real` | 强制真实调用 |
| `auto`（默认） | 有 Key 走真实，失败单工具降级 | 推荐 |

在仓库根目录 `.env` 中配置（复制 `.env.example`）：

```
DASHSCOPE_API_KEY=sk-...            # 通义 qwen-vl（多模态 OCR）
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_VISION_MODEL=qwen-vl-max-latest
TAVILY_API_KEY=tvly-...             # 联网检索（机构/专家/传播核验）
AGENT_MODE=auto
TOOL_TIMEOUT_SECONDS=15
```

未配置 Key 也能完整演示，界面右上角会显示当前模式。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 当前模式、模型、是否检测到 Key |
| GET | `/api/samples` | 三个示例案例 |
| POST | `/api/cases` | 提交核验（multipart：text/brand/product/source_url/images/image_names） |
| GET | `/api/cases/{id}/stream` | SSE 步骤事件流 |
| GET | `/api/cases/{id}` | 案例详情 |
| POST | `/api/cases/{id}/override` | 人工覆盖某条证据状态并重算结论 |
| GET | `/api/cases/{id}/export?format=md\|json` | 导出举证材料 |
| GET | `/api/cases` | 历史案例列表 |

## 判定要点

- **查无结果 ≠ 伪造**：`NOT_FOUND` 只进入「缺失材料清单」，只有 `CONTRADICTED`（信源存在但与声明冲突）才是强降信信号
- **红线一票否决**：证书/备案主体不符、机构确认不存在、专家与机构冲突、核心宣称使用禁用医疗用语
- **四层结论**：可核验 / 存疑 / 高度疑似伪造 / 证据不足 + 置信度，每条结论必挂证据链
- **阈值外置**：权重与红线开关都在 `backend/config/thresholds.yaml`，改配置不改代码

## 已知限制

- S2 技术取证本期为占位节点（ELA / EXIF / AI 生成痕迹尚未实现），权重槽位已保留
- 药监局无开放 API，抓取失败一律降级为「不可验」并转人工复核
- 示例数据全部虚构，不指向任何真实主体
