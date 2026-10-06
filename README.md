# git-demo · 多场景「鉴真 Agent」仓库

一个按**场景（scenario）**组织的 Agent 工程仓库：每个场景是一套完整的「受理 → 取证 → 核验 → 裁决 → 处置」链路，共用同一套工程约定与协作规范。

> 判定对象始终是**信源/凭证的伪造风险**，不是产品质量优劣，也不作司法终局定论。

---

## 一、仓库地图

| 路径 | 是什么 | 状态 |
| --- | --- | --- |
| `backend/` | **场景A**：电商售后客诉凭证鉴真 Agent（Step0–7 编排、视觉/像素/业务工具、交叉验证与裁决、阈值外置） | 可用 |
| `data/seed/` | 场景A 的种子数据：工单、订单、物流、账号、聊天、商品 + 视觉/像素回放 fixtures | 可用 |
| `scripts/` | 场景A 辅助脚本（生成占位图等） | 可用 |
| `docs/` | 全部文档，按场景分目录，入口见 [`docs/README.md`](docs/README.md) | 可用 |
| `scenarios/scene-b-geo-forensics/` | **场景B**：美妆品牌 GEO 伪造信源核验 Agent（本次新增） | 开发中 |
| `archive/v0-truthguard/` | v0 版「真鉴 TruthGuard」完整旧项目（FastAPI + React + 路演材料），**仅归档，不再维护** | 归档 |

> 目录命名的历史包袱：`backend/` 实际是场景A，为减少队友本地路径迁移成本**暂不重命名**；新场景一律放 `scenarios/<scene-name>/`。

---

## 二、场景索引

| 场景 | 一句话 | 入口 | 文档 |
| --- | --- | --- | --- |
| **A · 电商售后客诉凭证鉴真** | 用户上传破损/漏液/少件照片，结合订单、物流、历史工单判断凭证真伪与责任归属 | `backend/app/main.py` | [`docs/scene-a-ecommerce/`](docs/scene-a-ecommerce/) |
| **B · 美妆 GEO 伪造信源核验** | 品牌/监管方上传证书图、检测报告图、专家头像或一段文案，判断是否存在伪造专家、伪造证书、虚构背书等 GEO 污染信源 | `scenarios/scene-b-geo-forensics/backend/app/main.py` | [`docs/scene-b-geo-forensics/`](docs/scene-b-geo-forensics/) |

---

## 三、快速开始

### 0. 准备环境

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 1. 场景A · 售后客诉凭证鉴真

```powershell
pip install -r backend/requirements.txt
copy .env.example .env          # 可选：不填 Key 即进入 Mock 模式，流程完整可跑
uvicorn backend.app.main:app --reload --port 8000
```

打开 http://127.0.0.1:8000/docs 查看接口，`/api/health` 可确认当前是 mock 还是 llm 模式。

### 2. 场景B · 美妆 GEO 伪造信源核验

```powershell
pip install -r scenarios/scene-b-geo-forensics/requirements.txt
cd scenarios/scene-b-geo-forensics/backend
copy ..\.env.example ..\.env    # 可选
python -m uvicorn app.main:app --reload --port 8001
```

打开 http://127.0.0.1:8001 使用控制台（内置一键示例，无 Key 也能完整演示）。

---

## 四、运行模式（两个场景通用）

| 模式 | 触发条件 | 行为 |
| --- | --- | --- |
| `mock` | 未配置任何 API Key | 全部外部能力走本地回放数据，流程完整可演示，结果标注为演示数据 |
| `llm` / `real` | 配置了 Key | 真实调用多模态模型、检索、官方库抓取 |
| 自动降级 | 真实调用超时/失败 | 单工具降级为不可用并标记 `degraded`，**绝不把"查不到"当成"造假"**，主流程不中断 |

关键语义：**`查无结果 ≠ 伪造`**。只有"信源存在但与声明冲突"才构成降信证据；"查不到"只进入「缺失材料清单」并转人工复核。

---

## 五、环境变量

复制 `.env.example` 为 `.env`（已被 `.gitignore` 忽略，**切勿提交密钥**）。两个场景共用同一份 `.env`，变量按分组注释区分：

- 模型提供方：`PROVIDER_ORDER`、`DASHSCOPE_*`、`OPENAI_*`、`DEEPSEEK_*`
- 检索能力：`TAVILY_API_KEY`（场景B 用）
- 服务参数：`LLM_TIMEOUT_SECONDS`、`LLM_CACHE`

---

## 六、协作规范

- **分支**：`main` 为保护分支；开发一律 `feat/<scope>`、`fix/<scope>`、`docs/<scope>`
- **流程**：feature 分支推送 → GitHub 发起 PR → 至少一人 review → 合并 `main`
- **提交**：`<type>(<scope>): <subject>`，如 `feat(scene-b): 新增药监局备案核验工具`
- **密钥**：只放 `.env`，禁止写进代码、日志、测试用例与 issue
- **大文件**：图片/模型/PPT 不入库用二进制，走 `.gitignore` 排除或外部网盘

---

## 七、边界声明

本仓库所有输出均为**风险研判与举证辅助**，不构成对任何主体的真伪定论、质量评价或法律意见；结论须由人工复核后使用。
