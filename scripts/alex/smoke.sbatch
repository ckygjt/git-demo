#!/bin/bash
#SBATCH --job-name=15-g1
#SBATCH --partition=a100
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --time=00:30:00
#SBATCH --output=/anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/edit2/logs/%x-%j.out
#SBATCH --error=/anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/edit2/logs/%x-%j.err
set -e
WS=/anvme/workspace/b240dd18-data_store/runtime/spaces/a6eac70923360ffe/edit/edit2
source /anvme/workspace/b240dd18-dataset/conda/etc/profile.d/conda.sh
conda activate $WS/env
export HF_HOME=$WS/weights TORCH_HOME=$WS/weights/torch XDG_CACHE_HOME=$WS/weights/xdg
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
cd $WS/code
COMMON="--images-dir $WS/inputs/images --screened $WS/inputs/real_screened_edit2.jsonl --manifest $WS/out/smoke_manifest.jsonl --prefix smoke --flux-path $WS/weights/flux_fill --sdxl-path $WS/weights/sdxl_inpaint"
nvidia-smi --query-gpu=name,memory.total --format=csv
python gen_edits_local.py $COMMON --only flux --limit 1
python gen_edits_local.py $COMMON --only sdxl --limit 1
python gen_edits_local.py $COMMON --verify
echo EDIT2_DONE
