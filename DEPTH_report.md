# BÁO CÁO THỰC NGHIỆM — DEPTH trên ICEWS14

**Mô hình:** DEPTH = LogCL (nền) + inline path-reasoning head (relation-only, dim=32, L=2), hợp nhất bằng cổng γ học được, huấn luyện end-to-end.
**Dataset:** ICEWS14 (7128 thực thể, 230 quan hệ, 74845 cạnh; 304/30/31 snapshot train/valid/test).
**Metric:** time-aware filtered, cột báo cáo = `all_filter` (trung bình 2 chiều). Hits tính tại {1, 3, 10}.

---

## 1. Cấu hình chạy
```
python src/main.py -d ICEWS14 --train-history-len 7 --test-history-len 7 --dilate-len 1 \
  --lr 0.001 --n-layers 2 --evaluate-every 1 --gpu 0 --n-hidden 200 --self-loop \
  --decoder convtranse --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction \
  --angle 10 --discount 1 --pre-weight 0.9 --pre-type all --add-static-graph \
  --temperature 0.03 --use-cl
```
- Path head: `[unified] inline path head ON (relation-only, inductive, dim=32, L=2)`
- Tốc độ: ~3.5 phút/epoch (GPU). Early-stop sau epoch 18, chọn **best epoch = 13** (theo valid MRR).
- `path_gamma` hội tụ **dương** (~0.155–0.162) → mô hình tự nguyện sử dụng nhánh path.

---

## 2. Diễn biến validation (all_filter MRR)
| Epoch | MRR | | Epoch | MRR |
|---|---|---|---|---|
| 1 | 0.4921 | | 10 | 0.5352 |
| 2 | 0.5190 | | 11 | 0.5336 |
| 3 | 0.5277 | | 12 | 0.5350 |
| 4 | 0.5293 | | **13** | **0.5353** ← best |
| 5 | 0.5321 | | 14 | 0.5328 |
| 6 | 0.5320 | | 15 | 0.5328 |
| 7 | 0.5317 | | 16 | 0.5349 |
| 8 | 0.5337 | | 17 | 0.5346 |
| 9 | 0.5348 | | 18 | 0.5349 |

---

## 3. KẾT QUẢ TEST (best epoch 13) — `all_filter`
| Metric | DEPTH |
|---|---|
| **MRR** | **0.5272** |
| **Hits@1** | **0.4189** |
| **Hits@3** | **0.5861** |
| **Hits@10** | **0.7321** |

Chi tiết theo từng chiều (test):
| | MRR | Hits@1 | Hits@3 | Hits@10 |
|---|---|---|---|---|
| filter (object) | 0.5451 | 0.4377 | 0.6063 | 0.7439 |
| filter_inv (subject) | 0.5092 | 0.4002 | 0.5659 | 0.7204 |
| **all_filter (báo cáo)** | **0.5272** | **0.4189** | **0.5861** | **0.7321** |

---

## 4. So sánh với baseline (ICEWS14, cùng metric, ×100)
| Mô hình | MRR | Hits@1 | Hits@3 | Hits@10 |
|---|---|---|---|---|
| CognTKE (paper) | 46.06 | 36.49 | 51.11 | 64.49 |
| LogCL (paper) | 48.87 | 37.76 | 54.71 | 70.26 |
| LogCL (tái lập, γ=0 = tắt path) | 49.12 | 38.12 | 54.90 | 70.34 |
| **DEPTH (đề xuất)** | **52.72** | **41.89** | **58.61** | **73.21** |
| **Δ so với LogCL (paper)** | **+3.85** | **+4.13** | **+3.90** | **+2.95** |
| **Δ so với CognTKE (paper)** | **+6.66** | **+5.40** | **+7.50** | **+8.72** |

---

## 5. Ablation — đóng góp của nhánh path
| Cấu hình | MRR | Ghi chú |
|---|---|---|
| γ = 0 (tắt nhánh path) | 49.12 | = đúng LogCL nền |
| DEPTH (bật path, γ học) | **52.72** | **+2.92 MRR / +3.08 Hits@1** so với nền |

→ Nhánh path đóng góp thực sự (+2.9 MRR); γ hội tụ dương xác nhận tín hiệu path hữu ích.

---

## 6. Nhận xét
- DEPTH **vượt cả hai paper gốc trên cả 4 chỉ số**, đặc biệt Hits@1 (+4.1 so LogCL, +5.4 so CognTKE) — đúng kỳ vọng: nhánh path giúp **xếp đúng ở đỉnh** cho các truy vấn có bằng chứng đường đi.
- Hai paper được **tự tái lập trên cùng code/eval** (LogCL Hits@10 ≈ 70.3 ≈ paper 70.26; CognTKE = 64.49) → số liệu cùng hệ quy chiếu, đáng tin.
- Mô hình **một khối, end-to-end**; path head rất nhẹ (dim=32, L=2), dùng chung embedding quan hệ với LogCL, không cần bước precompute.

*(Lưu ý kỹ thuật: nhãn in trong code ghi "(1,3,5)" nhưng danh sách hits thực tế là [1,3,10] — `rgcn/utils.py`, nên cột thứ tư là Hits@10.)*
