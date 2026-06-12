"""
Oracle 诊断：在已训练 baseline 上，统计真答案的过滤排名分布，
回答“做 top-k 重排最多能把 MRR 提到多少”。不训练。

对每个查询得到过滤排名 r：
- recall@k = P(r <= k)：答案落在 top-k 的比例（reranker 的可作用范围）
- oracle_mrr@k = mean( 1.0 if r<=k else 1/r )：完美重排 top-k 后的 MRR 上界
基线 MRR = mean(1/r)。
"""
import numpy as np
import torch
import utils
from utils import gpu_setting

CKPT = "results/TRED_GNN/L3/ICEWS14s/2026-06-02-21-19/best_weight.pt"


def patch(m):
    for a, v in [("use_query_gate", False), ("use_entity_embed", False),
                 ("use_route_gate", False), ("use_global_scorer",
                  getattr(m, "use_global_scorer", False))]:
        if not hasattr(m, a):
            setattr(m, a, v)
    return m


def collect_ranks(model, data, split):
    if split == "valid":
        start, end = data.time_length_train, data.time_length_train + data.time_length_valid
    else:
        start = data.time_length_train + data.time_length_valid
        end = data.time_length
    all_ranks = []
    bs = 128
    for ts in range(start, end):
        q = data.data_splited[ts]
        nb = q.shape[0] // bs + (q.shape[0] % bs > 0)
        for b in range(nb):
            idx = list(range(b * bs, min((b + 1) * bs, q.shape[0])))
            batch = torch.tensor(data.get_batch(ts, idx)).cuda()
            with torch.no_grad():
                sc = model(ts, batch[:, 0], batch[:, 1]).cpu().numpy()
            labels = batch[:, 2].cpu().numpy()
            fi = [(i, o) for i, t in enumerate(batch.tolist())
                  for o in data.time_filter[ts][(t[0], t[1])]]
            fi = np.array(fi).T
            filt = np.zeros_like(sc)
            filt[fi[0], fi[1]] = 1
            all_ranks += utils.cal_ranks(sc, labels, filt)
    return np.array(all_ranks, dtype=np.float64)


if __name__ == "__main__":
    gpu_setting(-1)
    model = patch(torch.load(CKPT, weights_only=False).cuda().eval())
    data = model.data
    print("collecting test ranks ...")
    r = collect_ranks(model, data, "test")
    n = len(r)
    base_mrr = (1.0 / r).mean()
    print(f"\nN={n}  baseline test MRR={base_mrr:.4f}  Hits@1={np.mean(r<=1):.4f}")
    print(f"\n{'k':>4} {'recall@k':>9} {'oracle_MRR@k':>13} {'gain vs base':>13}")
    for k in [1, 3, 5, 10, 20, 30, 50, 100]:
        recall = np.mean(r <= k)
        oracle = np.where(r <= k, 1.0, 1.0 / r).mean()
        print(f"{k:>4} {recall:>9.4f} {oracle:>13.4f} {oracle-base_mrr:>+13.4f}")
    # how much of the miss is "in top-k but not #1" (rerankable) vs "outside top-k"
    print("\n排名分布:")
    for lo, hi in [(1,1),(2,3),(4,5),(6,10),(11,20),(21,50),(51,100),(101,10**9)]:
        frac = np.mean((r>=lo)&(r<=hi))
        print(f"  rank {lo:>3}-{hi if hi<10**9 else 'inf':<4}: {frac:.4f}")
