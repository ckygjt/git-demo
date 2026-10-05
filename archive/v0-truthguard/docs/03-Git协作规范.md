# 03 · Git 协作规范

> 目标：让 5 个人同时改同一个仓库不打架、不丢代码、不泄露密钥。

---

## 一、分支策略

```
main        ← 稳定可演示版本，任何时刻都能跑通（仅队长可合并）
 └── develop ← 集成分支，各功能完成后合并到这里
      ├── feature/image-forensics   图像取证模块
      ├── feature/text-detector     文案检测模块
      ├── feature/risk-agent        Agent 决策层
      ├── feature/frontend          前端演示界面
      ├── feature/samples           测试样本与演示脚本
      └── docs/xxx                  文档更新
```

**规则**
1. `main` 受保护，不直接 push；只能通过 develop 合并
2. 每人一个 feature 分支，命名 `feature/模块名` 或 `docs/内容`
3. 分支存活不超过 3 天，做完立刻合并，避免长期分叉
4. 每周日晚上由队长把 develop 合并进 main 打一次"周版本"

---

## 二、标准工作流（每人每天必做）

```powershell
# 1. 开工前：拉取最新代码（防止基于旧代码开发）
git checkout develop
git pull origin develop

# 2. 开自己的分支
git checkout -b feature/image-forensics

# 3. 写代码，小步提交（不要攒一天）
git add backend/app/detection/image_forensics.py
git commit -m "feat(detection): 实现 ELA 误差分析并输出热力图"

# 4. 每天下班前推一次（即使没做完，也保底云端有一份）
git push -u origin feature/image-forensics

# 5. 模块完成 → 在 Gitee/GitHub 发起 PR 到 develop，@ 队长评审
```

---

## 三、提交信息规范

格式：`<类型>(<范围>): <简述>`

| 类型 | 用于 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修 bug |
| `docs` | 文档 |
| `refactor` | 重构（不改行为） |
| `style` | 格式/样式 |
| `perf` | 性能优化 |
| `test` | 测试 |
| `chore` | 构建/依赖/杂项 |

示例：
```
feat(agent): 实现风险分级与处置动作映射
fix(frontend): 修复热力图与原图尺寸不对齐
docs(plan): 补充决赛答辩剧本
```

---

## 四、文件所有权（避免冲突的核心手段）

| 目录 | 负责人 | 其他人 |
| --- | --- | --- |
| `backend/app/detection/image_forensics.py` | 队员A | 只读，改动需提 issue |
| `backend/app/detection/text_detector.py` | 队员B | 只读 |
| `backend/app/agent/` | 队员C | 只读 |
| `frontend/src/` | 队员D | 只读 |
| `docs/` `samples/` | 队长 | 可提议 |
| `backend/app/schemas.py` | **队长**（数据契约） | 需改请提 PR 说明 |

**黄金法则**：`schemas.py` 是前后端共同契约，任何人修改必须先在群里说一声。

---

## 五、冲突处理

1. **先 pull 再 push**，这是 90% 冲突的解药
2. 真冲突时：**不要盲选"我的版本"**，打开冲突文件看 `<<<<<<<` 标记，和相关同学口头确认
3. 二进制文件（图片、模型、PPT）无法自动合并 → 先沟通再覆盖
4. 不确定就 `git stash` 保存现场，找队长

---

## 六、安全与红线

- **绝不提交** `.env`、API Key、令牌。`.gitignore` 已排除，提交前用 `git status` 自查
- 若误提交密钥：`git reset` 撤销 + 立刻去平台**吊销该 Key**，别只删文件
- 大文件（>10MB 图片/模型/数据集）不进仓库，放网盘并在 `docs/` 记录链接

---

## 七、演示安全网（重要）

比赛演示前一天：
```powershell
git tag v1.0-demo
git push origin v1.0-demo
```
之后所有改动都在新分支上做。**万一改崩了，一条命令回到能演示的版本**：
```powershell
git checkout v1.0-demo
```

---

## 八、常用命令速查

| 场景 | 命令 |
| --- | --- |
| 看当前状态 | `git status` |
| 看改动内容 | `git diff` |
| 撤销未提交改动 | `git checkout -- <文件>` |
| 撤销已 add | `git restore --staged <文件>` |
| 回退上一次提交（保留改动） | `git reset --soft HEAD~1` |
| 临时保存现场 | `git stash` / `git stash pop` |
| 看提交图 | `git log --oneline --graph --all` |
| 同步远程 | `git fetch --all --prune` |

---

## 九、每日同步节奏（建议）

- **早 10 分钟**：群里发"今天我要做 X，会改 Y 文件"
- **晚 5 分钟**：push + 群里发"已完成 X，遇到 Z 问题"
- **周日 30 分钟**：周会，develop → main，更新 `docs/04` 看板
