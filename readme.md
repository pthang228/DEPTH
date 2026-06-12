# DEPTH — Dual Evolution–Path Temporal Reasoning

Hợp nhất **LogCL** (suy luận theo tiến hóa nhúng) và một **path-reasoning head** kiểu CognTKE
(NBFNet/RED-GNN) thành **một mô hình end-to-end** cho bài toán **TKG extrapolation**.

Kết quả ICEWS14 (test, time-aware filtered `all_filter`): **MRR 0.527**, vượt cả CognTKE và LogCL
trên cả 4 chỉ số.

| Mô hình | MRR | Hits@1 | Hits@3 | Hits@10 |
|---|---|---|---|---|
| CognTKE (paper) | 46.06 | 36.49 | 51.11 | 64.49 |
| LogCL (paper) | 48.87 | 37.76 | 54.71 | 70.26 |
| **DEPTH (đề xuất)** | **52.72** | **41.89** | **58.61** | **73.21** |

---

## 1. Cấu trúc thư mục
```
UnifiedTKG/        <-- DEPTH (chạy ở đây): LogCL + inline path head + fusion gamma
  src/main.py      <-- điểm vào train/test
  src/rrgcn.py     <-- model (PathHead + fusion S = S_embed + gamma*z(S_path))
  src/dgl/         <-- dgl shim (torch_scatter) -> KHÔNG cần cài dgl
  rgcn/, data/     <-- tiện ích + dữ liệu
LogCL-main/        <-- bản LogCL gốc + shim (tham khảo)
build_slides.py    <-- dựng slide trình bày (DEPTH_slides.pptx)
parse_run_log.py   <-- đọc log 1 lần chạy -> báo cáo .md
DEPTH_report.md    <-- báo cáo kết quả ICEWS14
```
> Luu y: `data/`, checkpoint (`*.pt`), diem precompute (`*.pkl`), history (`*.npy`) KHONG nam trong repo
> (da .gitignore). Phai tu chuan bi data + train lai.

---

## 2. Cài đặt
Python 3.12, GPU CUDA 12.1.
```bash
pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cu121
pip install torch-scatter==2.1.2 -f https://data.pyg.org/whl/torch-2.3.0+cu121.html
pip install -r requirements.txt
```
Không cần `dgl` (đã thay bằng shim trong `UnifiedTKG/src/dgl`).

---

## 3. Chuẩn bị dữ liệu
Đặt dữ liệu thô vào `UnifiedTKG/data/<DATASET>/` gồm:
`train.txt, valid.txt, test.txt, entity2id.txt, relation2id.txt, stat.txt`.

Với MỖI dataset cần sinh thêm 2 thứ:

**(a) History subgraph** — sửa `data/get_his_subg.py`, dòng:
```python
dataset_list = ["ICEWS14"]      # đổi thành dataset cần chạy
```
rồi:
```bash
cd UnifiedTKG/data
python get_his_subg.py          # tạo his_graph_for/, his_graph_inv/, his_dict/
cd ..
```

**(b) Đồ thị tĩnh entity-word** (cần cho `--add-static-graph`):
```bash
cd UnifiedTKG/data/<DATASET>
python ent2word.py              # tạo e-w-graph.txt
cd ../..
```
> Windows: nếu `ent2word.py` lỗi UnicodeDecode -> thêm `encoding='utf-8'` vào các lệnh `open(...)`.

---

## 4. Train

### ICEWS14 (mặc định)
```bash
cd UnifiedTKG
python src/main.py -d ICEWS14 --train-history-len 7 --test-history-len 7 --dilate-len 1 \
  --lr 0.001 --n-layers 2 --evaluate-every 1 --gpu 0 --n-hidden 200 --self-loop \
  --decoder convtranse --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction \
  --angle 10 --discount 1 --pre-weight 0.9 --pre-type all --add-static-graph \
  --temperature 0.03 --use-cl
```
Đầu log phải có `[unified] inline path head ON` (đây là DEPTH). Tự early-stop, ~3.5 phút/epoch.

### ICEWS18
1. Làm mục 3(a)(b) với `dataset_list = ["ICEWS18"]`.
2. Train (đổi `-d ICEWS18`):
```bash
cd UnifiedTKG
python src/main.py -d ICEWS18 --train-history-len 7 --test-history-len 7 --dilate-len 1 \
  --lr 0.001 --n-layers 2 --evaluate-every 1 --gpu 0 --n-hidden 200 --self-loop \
  --decoder convtranse --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction \
  --angle 10 --discount 1 --pre-weight 0.9 --pre-type all --add-static-graph \
  --temperature 0.03 --use-cl
```
> **Bộ nhớ:** ICEWS18 có 23033 thực thể -> nặng. Path head tự giảm chunk (`CH=8` khi N>=10000).
> **Cần GPU >= 8GB.** GPU 4GB sẽ OOM (riêng LogCL base đã gần đầy). Nếu OOM, thử:
> ```bash
> # PowerShell
> $env:PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
> # hoặc giảm --n-hidden 100
> ```

---

## 5. Đọc kết quả -> báo cáo
```bash
# lưu log khi chạy:  python src/main.py ... 2>&1 | tee run.log
python parse_run_log.py run.log --name "DEPTH-ICEWS14" --out report.md
```
Tự rút: cấu hình, MRR từng epoch, best epoch, gamma, kết quả test + bảng so 2 paper.

---

## 6. Ghi chú
- **dgl shim:** `UnifiedTKG/src/dgl` thay dgl bằng `torch_scatter` để chạy không cần dgl-CUDA
  (đã tái lập đúng số LogCL/CognTKE trên ICEWS14).
- **Nhãn metric:** code in `Hits@ (1,3,5)` nhưng `rgcn/utils.py` đặt `hits=[1,3,10]` -> **cột 4 là Hits@10**.
- **Tính chất:** Head B (path) inductive, nhưng Head A dùng embedding thực thể -> tổng thể **transductive**
  (đúng thiết lập chuẩn ICEWS14).

## Build slide (tùy chọn)
```bash
python build_slides.py     # -> DEPTH_slides.pptx
```
