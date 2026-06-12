"""
Pha 2b: nạp điểm path của CognTKE (precompute) và fuse vào điểm LogCL.
An toàn: gamma init 0 + key thiếu -> path=0  => không bao giờ tụt dưới LogCL.
"""
import pickle
import numpy as np
import torch


class PathFuser:
    def __init__(self, pkl_path, num_entity, tl_train, tl_valid, device):
        with open(pkl_path, "rb") as f:
            d = pickle.load(f)
        self.scores = d["scores"]              # {(s, r, t_global): (idx np.int32, val np.float16)}
        self.num_entity = num_entity
        self.tl_train = tl_train
        self.tl_valid = tl_valid
        self.device = device

    def global_t(self, time_idx, split):
        if split == "train":
            return int(time_idx)
        if split == "valid":
            return self.tl_train + int(time_idx)
        return self.tl_train + self.tl_valid + int(time_idx)   # test

    @torch.no_grad()
    def dense(self, triples, time_idx, split):
        """triples [B,3] (s,r,o) -> path 分数 [B,num_entity]，行内标准化。"""
        gt = self.global_t(time_idx, split)
        B = triples.shape[0]
        out = torch.zeros(B, self.num_entity, device=self.device)
        s = triples[:, 0].tolist(); r = triples[:, 1].tolist()
        rows, cols, vals = [], [], []
        for b in range(B):
            rec = self.scores.get((s[b], r[b], gt))
            if rec is None:
                continue
            idx, val = rec
            rows.append(np.full(len(idx), b, dtype=np.int64))
            cols.append(idx.astype(np.int64))
            vals.append(val.astype(np.float32))
        if rows:
            rb = torch.as_tensor(np.concatenate(rows), device=self.device)
            cb = torch.as_tensor(np.concatenate(cols), device=self.device)
            vb = torch.as_tensor(np.concatenate(vals), device=self.device)
            out[rb, cb] = vb
        mask = (out.abs().sum(1, keepdim=True) > 0)
        mu = out.mean(1, keepdim=True); sd = out.std(1, keepdim=True) + 1e-6
        return torch.where(mask, (out - mu) / sd, torch.zeros_like(out))
