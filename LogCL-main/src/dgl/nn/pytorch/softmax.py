from torch_scatter import scatter_softmax


def edge_softmax(g, logits, eids=None):
    # softmax theo node đích (chỉ dùng trong RGAT, không nằm trên đường uvrgcn)
    return scatter_softmax(logits, g._dst, dim=0)
