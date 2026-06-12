"""dgl.function shim: chỉ reducer fn.sum (+ vài alias) mà LogCL dùng."""


class _Reducer:
    def __init__(self, op, msg, out):
        self.op = op
        self.msg = msg
        self.out = out


def sum(msg, out):
    return _Reducer("sum", msg, out)


def mean(msg, out):
    return _Reducer("mean", msg, out)


def max(msg, out):
    return _Reducer("max", msg, out)


# copy_u/copy_src dùng cho message đơn giản (không bắt buộc cho uvrgcn)
def copy_u(u, out):
    return ("copy_u", u, out)


copy_src = copy_u
