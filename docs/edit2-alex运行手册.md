# edit2 样本在 alex 上的运行手册

目标：用 FLUX.1-Fill-dev 与 SDXL-inpainting 生成约 130 个局部篡改样本（每个样本含 splice、control_splice、full、mask）。
**每一步都先经用户批准再执行；命令只在对应位置（本机 / 登录节点 / 提交 sbatch）逐条粘贴，不要把多条混着粘。**

## 约定值（均为实际值）
- 工作目录：`/anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/drag/edit2`（下称 `$WS`，子目录 `env/ weights/ inputs/ code/ out/ logs/`）
- conda：`/anvme/workspace/b240dd18-dataset/conda/etc/profile.d/conda.sh`（S0 会核对此文件是否存在）
- 任务名：冒烟 `15-g1`，全量 `15-g2`（序号 `15-` 待用户对照团队表格确认；不含方向/模型/数据集名）
- sbatch：partition `a100`，`--gres=gpu:1`，`--cpus-per-task=8`，**不加 `--mem`**（按用户在 alex 上的经验），日志在 `$WS/logs/`
- 登录节点只做：下载、pip、mkdir、`--dry-run`（不加载模型）。**加载模型和冒烟、全量一律 sbatch。**

## 步骤总览
| 步骤 | 位置 | 内容 | 会写入 / 占用 |
| --- | --- | --- | --- |
| S0 | 登录节点（只读） | 查配额、核对 conda 路径 | 无 |
| S1 | 本机 | 打包 26 张原图和代码，上传到 HF 私有 dataset | HF 上约 5MB |
| S2 | 登录节点 | 建目录和 env、装依赖 | `$WS/env` 约 6–8GB |
| S3 | 登录节点 | HF 登录、下载权重和 inputs | `$WS/weights` 约 40GB |
| S4 | 登录节点 + sbatch | dry-run，提交冒烟 `15-g1` | 约 30 分钟 GPU |
| S5 | sbatch | 全量 `15-g2`（可断点续跑） | 约 1–1.5 小时 GPU |
| S6 | 登录节点 + 本机 | 打包回传、本机下载、报告 | 约 0.6–0.8GB |

## S0 只读检查（登录节点）
```bash
df -h /anvme/workspace/b240dd18-data_store | tail -1
du -sh /anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/drag/weights
du -sh /home/hpc/b240dd/b240dd18
ls /anvme/workspace/b240dd18-dataset/conda/etc/profile.d/conda.sh
ls /anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/drag
```
贴回：五条输出。通过标准：`$WS` 所在盘剩余空间大于 60GB；conda.sh 存在；`edit/drag/` 下没有 `edit2`（它是 `drag` 下的独立子目录，与 `env/ code/ scripts/ weights/` 并列，不会改动它们）。

## S1 本机打包并上传（Windows PowerShell，在仓库根目录）
前提：`pip install huggingface_hub`，并已在本机执行 `huggingface-cli login`（token 只在你的终端输入）。
```powershell
python scripts/hf_edit2_transfer.py pack
python scripts/hf_edit2_transfer.py up
```
预期输出：`已组装 ...：26 张原图，26 行 jsonl，code/ 下 3 个文件`，然后 `已上传到私有 dataset：<你的HF用户名>/edit2-tamper-eval`。
贴回：两行输出。

## S2 建环境（登录节点，联网）
依次粘贴，一条一回车：
```bash
export WS=/anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/drag/edit2
mkdir -p $WS/weights $WS/inputs $WS/code $WS/out $WS/logs
source /anvme/workspace/b240dd18-dataset/conda/etc/profile.d/conda.sh
conda create -p $WS/env python=3.10 -y
conda activate $WS/env
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu121
pip install diffusers==0.32.2 transformers==4.46.3 accelerate==1.1.1 huggingface_hub==0.26.2 sentencepiece protobuf safetensors numpy pillow
```
贴回：最后两条的结尾输出（`Successfully installed ...`）。版本组合未实测，冒烟阶段会暴露不兼容。

