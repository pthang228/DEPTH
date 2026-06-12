# HƯỚNG DẪN CHẠY DEPTH — A→Z (3 dataset)

Áp dụng cho Windows + PowerShell. Mọi lệnh chạy trong thư mục `UnifiedTKG`.

Dataset | Số thực thể | Yêu cầu GPU | Ghi chú
---|---|---|---
ICEWS14 | 7128 | ~4GB+ | nhẹ, ~3.5 phút/epoch
ICEWS05-15 | 10488 | ~6–8GB | nhiều snapshot → tiền xử lý & train chậm
ICEWS18 | 23033 | **≥8GB** | nặng nhất, GPU 4GB sẽ OOM

---

## BƯỚC 0 — Cài đặt (làm 1 lần)
```powershell
pip install torch==2.3.0 --index-url https://download.pytorch.org/whl/cu121
pip install torch-scatter==2.1.2 -f https://data.pyg.org/whl/torch-2.3.0+cu121.html
pip install -r requirements.txt
```
(Không cần dgl — dùng shim sẵn trong `UnifiedTKG/src/dgl`.)

Kiểm tra GPU:
```powershell
nvidia-smi
```

---

## BƯỚC 1 — Đảm bảo có dữ liệu thô
Mỗi dataset phải có thư mục `UnifiedTKG/data/<TÊN>/` chứa:
`train.txt, valid.txt, test.txt, entity2id.txt, relation2id.txt, stat.txt, ent2word.py`
- ICEWS14, ICEWS18, ICEWS05-15: đã có sẵn.
- GDELT: mới ở dạng `GDELT.zip` → cần giải nén nếu muốn dùng.

---

# ============== ICEWS14 ==============

### 1a. Sinh history subgraph
Mở `UnifiedTKG/data/get_his_subg.py`, sửa dòng (khoảng dòng 139):
```python
dataset_list = ["ICEWS14"]
```
Chạy:
```powershell
cd "F:\New folder\CognTKE-main\CognTKE-main\UnifiedTKG\data"
python get_his_subg.py
cd ..
```
→ tạo `data/ICEWS14/his_graph_for/`, `his_graph_inv/`, `his_dict/`.

### 1b. Sinh đồ thị tĩnh
```powershell
cd data\ICEWS14
python ent2word.py
cd ..\..
```
→ tạo `e-w-graph.txt`. (Nếu lỗi UnicodeDecode: thêm `encoding='utf-8'` vào các lệnh `open(...)` trong `ent2word.py`.)

### 1c. Train (xem trực tiếp trên màn hình)
```powershell
python src/main.py -d ICEWS14 --train-history-len 7 --test-history-len 7 --dilate-len 1 --lr 0.001 --n-layers 2 --evaluate-every 1 --gpu=0 --n-hidden 200 --self-loop --decoder convtranse --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction --angle 10 --discount 1 --pre-weight 0.9 --pre-type all --add-static-graph --temperature 0.03 --use-cl
```
Đầu log phải có: `[unified] inline path head ON`. Tự early-stop (~13–30 epoch).

### 1d. (tùy chọn) lưu log + đọc báo cáo
```powershell
# lưu log:
python src/main.py -d ICEWS14 ... --use-cl *> icews14.txt
# đọc báo cáo:
python parse_run_log.py icews14.txt --name "DEPTH-ICEWS14" --out icews14_report.md
```

---

# ============== ICEWS05-15 ==============

### 2a. Sinh history subgraph
Sửa `data/get_his_subg.py`:
```python
dataset_list = ["ICEWS05-15"]
```
Chạy (CHẬM — nhiều snapshot, có thể vài chục phút):
```powershell
cd "F:\New folder\CognTKE-main\CognTKE-main\UnifiedTKG\data"
python get_his_subg.py
cd ..
```

### 2b. Sinh đồ thị tĩnh
```powershell
cd data\ICEWS05-15
python ent2word.py
cd ..\..
```
(Nếu lỗi UnicodeDecode → thêm `encoding='utf-8'` vào `open(...)` trong file này.)

### 2c. Train
```powershell
$env:PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
python src/main.py -d ICEWS05-15 --train-history-len 7 --test-history-len 7 --dilate-len 1 --lr 0.001 --n-layers 2 --evaluate-every 1 --gpu=0 --n-hidden 200 --self-loop --decoder convtranse --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction --angle 10 --discount 1 --pre-weight 0.9 --pre-type all --add-static-graph --temperature 0.03 --use-cl
```
> 10488 thực thể → nếu OOM trên GPU nhỏ: thêm `--n-hidden 100`.

### 2d. Báo cáo
```powershell
python src/main.py -d ICEWS05-15 ... --use-cl *> icews0515.txt
python parse_run_log.py icews0515.txt --name "DEPTH-ICEWS05-15" --out icews0515_report.md
```

---

# ============== ICEWS18 ==============

### 3a. Sinh history subgraph
Sửa `data/get_his_subg.py`:
```python
dataset_list = ["ICEWS18"]
```
Chạy:
```powershell
cd "F:\New folder\CognTKE-main\CognTKE-main\UnifiedTKG\data"
python get_his_subg.py
cd ..
```

### 3b. Sinh đồ thị tĩnh
```powershell
cd data\ICEWS18
python ent2word.py
cd ..\..
```

### 3c. Train (CẦN GPU ≥ 8GB)
```powershell
$env:PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
python src/main.py -d ICEWS18 --train-history-len 7 --test-history-len 7 --dilate-len 1 --lr 0.001 --n-layers 2 --evaluate-every 1 --gpu=0 --n-hidden 200 --self-loop --decoder convtranse --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction --angle 10 --discount 1 --pre-weight 0.9 --pre-type all --add-static-graph --temperature 0.03 --use-cl
```
> 23033 thực thể → **GPU 4GB sẽ OOM** (riêng LogCL base đã gần đầy). Cần ≥8GB.
> Nếu vẫn OOM: thêm `--n-hidden 100`. Path head tự giảm chunk (CH=8) khi N≥10000.

### 3d. Báo cáo
```powershell
python src/main.py -d ICEWS18 ... --use-cl *> icews18.txt
python parse_run_log.py icews18.txt --name "DEPTH-ICEWS18" --out icews18_report.md
```

---

## MẸO CHUNG
- **Đổi dataset = đổi 2 chỗ:** dòng `dataset_list` trong `get_his_subg.py` (bước a) + cờ `-d <TÊN>` khi train.
- **Xem live vs lưu file:** bỏ `*> file.txt` để xem thẳng trên màn hình; thêm vào để dồn ra file.
- **Dấu hiệu chạy ĐÚNG (DEPTH):** đầu log có `[unified] inline path head ON`. Nếu thấy `[fusion] loaded CognTKE path scores` là bạn đang chạy nhầm trong `LogCL-main` (KHÔNG phải DEPTH).
- **Loss = nan?** báo lại; **CUDA out of memory?** giảm `--n-hidden 100` hoặc dùng GPU lớn hơn.
- **Early-stop:** patience 5 epoch; model tự lưu checkpoint tốt nhất và tự test khi dừng.
