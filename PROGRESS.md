# PROGRESS — Cải tiến CognTKE (luận án TKG extrapolation, ICEWS14)

> File ghi nhớ toàn bộ tiến trình. Đọc lại nếu mất context.

## Mục tiêu
Cải tiến CognTKE (AAAI 2025, path-based TKG extrapolation) để tăng MRR trên ICEWS14,
mục tiêu ≥ 47-48. CognTKE là **phương pháp chính** của luận án.

## KẾT QUẢ CUỐI (test, time-aware filtered `all_filter`, cùng code/eval)
| Model | MRR | Hits@1 | Hits@3 | Hits@5/10 |
|---|---|---|---|---|
| CognTKE (path) đơn | 0.4624 | 0.3669 | 0.5113 | 0.6449 |
| LogCL đơn — no-cl, trên shim (CŨ, baseline yếu) | 0.4671 | 0.3555 | 0.5222 | ~0.687 |
| **LogCL đơn — CÓ use-cl (baseline ĐÚNG)** | **0.4912** | **0.3812** | **0.5490** | 0.7034 (@5) |
| FUSED — γ vô hướng, no-cl (CŨ, delta thổi phồng) | 0.5140 | 0.4115 | 0.5691 | 0.7152 |
| FUSED — gating + use-cl | 0.5041 | 0.3928 | 0.5648 | 0.7160 (@5) |
| ★ FUSED late — γ vô hướng + cl (CognTKE đóng băng, 2 mô hình) | 0.5199 | 0.4109 | 0.5784 | 0.7319 (@10) |
| **★★ UNIFIED end-to-end (1 mô hình) — TỐT NHẤT** | **0.5272** | **0.4189** | **0.5861** | **0.7321** (@10) |

> ⚠️ Cột 4 = **Hits@10** (rgcn/utils.py:204 `hits=[1,3,10]`; nhãn in "(1,3,5)" SAI). Khớp paper: LogCL@10=0.7034≈70.26, CognTKE@10=0.6449=64.49.

> ★★ CHỐT 2026-06-09: **UNIFIED end-to-end = 0.5272** > late-fusion 0.5199 > LogCL 0.4912 > CognTKE 0.4624.
>   Thư mục: `UnifiedTKG/`. 1 backbone chung + Head A (LogCL) + Head B (path inline relation-only) + γ.
>   Head B port NBFNet/RED-GNN style, dùng chung emb_rel, train END-TO-END. Best epoch 13, ~3.5 ph/epoch.
>   So paper: vượt CognTKE +6.66 / LogCL +3.85 MRR. Cao hơn + gọn (bỏ precompute+pkl, 1 mô hình).
>   ⚠️ TRANSDUCTIVE: Head B inductive nhưng Head A dùng dynamic_emb -> TỔNG THỂ vẫn transductive (như late-fusion).
>   Vì sao > late-fusion: path head học chung -> tự thích nghi bù lỗi embedding (frozen fusion không làm được).
> Cột thứ 4 = Hits@5 (nhãn code (1,3,5)); paper báo Hits@10 nên chỉ so trực tiếp MRR/H@1/H@3.

> ★ γ vô hướng + cl (late-fusion) = **0.5199** > gating 0.5041 > baseline 0.4912.
>   Delta thật so baseline đúng = **+2.9 MRR / +3.0 Hits@1**. So CognTKE gốc 0.4624 = **+5.75 MRR**.
>   γ hội tụ ~0.10-0.12 (best epoch 7). Code HIỆN TẠI đã là bản γ vô hướng (đã revert khỏi gating).
> Bài học: cơ chế ĐƠN GIẢN (1 scalar γ) MẠNH HƠN gating MLP (gating overfit tín hiệu path thưa).
>   → Dùng γ vô hướng: vừa cao hơn, vừa dễ giải thích/bảo vệ (1 tham số), vừa không nan.

> XÁC NHẬN 2026-06-09: LogCL+cl trên shim = 0.4912 (≥ paper 0.489) → **shim CHUẨN**, bỏ caveat #1+#2.
> Baseline so sánh giờ là **0.4912** (không phải 0.467). Delta thật fusion = fused_cl − 0.4912.
> Bug nan của gating (z-norm thưa → cổng nổ) đã vá: kẹp pd ±5, chuẩn hóa feat gate, kẹp g≤3.
> CŨ: Fusion +4.7 so nền yếu 0.467 là THỔI PHỒNG — phải báo cáo delta so 0.4912.

## Ý TƯỞNG / KIẾN TRÚC
Hợp nhất 2 nhánh KHÁC HỌ (lỗi bù trừ → fusion lời lớn):
- **Nhánh 1 (bổ trợ): Embedding-evolution** = LogCL/RE-GCN (RGCN mỗi snapshot + GRU tiến hóa
  + global attention + contrastive + ConvTransE) → `S_embed` dày đặc.
- **Nhánh 2 (chính): Path** = CognTKE TCR-Digraph (retrieval hop0 global + hop local,
  message-passing) → `S_path` thưa (in-graph). **Precompute sẵn, đóng băng.**
- **Fusion**: `S = S_embed + γ·z-norm(S_path)`, γ = nn.Parameter học được (init 0 → sàn = LogCL).

Khung luận án: CognTKE = chính; nhánh embedding = module bổ trợ (cite RE-GCN/contrastive,
KHÔNG gọi tên LogCL như method chính); **đóng góp = cơ chế fusion γ-học hợp nhất 2 họ**.

## FILE ĐÃ TẠO / SỬA

### Phía CognTKE (thư mục gốc `CognTKE-main/`)
- `precompute_path.py` (MỚI): tính sẵn điểm path CognTKE cho mọi (s,r,t) → `cogntke_path_scores.pkl`
  (161779 keys, 365 timestamp). Dùng checkpoint `results/TRED_GNN/L3/ICEWS14s/2026-06-02-21-19/best_weight.pt`.
  Chạy: `python precompute_path.py` (BS=48, resume được, ~20 phút, không cần dgl).