## S3 下载权重和 inputs（登录节点，联网；下载不属于加载模型）
前提：已在 `https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev` 同意协议。
```bash
export HF_HOME=$WS/weights TORCH_HOME=$WS/weights/torch XDG_CACHE_HOME=$WS/weights/xdg HUGGINGFACE_HUB_CACHE=$WS/weights/hub
huggingface-cli login
export HFU=$(huggingface-cli whoami | head -n 1)
echo $HFU
huggingface-cli download black-forest-labs/FLUX.1-Fill-dev --local-dir $WS/weights/flux_fill --exclude "flux1-fill-dev.safetensors" "ae.safetensors"
huggingface-cli download diffusers/stable-diffusion-xl-1.0-inpainting-0.1 --local-dir $WS/weights/sdxl_inpaint --include "*.json" "*.txt" "*.fp16.safetensors"
python -c "import os; from huggingface_hub import snapshot_download as s; s(os.environ['HFU']+'/edit2-tamper-eval', repo_type='dataset', local_dir='$WS', allow_patterns=['inputs/*'])"
mkdir -p $WS/code && cp $WS/inputs/code/* $WS/code/ && sed -i 's/\r$//' $WS/code/*
du -sh $WS/weights/flux_fill $WS/weights/sdxl_inpaint
ls $WS/code && find $WS/inputs/images -name "*.jpg" | wc -l
```
预期：`echo $HFU` 打印你的用户名；`ls $WS/code` 有 `full.sbatch gen_edits_local.py smoke.sbatch`；原图数量 26。
贴回：`echo $HFU`、`du` 两行、最后两条输出。

## S4 dry-run 和冒烟
登录节点 dry-run（不加载模型，只用 numpy）：
```bash
cd $WS/code
python gen_edits_local.py --dry-run --images-dir $WS/inputs/images --screened $WS/inputs/real_screened_edit2.jsonl --manifest $WS/out/smoke_manifest.jsonl
```
预期：`计划 130 个样本 ... {'flux': 65, 'sdxl': 65}`，掩码面积 min=0.061 max=0.229（本机已实测相同）。

提交冒烟（FLUX 和 SDXL 各 1 张，离线，30 分钟时限）：
```bash
cd $WS/code
sbatch smoke.sbatch
```
监控（日志文件要等任务进入 R 状态后才会出现）：
```bash
squeue -u b240dd18
tail -n 30 $WS/logs/15-g1-*.out
```
验收：日志出现 `verify: 4 行, 失败 0` 和 `EDIT2_DONE`。含义：2 个样本 × 2 行；掩码面积 5%–25%、掩码外与底图逐像素一致、splice 差异大于 0.5%、full 图存在。
失败时：
```bash
grep -nE "Traceback|Error|error" $WS/logs/15-g1-*.err | head
```
把输出贴回，不要自行改库版本。

## S5 全量
```bash
cd $WS/code
sbatch full.sbatch
```
断点续跑：作业被杀或超时后，再次 `sbatch full.sbatch` 即可，已完成样本会跳过。
验收：日志末尾有 `verify: 260 行, 失败 0`（若有丢弃则行数更少）、`--report` 汇总和 `EDIT2_DONE`。

## S6 回传
登录节点：
```bash
export WS=/anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/drag/edit2
tar -cf $WS/out/edit2_outputs.tar -C $WS/inputs/images edit2 -C $WS/out edit2_manifest.jsonl
python -c "import os; from huggingface_hub import HfApi; HfApi().upload_file(path_or_fileobj='$WS/out/edit2_outputs.tar', path_in_repo='outputs/edit2_outputs.tar', repo_id=os.environ['HFU']+'/edit2-tamper-eval', repo_type='dataset')"
```
（若换了新终端，需先 `source` conda、`conda activate $WS/env`，并重新 `export HFU=$(huggingface-cli whoami | head -n 1)`。）

本机：
```powershell
python scripts/hf_edit2_transfer.py down
python scripts/gen_edits_local.py --verify
python scripts/gen_edits_local.py --report
```
`data/images/edit2/` 与 `data/seed/edit2_manifest.jsonl` 就位后，评测接入由本仓库侧完成。

## 报告模板（15 行以内，交付给我）
```
1. 计划 / 完成 / 丢弃：  /  /
2. 按生成器：flux=  sdxl=
3. 按破损类型：crack= leak= pump= box= tube= label=
4. 对照 diff_frac 均值 vs splice diff_frac 均值：  vs
5. 掩码面积范围：
6. 模型与许可：FLUX.1-Fill-dev（非商业许可）、SDXL-inpainting-0.1（OpenRAIL++）
7. 单张平均耗时 / 总耗时：  /
8. 肉眼检查（抽 20 张）：哪类破损效果差、哪种掩码有接缝：
9. 冒烟 / 全量的作业号与退出状态：
```
