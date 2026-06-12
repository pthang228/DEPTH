"""
后验集成实验：把多个已训练 checkpoint 的预测融合，不重新训练。
- RRF (Reciprocal Rank Fusion)：无参数、抗尺度差异，对不同结构模型最稳。
- 归一化加权平均：每行 min-max 到 [0,1] 再平均。
在 valid 上选最优组合/方法，报告 test MRR。
"""
import sys
import numpy as np
import torch
from scipy.stats import rankdata
import utils
from utils import gpu_setting

CKPTS = {
    "gscorer": "results/TRED_GNN/L3/ICEWS14s/2026-06-02-21-19/best_weight.pt",  # 0.4624
    "route":   "results/TRED_GNN/L3/ICEWS14s/2026-06-05-23-26/best_weight.pt",  # 0.4612
    "decay":   "results/TRED_GNN/L3/ICEWS14s/2026-06-03-07-47/best_weight.pt",  # 0.4596
    "qgate":   "results/TRED_GNN/L3/ICEWS14s/2026-06-03-23-55/best_weight.pt",  # 0.4587
}


def patch(m):
    for a, v in [("use_query_gate", False), ("use_entity_embed", False),
                 ("use_route_gate", False), ("use_global_scorer", False)]:
        if not hasattr(m, a):
            setattr(m, a, v)
    return m


def collect(models, data, split):
    if split == "valid":
        start, end = data.time_length_train, data.time_length_train + data.time_length_valid
    else:
        start = data.time_length_train + data.time_length_valid
        end = data.time_length
    # per batch: list of (scores_per_model[M][B,E], labels, filt)
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
            scs = []
            for m in models:
                with torch.no_grad():
                    s = m(ts, batch[:, 0], batch[:, 1]).cpu().numpy().astype(np.float32)
                scs.append(s)
            batches.append((scs, labels, filt))
    return batches


def eval_combo(batches, model_idx, method, k=60):
    ranks = []
    for scs, labels, filt in batches:
        sel = [scs[i] for i in model_idx]
        if len(sel) == 1:
            fused = sel[0]
        elif method == "rrf":
            fused = np.zeros_like(sel[0])
            for s in sel:
                r = rankdata(-s, method="average", axis=1)  # 1=best
                fused += 1.0 / (k + r)
        else:  # normalized average
            fused = np.zeros_like(sel[0])
            for s in sel:
                lo = s.min(1, keepdims=True); hi = s.max(1, keepdims=True)
                fused += (s - lo) / (hi - lo + 1e-9)
        ranks += utils.cal_ranks(fused, labels, filt)
    return utils.cal_performance(np.array(ranks))


if __name__ == "__main__":
    gpu_setting(-1)
    names = list(CKPTS)
    models = []
    data = None
    for n in names:
        m = patch(torch.load(CKPTS[n], weights_only=False).cuda().eval())
        models.append(m)
        data = m.data
    print("collecting valid ...")
    vb = collect(models, data, "valid")
    print("collecting test ...")
    tb = collect(models, data, "test")

    print("\n-- individual (test MRR) --")
    for i, n in enumerate(names):
        t = eval_combo(tb, [i], "rrf")
        print(f"  {n:8s} {t[0]:.4f}")

    # candidate combos
    import itertools
    combos = []
    for r in range(2, len(names) + 1):
        for c in itertools.combinations(range(len(names)), r):
            combos.append(list(c))

    print("\n-- ensembles (sorted by valid MRR) --")
    print(f"{'method':>5} {'models':<28} {'vMRR':>8} {'tMRR':>8} {'t_h1':>8} {'t_h3':>8}")
    results = []
    for method in ["rrf", "navg"]:
        for combo in combos:
            v = eval_combo(vb, combo, method)
            t = eval_combo(tb, combo, method)
            results.append((v[0], t, method, combo))
    results.sort(key=lambda x: -x[0])
    for v0, t, method, combo in results[:12]:
        tag = "+".join(names[i] for i in combo)
        print(f"{method:>5} {tag:<28} {v0:>8.4f} {t[0]:>8.4f} {t[1]:>8.4f} {t[2]:>8.4f}")
        sys.stdout.flush()

    best = results[0]
    print(f"\nBEST by valid: {best[2]} [{'+'.join(names[i] for i in best[3])}]")
    print(f"  test MRR {best[1][0]:.4f} h1 {best[1][1]:.4f} h3 {best[1][2]:.4f} h10 {best[1][3]:.4f}")
    print(f"  baseline single best (gscorer) test MRR 0.4624")
