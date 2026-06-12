"""
Pha 2a: precompute CognTKE 的 path 分数(稀疏, in-graph)给所有 (s, r, t) 查询
(正向 + 反向)，存成字典供 LogCL 融合时按 key 查表。不需要 dgl。

key = (s, r, t_global)  ->  (entity_idx[np.int32], score[np.float16])
t_global = CognTKE data_splited 的全局快照下标 (train+valid+test 连续)。
反向查询用 r + num_relation (CognTKE 自带反向关系)。
"""
import numpy as np
import torch
import pickle
from utils import gpu_setting

CKPT = "results/TRED_GNN/L3/ICEWS14s/2026-06-02-21-19/best_weight.pt"
OUT = "cogntke_path_scores.pkl"
BS = 48


def patch(m):
    for a, v in [("use_query_gate", False), ("use_entity_embed", False),
                 ("use_route_gate", False), ("use_reranker", False),
                 ("use_fusion", False), ("use_contrastive", False), ("use_logcl", False),
                 ("use_global_scorer", getattr(m, "use_global_scorer", False))]:
        if not hasattr(m, a):
            setattr(m, a, v)
    return m


if __name__ == "__main__":
    gpu_setting(-1)
    model = patch(torch.load(CKPT, weights_only=False).cuda().eval())
    data = model.data
    nrel = data.num_relation
    import os
    out = {}
    done_t = set()
    if os.path.exists(OUT):           # resume nếu đã có file dở
        with open(OUT, "rb") as f:
            out = pickle.load(f)["scores"]
        done_t = {k[2] for k in out}
        print(f"resume: đã có {len(out)} keys, {len(done_t)} timestamp")
    # 对每个全局时间片，收集该片所有事实的正/反向查询 (s', r')，批量算 path 分数
    for t in range(data.time_length):
        if t in done_t:
            continue
        facts = data.data_splited[t]            # [N,3] = s,r,o (已含反向关系 fact)
        if len(facts) == 0:
            continue
        # data_splited 已包含正反两个方向(反向以 rel+num_relation 存在)，直接取 (s,r) 去重
        q = np.unique(facts[:, [0, 1]], axis=0)
        for i in range(0, len(q), BS):
            chunk = q[i:i + BS]
            s = torch.tensor(chunk[:, 0]).cuda()
            r = torch.tensor(chunk[:, 1]).cuda()
            with torch.no_grad():
                scores_all, nodes, _, _ = model.forward_with_evidence(t, s, r)
            nodes = nodes.cpu().numpy()
            scores_all = scores_all.cpu()
            for b in range(len(chunk)):
                ents = nodes[nodes[:, 0] == b, 1]
                if len(ents) == 0:
                    continue
                vals = scores_all[b, ents].numpy().astype(np.float16)
                out[(int(chunk[b, 0]), int(chunk[b, 1]), int(t))] = (
                    ents.astype(np.int32), vals)
        torch.cuda.empty_cache()
        if t % 20 == 0:
            print(f"t={t}/{data.time_length}  keys={len(out)}", flush=True)
            with open(OUT, "wb") as f:        # lưu định kỳ (checkpoint)
                pickle.dump({"num_entity": data.num_entity, "scores": out}, f)
    with open(OUT, "wb") as f:
        pickle.dump({"num_entity": data.num_entity, "scores": out}, f)
    print("saved", OUT, "total keys", len(out))