- `models/TRED_GNN.py`: có alias `TRED_GNN=TRED_GNN20` + nhiều cờ thử nghiệm (use_global_scorer,
  use_query_gate, use_route_gate, use_reranker, use_entity_embed, use_contrastive, use_logcl, use_fusion).
  → CHỈ global_scorer là cải tiến nhẹ thật (0.4624). Các cờ khác đều ~baseline (xem "Đã thử & thất bại").
- `models/CYGNET.py`, `models/REGCN.py` (MỚI): nhánh embedding tự viết (yếu: ~0.30-0.37) — KHÔNG dùng cho kết quả cuối.
- `models/reranker.py` (MỚI): reranker hop-cuối + path (train loss phẳng → bỏ).
- Probe scripts: `oracle_probe.py`, `ensemble_probe.py`, `ensemble_probe2.py`, `eval_fallback.py`, `phase0_probe.py`.
- `model_architecture.html`, `entity_journey.html`: visualize kiến trúc (mở bằng browser).

### Phía LogCL (`LogCL-main/`) — ĐÂY LÀ NƠI CHẠY KẾT QUẢ CUỐI
- `src/dgl/` (TẠO MỚI, QUAN TRỌNG): **shim dgl bằng torch_scatter** thay dgl thật
  (vì Windows+py3.12 không có dgl-CUDA). Gồm __init__.py, function.py, nn/pytorch/softmax.py, data/utils.py.
  Đối chiếu khớp UnionRGCN (sum theo node ×1/in-degree + self-loop). **Đây là biến số duy nhất có thể lệch số gốc.**
- `src/rrgcn.py` (SỬA): thêm `path_gamma`(Parameter), `PathFuser`, `cur_split`, `_fuse_path()`;
  trong `predict()` & `get_loss()` cộng `scores_ob += γ·path` trước softmax. **Chỉ bật khi có file pkl.**
- `path_fuse.py` (MỚI): class PathFuser nạp `cogntke_path_scores.pkl`, dựng dense theo (s,r,t).
  Offset thời gian: train t=time_idx; valid t=304+idx; test t=334+idx (ICEWS14: 304/30/31 snapshot).
- `src/main.py` (SỬA): set `model.cur_split`; print `[fusion] path_gamma`.
- `src/hyperparameter_range.py` (MỚI stub `hp_range={}` — repo thiếu sẵn).
- `rgcn/knowledge_graph.py`, `data/ICEWS14/ent2word.py` (SỬA): thêm `encoding='utf-8'` (lỗi đọc file Windows).
- `data/get_his_subg.py` (SỬA): `dataset_list=["ICEWS14"]`.
- `cogntke_path_scores.pkl`, `models/`, `result/`: cần có để chạy.

## CÁCH CHẠY (Windows, torch 2.3.0+cu121, dgl đã gỡ, shim trong src/dgl)
```powershell
cd LogCL-main
# FUSED (có file pkl):
python src/main.py -d ICEWS14 --train-history-len 7 --test-history-len 7 --dilate-len 1 --lr 0.001 ^
  --n-layers 2 --evaluate-every 1 --gpu=0 --n-hidden 200 --self-loop --decoder convtranse ^
  --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction --angle 10 --discount 1 ^
  --pre-weight 0.9 --pre-type all --add-static-graph --temperature 0.03
# LogCL-alone (baseline): ren cogntke_path_scores.pkl -> .bak rồi chạy lại; xong ren lại.
```
Tiền xử lý 1 lần: `cd data; python get_his_subg.py; cd ICEWS14; python ent2word.py`.

## CAVEAT (phải dọn trước khi bảo vệ)
1. **Chưa bật `--use-cl`** → LogCL-alone = 0.467 < paper 0.489. Nghi can chính của gap (KHÔNG phải shim).
   → Chạy lại CẢ fused + alone CÓ `--use-cl` để có số chuẩn + verify shim.
2. **Shim dgl** chưa verify từng số vs dgl thật (không có dgl-CUDA trên Windows). Nếu cần chắc 100%: chạy WSL2/Colab.
3. **Fused best epoch = 1** (CognTKE path bơm tín hiệu sớm). Model selection by valid → hợp lệ nhưng có thể bị hỏi.
4. **Cùng filter đã xác minh**: LogCL `load_all_answers_for_time_filter` = time-aware, giống CognTKE. ✓

## ĐÃ THỬ & THẤT BẠI (trên ICEWS14s, single-model, đều ~0.46 — trần dữ liệu)
global-scorer (0.4624, vượt paper nhẹ), time-decay prior, query-gate, route-gate, entity-embed,
recurrence (s,r,o), reranker hop-cuối + path (loss phẳng), multi-head attn (tệ hơn), scaling hidden128 (OOM).
→ Kết luận: single-model CognTKE bão hòa ~0.46. Chỉ **fusion cross-family với LogCL** mới phá trần (0.514).
Oracle analysis: 84% đáp án in-graph nhưng chỉ 43% xếp #1 → headroom ở ranking.

## NEXT STEPS (nâng tầm luận án — fusion thuần hơi mỏng)
1. Chạy lại có `--use-cl` (số sạch).
2. Gating fusion theo query (γ tùy query, không vô hướng) = cơ chế mới.
3. Phân tích bổ trợ: khi nào path thắng vs embedding (định lượng) — đóng góp khoa học.
4. Tính diễn giải (đường bằng chứng CognTKE) — điểm bán mạnh.
5. Ablation đầy đủ + thêm dataset (ICEWS18/05-15/GDELT).
