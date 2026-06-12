"""Tối giản shim 'dgl' chạy bằng torch_scatter — chỉ hỗ trợ các API LogCL dùng.
Cho phép LogCL chạy trên Windows/GPU không cần dgl-CUDA. KHÔNG sửa code LogCL."""
import torch
from torch_scatter import scatter

from . import function  # noqa


class _NodeView:
    def __init__(self, g, index):
        self.g = g
        self.index = index           # None = all nodes, else tensor of node ids
    def __getitem__(self, key):
        v = self.g.ndata[key]
        return v if self.index is None else v[self.index]


class _EdgeBatch:
    def __init__(self, g):
        self.g = g
        self.src = _NodeView(g, g._src)
        self.dst = _NodeView(g, g._dst)
        self.data = g.edata


class _NodeBatch:
    def __init__(self, g):
        self.data = g.ndata


class DGLGraph:
    def __init__(self, num_nodes=0):
        self._n = int(num_nodes)
        self._src = None
        self._dst = None
        self.ndata = {}
        self.edata = {}

    # ---- construction ----
    def add_nodes(self, n):
        self._n = int(n)

    def add_edges(self, src, dst):
        src = torch.as_tensor(src).long()
        dst = torch.as_tensor(dst).long()
        if self._src is None:
            self._src, self._dst = src, dst
        else:
            self._src = torch.cat([self._src, src])
            self._dst = torch.cat([self._dst, dst])
        if self._n == 0:
            self._n = int(max(self._src.max(), self._dst.max()).item()) + 1

    # ---- info ----
    def number_of_nodes(self):
        return self._n

    def num_nodes(self):
        return self._n

    def in_degrees(self, *args, **kwargs):
        deg = torch.zeros(self._n, device=self._dst.device)
        deg.scatter_add_(0, self._dst, torch.ones_like(self._dst, dtype=torch.float))
        return deg.long()

    # ---- message passing ----
    def apply_edges(self, func):
        out = func(_EdgeBatch(self))
        self.edata.update(out)

    def update_all(self, msg_func, reduce_func, apply_func=None):
        msgs = msg_func(_EdgeBatch(self))
        field, out = reduce_func.msg, reduce_func.out
        m = msgs[field]
        agg = scatter(m, self._dst, dim=0, dim_size=self._n, reduce=reduce_func.op)
        self.ndata[out] = agg
        if apply_func is not None:
            res = apply_func(_NodeBatch(self))
            if res:
                self.ndata.update(res)

    # ---- device / misc ----
    def to(self, device):
        if isinstance(device, int):
            device = f"cuda:{device}" if device >= 0 else "cpu"
        self._src = self._src.to(device)
        self._dst = self._dst.to(device)
        self.ndata = {k: v.to(device) for k, v in self.ndata.items()}
        self.edata = {k: v.to(device) for k, v in self.edata.items()}
        return self

    def local_var(self):
        return self


def graph(data, num_nodes=0):
    src, dst = data
    g = DGLGraph(num_nodes=num_nodes)
    g.add_edges(src, dst)
    return g


# ---- stub submodules để 'import dgl.xxx' không lỗi ----
class _Stub:
    def __getattr__(self, k):
        raise NotImplementedError(f"dgl shim: '{k}' chưa hỗ trợ")
