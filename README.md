# 真鉴 TruthGuard · 美妆内容鉴真 Agent

> 欧莱雅第二届美妆科技黑客松 · 赛道二「TRUTH GUARDIAN 信任守护师 —— 创造者的 AI 卫士」
> 提交截止：2026-10-20

---

## 一、我们做什么

面向美妆内容生态的多模态鉴真与风控 Agent。输入**一张商品图 + 一段推广文案**，系统自动完成：

```
上传 → 图像取证 → 语义分析 → Agent 决策 → 证据可视化 → 风险等级 + 处置建议
```

核心是**从"识别"到"决策"的完整闭环**：不只判断真伪，还给出该做什么。

---

## 二、技术创新速览

| 创新点 | 说明 |
| --- | --- |
| 双层证据融合 | 像素级取证（ELA/噪声/EXIF）+ 语义级理解（多模态大模型），互补而非黑箱 |
| 美妆垂类合规库 | 绝对化用语、医疗功效、时限承诺、伪造背书、成分造假等可机读规则 |
| 闭环决策 Agent | 证据聚合 → 风险分级 → 处置动作（通过/复核/警示/下架）+ 角色化建议 |
| 可解释可视化 | 篡改区域热力图 + 逐条证据卡，算法判断变成人能看懂的证据 |

详见 [`docs/01-赛题分析与总体方案.md`](docs/01-赛题分析与总体方案.md)。

---

## 三、快速开始

### 3.1 环境要求

- Python **3.10+**
- Node.js **18+**
-（可选）通义千问 / DeepSeek API Key

### 3.2 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 配置密钥（可选，不配也能跑本地取证模式）
cp ../.env.example ../.env

uvicorn app.main:app --reload --port 8000
```

打开 `http://localhost:8000/docs` 查看自动生成的接口文档。

### 3.3 前端

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。

### 3.4 无前端快速验证

```powershell
python scripts/demo_flow.py --image samples/real/01.jpg --text "七天美白，医美级效果"
```

---

## 四、目录结构

```
.
├── README.md                 # 本文件
├── .env.example              # 环境变量模板（复制为 .env，勿提交）
├── docs/
│   ├── 01-赛题分析与总体方案.md  # 赛题拆解、创新点、演示剧本
│   ├── 02-技术架构.md           # 架构、数据契约、算法细节
│   ├── 03-Git协作规范.md        # 分支策略、提交规范、冲突处理
│   └── 04-赛程计划与任务看板.md  # 四周计划、分工、提交清单
├── backend/                  # FastAPI 服务
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # 服务入口与路由
│       ├── schemas.py        # 数据契约（前后端唯一真相源）
│       ├── detection/        # 图像取证 + 文案检测
│       └── agent/            # RiskAgent 决策层
├── frontend/                 # React + Vite 演示界面
├── samples/                  # 测试样本（真/假/灰三类）
└── scripts/
    └── demo_flow.py          # 端到端演示脚本
```

---

## 五、团队协作

**新人上车三步**：

```powershell
git clone <仓库地址>
cd git-demo
git checkout develop
```

然后读 [`docs/03-Git协作规范.md`](docs/03-Git协作规范.md) —— 分支策略、提交规范、文件所有权都在里面。

**重要约定**：
- `main` 稳定可演示，`develop` 集成分支，每人 `feature/模块名`
- 绝不提交 API Key（`.env` 已被忽略）
- 改 `backend/app/schemas.py` 必须在群里先说

---

## 六、开发顺序（板块攻略）

| 板块 | 内容 | 状态 |
| --- | --- | --- |
| 1 | 仓库骨架 + 方案文档 | ✅ |
| 2 | 图像取证 + 文案检测模块 | ⬜ |
| 3 | Agent 决策层 | ⬜ |
| 4 | 前端演示界面 | ⬜ |
| 5 | 样本集 + 端到端跑通 | ⬜ |
| 6 | 路演 PPT + 提交 | ⬜ |
