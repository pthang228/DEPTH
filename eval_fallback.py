"""
对比图外(out-graph)实体的两种兜底打分(in-graph 完全保留 CognTKE):
  A) freq-prior 兜底  (= 现有 global-scorer, baseline 0.4624)
  B) 学习模型(CYGNET)兜底
不训练，直接在 test 上评测。
"""
import numpy as np
import torch
import utils
from utils import gpu_setting

COG = "results/TRED_GNN/L3/ICEWS14s/2026-06-02-21-19/best_weight.pt"   # 含 freq_prior
import glob, os
CYG = sorted(glob.glob("results/CYGNET/*/ICEWS14s/*/best_weight.pt"), key=os.path.getmtime)[-1]


def patch(m):
    for a, v in [("use_query_gate", False), ("use_entity_embed", False), ("use_route_gate", False),
                 ("use_reranker", False), ("use_fusion", False), ("use_contrastive", False),
                 ("use_global_scorer", getattr(m, "use_global_scorer", False))]:
        if not hasattr(m, a):
            setattr(m, a, v)
    return m


def fallback_combine(scores_path, in_graph, g):
    row_min = scores_path.masked_fill(~in_graph, float("inf")).min(1, keepdim=True).values
    row_min = torch.where(torch.isinf(row_min), torch.zeros_like(row_min), row_min)
    g_norm = (g - g.max(1, keepdim=True).values) * 0.01
    out_scores = row_min - 1.0 + g_norm
    return torch.where(in_graph, scores_path, out_scores)


if __name__ == "__main__":
    gpu_setting(-1)
    cog = patch(torch.load(COG, weights_only=False).cuda().eval())
    cyg = patch(torch.load(CYG, weights_only=False).cuda().eval())
    data = cog.data
    start = data.time_length_train + data.time_length_valid
    end = data.time_length
    ranks = {"freq": [], "learned": []}
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
            with torch.no_grad():
                # 原始 in-graph 分数 + mask（用 forward_with_evidence 拿未加兜底的分）
                sp, nodes, _, _ = cog.forward_with_evidence(ts, batch[:, 0], batch[:, 1])
                in_graph = torch.zeros_like(sp, dtype=torch.bool)
                in_graph[[nodes[:, 0], nodes[:, 1]]] = True
                # A) freq 兜底
                g_freq = cog.freq_prior[batch[:, 1]]
                sa = fallback_combine(sp, in_graph, g_freq)
                # B) 学习(CYGNET)兜底
                g_learn = cyg(ts, batch[:, 0], batch[:, 1])
                sb = fallback_combine(sp, in_graph, g_learn)
            ranks["freq"] += utils.cal_ranks(sa.cpu().numpy(), labels, filt)
            ranks["learned"] += utils.cal_ranks(sb.cpu().numpy(), labels, filt)
    for k in ranks:
        mrr, h1, h3, h10, h100 = utils.cal_performance(np.array(ranks[k]))
        print(f"{k:8s}  MRR {mrr:.4f}  H1 {h1:.4f}  H3 {h3:.4f}  H10 {h10:.4f}")
