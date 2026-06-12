"""
跨家族加权集成：4 个 CognTKE checkpoint + 1 个 CYGNET(不同家族)。
- 加权 RRF：fused = sum_m w_m / (k + rank_m)
- 在 valid 上用坐标上升搜索权重(降低弱成员权重，保留互补性)
- 报告 test MRR。不重新训练。
"""
import sys, glob, os
import numpy as np
import torch
from scipy.stats import rankdata
import utils
from utils import gpu_setting

# 4 个 CognTKE (同家族) + CYGNET (异家族, 自动取最新)
CKPTS = {
    "gscorer": "results/TRED_GNN/L3/ICEWS14s/2026-06-02-21-19/best_weight.pt",
    "route":   "results/TRED_GNN/L3/ICEWS14s/2026-06-05-23-26/best_weight.pt",
    "decay":   "results/TRED_GNN/L3/ICEWS14s/2026-06-03-07-47/best_weight.pt",
    "qgate":   "results/TRED_GNN/L3/ICEWS14s/2026-06-03-23-55/best_weight.pt",
}
cyg = sorted(glob.glob("results/CYGNET/*/ICEWS14s/*/best_weight.pt"), key=os.path.getmtime)
if cyg:
    CKPTS["cygnet"] = cyg[-1]


def patch(m):
    for a, v in [("use_query_gate", False), ("use_entity_embed", False),
                 ("use_route_gate", False), ("use_reranker", False),
                 ("use_global_scorer", getattr(m, "use_global_scorer", False))]:
        if not hasattr(m, a):
            setattr(m, a, v)
    return m


def collect(models, data, split):
    if split == "valid":
        start, end = data.time_length_train, data.time_length_train + data.time_length_valid
    else:
        start = data.time_length_train + data.time_length_valid
        end = data.time_length
    batches = []
    bs = 128
    for ts in range(start, end):
        q = data.data_splited[ts]
        nb = q.shape[0] // bs + (q.shape[0] % bs > 0)
        for b in range(nb):
            idx = list(range(b * bs, min((b + 1) * bs, q.shape[0])))
            batch = torch.tensor(data.get_batch(ts, idx)).cuda()
            labels = batch[:, 2].cpu().numpy()
            fi = [(i, o) for i, t in enumerate(batch.tolist())
                  for o in data.time_filter[ts][(t[0], t[1])]]
            fi = np.array(fi).T
            filt = np.zeros((batch.shape[0], data.num_entity), dtype=np.float32)
            filt[fi[0], fi[1]] = 1
            ranks_per_model = []
            for m in models:
                with torch.no_grad():
                    s = m(ts, batch[:, 0], batch[:, 1]).cpu().numpy().astype(np.float32)
                ranks_per_model.append(rankdata(-s, method="average", axis=1))  # 1=best
            batches.append((np.stack(ranks_per_model), labels, filt))  # [M,B,E]
    return batches


def eval_w(batches, w, k=60):
    ranks = []
    for rk, labels, filt in batches:
        fused = np.tensordot(w, 1.0 / (k + rk), axes=([0], [0]))  # [B,E]
        ranks += utils.cal_ranks(fused, labels, filt)
    return utils.cal_performance(np.array(ranks))[0]


if __name__ == "__main__":
    gpu_setting(-1)
    names = list(CKPTS)
    print("members:", names)
    models, data = [], None
    for n in names:
        m = patch(torch.load(CKPTS[n], weights_only=False).cuda().eval())
        models.append(m); data = m.data
    print("collecting valid/test ...")
    vb = collect(models, data, "valid")
    tb = collect(models, data, "test")

    M = len(names)
    print("\nindividual test MRR:")
    for i, n in enumerate(names):
        w = np.zeros(M); w[i] = 1
        print(f"  {n:8s} {eval_w(tb, w):.4f}")

    # 等权基线
    w = np.ones(M)
    print(f"\nequal-weight RRF  valid {eval_w(vb,w):.4f}  test {eval_w(tb,w):.4f}")

    # 坐标上升搜索权重(on valid)
    grid = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
    w = np.ones(M)
    best_v = eval_w(vb, w)
    for _ in range(4):
        for i in range(M):
            bw, bv = w[i], best_v
            for g in grid:
                w[i] = g
                v = eval_w(vb, w)
                if v > bv:
                    bv, bw = v, g
            w[i] = bw; best_v = bv
    tv = eval_w(tb, w)
    print(f"\ntuned weights {dict(zip(names, np.round(w,2)))}")
    print(f"  valid MRR {best_v:.4f}  test MRR {tv:.4f}")
    print(f"  baseline single best 0.4624 | same-family ensemble 0.4679")
