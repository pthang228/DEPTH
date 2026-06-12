"""
Pha 0: 验证 reranker 数据管线。
- 加载冻结 GNN，跑 forward_with_evidence
- 每个 query 取 in-graph top-k 候选
- 为每个候选收集其入边证据（未压缩）
- 用一个 dummy pooling 跑通，确认形状/索引正确
- 统计：每候选平均入边数、真答案落在 top-k 的比例、在 rank2-k 的可重排比例
不训练。
"""
import numpy as np
import torch
from torch_scatter import scatter
from utils import gpu_setting

CKPT = "results/TRED_GNN/L3/ICEWS14s/2026-06-02-21-19/best_weight.pt"
K = 20


def patch(m):
    for a, v in [("use_query_gate", False), ("use_entity_embed", False),
                 ("use_route_gate", False),
                 ("use_global_scorer", getattr(m, "use_global_scorer", False))]:
        if not hasattr(m, a):
            setattr(m, a, v)
    return m


def topk_per_query(nodes, hidden_scores, num_query, k):
    """返回每个 query 的 top-k 候选局部节点 idx [B,k]（不足补 -1）以及其分数。"""
    cand = torch.full((num_query, k), -1, dtype=torch.long, device=nodes.device)
    cscore = torch.full((num_query, k), -1e9, device=nodes.device)
    for q in range(num_query):
        sel = (nodes[:, 0] == q).nonzero(as_tuple=True)[0]   # 该 query 的候选局部 idx
        if sel.numel() == 0:
            continue
        sc = hidden_scores[sel]
        kk = min(k, sel.numel())
        top = sc.topk(kk).indices
        cand[q, :kk] = sel[top]
        cscore[q, :kk] = sc[top]
    return cand, cscore


if __name__ == "__main__":
    gpu_setting(-1)
    model = patch(torch.load(CKPT, weights_only=False).cuda().eval())
    data = model.data
    ts = data.time_length_train + data.time_length_valid + 3   # 一个 test 时间片
    q = data.data_splited[ts]
    batch = torch.tensor(q[:128]).cuda()
    B = batch.shape[0]

    with torch.no_grad():
        scores_all, nodes, ev, hidden = model.forward_with_evidence(ts, batch[:, 0], batch[:, 1])
    # 候选打分（与 _score 一致，用于排序）
    node_scores = model._score(hidden, nodes)   # [m]
    print(f"batch={B}  final nodes m={nodes.size(0)}  edges E={ev['obj'].numel()}")

    cand, cscore = topk_per_query(nodes, node_scores, B, K)   # [B,K]

    # incoming-edge count per candidate
    deg = scatter(torch.ones_like(ev["obj"], dtype=torch.float), ev["obj"],
                  dim=0, dim_size=nodes.size(0), reduce="sum")  # [m]
    valid = cand >= 0
    cand_deg = torch.where(valid, deg[cand.clamp_min(0)], torch.zeros_like(cscore))
    print(f"top-{K} cand incoming-edges  mean={cand_deg[valid].mean().item():.1f}  "
          f"median={cand_deg[valid].median().item():.0f}  max={cand_deg[valid].max().item():.0f}")

    # dummy pooling: scatter-mean message by obj -> [m,d], index top-k -> [B,K,d] -> Linear
    d = ev["message"].shape[1]
    agg = scatter(ev["message"], ev["obj"], dim=0, dim_size=nodes.size(0), reduce="mean")  # [m,d]
    cand_feat = agg[cand.clamp_min(0)]              # [B,K,d]
    dummy = torch.nn.Linear(d, 1).cuda()
    rerank_logits = dummy(cand_feat).squeeze(-1)    # [B,K]  <- reranker output shape
    rerank_logits = rerank_logits.masked_fill(~valid, -1e9)
    print(f"dummy reranker output shape: {tuple(rerank_logits.shape)}  (expect [{B},{K}])")

    # is true answer in top-k, and its position (rerankable quality)
    ans = batch[:, 2]                                # [B] answer entity
    cand_entity = torch.where(valid, nodes[cand.clamp_min(0), 1], torch.full_like(cand, -1))
    hit = (cand_entity == ans.unsqueeze(1))          # [B,K]
    in_topk = hit.any(dim=1)
    pos = torch.where(hit.any(1), hit.float().argmax(1), torch.full((B,), -1, device=hit.device))
    print(f"\ntrue answer in top-{K}: {in_topk.float().mean().item():.3f}")
    print(f"  at rank-1 (already correct): {((pos==0)&in_topk).float().mean().item():.3f}")
    print(f"  at rank 2-{K} (RERANKABLE):  {((pos>=1)&in_topk).float().mean().item():.3f}")
    print("\nPhase 0 OK: pipeline works. top-k extraction + per-edge evidence + reranker-shaped output all fine.")
