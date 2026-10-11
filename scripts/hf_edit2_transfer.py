"""本机侧的 edit2 数据传输（经 HF 私有 dataset repo）。需先 pip install huggingface_hub 并 huggingface-cli login。

  python scripts/hf_edit2_transfer.py pack   # 组装待上传目录 data/images/_edit2_inputs/
  python scripts/hf_edit2_transfer.py up     # 创建私有 repo 并上传 inputs/
  python scripts/hf_edit2_transfer.py down   # 下载 outputs/ 并解到 data/images/edit2、data/seed/edit2_manifest.jsonl
"""
import json
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "data" / "images"
STAGE = IMG / "_edit2_inputs"
REPO = "edit2-tamper-eval"


def pack() -> None:
    rows = [json.loads(l) for l in (ROOT / "data" / "seed" / "real_screened.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    keep = [r for r in rows if r.get("keep") and r["truth"] == "real_intact"]
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "code").mkdir(parents=True)
    for r in keep:
        dst = STAGE / "images" / r["file"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(IMG / r["file"], dst)
    slim = [{k: r[k] for k in ("file", "truth", "keep", "container", "is_package")} for r in keep]
    (STAGE / "real_screened_edit2.jsonl").write_text("\n".join(json.dumps(r) for r in slim) + "\n", encoding="utf-8", newline="\n")
    for p in [ROOT / "scripts" / "gen_edits_local.py", *(ROOT / "scripts" / "alex").glob("*.sbatch")]:
        text = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        (STAGE / "code" / p.name).write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for f in (STAGE / "images").rglob("*") if f.is_file())
    print(f"已组装 {STAGE}：{n} 张原图，{len(slim)} 行 jsonl，code/ 下 {len(list((STAGE / 'code').iterdir()))} 个文件")


def up() -> None:
    from huggingface_hub import HfApi
    api = HfApi()
    user = api.whoami()["name"]
    api.create_repo(REPO, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(folder_path=str(STAGE), repo_id=f"{user}/{REPO}", repo_type="dataset", path_in_repo="inputs")
    print(f"已上传到私有 dataset：{user}/{REPO}（inputs/）")


def down() -> None:
    from huggingface_hub import HfApi, hf_hub_download
    user = HfApi().whoami()["name"]
    p = hf_hub_download(f"{user}/{REPO}", "outputs/edit2_outputs.tar", repo_type="dataset")
    with tarfile.open(p) as t:
        t.extractall(IMG)
    shutil.move(str(IMG / "edit2_manifest.jsonl"), str(ROOT / "data" / "seed" / "edit2_manifest.jsonl"))
    print("已解压到 data/images/edit2/，manifest 在 data/seed/edit2_manifest.jsonl")


if __name__ == "__main__":
    cmds = {"pack": pack, "up": up, "down": down}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]]()
