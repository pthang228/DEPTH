# Chờ run LogCL hiện tại (process python) kết thúc -> chạy FUSED tự động.
# Cách dùng: MỞ 1 CỬA SỔ PowerShell MỚI (không tắt cửa sổ đang chạy), rồi:
#   cd "F:\New folder\CognTKE-main\CognTKE-main\LogCL-main"
#   powershell -ExecutionPolicy Bypass -File run_fused_after.ps1

$ErrorActionPreference = "Continue"
Set-Location "F:\New folder\CognTKE-main\CognTKE-main\LogCL-main"

# ID của tiến trình PowerShell này (để không tự đếm nhầm)
Write-Host ("[{0}] Dang cho run LogCL hien tai (python) ket thuc..." -f (Get-Date -Format "HH:mm:ss"))

# Chờ tới khi KHÔNG còn process python nào chạy
while ($true) {
    $py = Get-Process python -ErrorAction SilentlyContinue
    if (-not $py) { break }
    Start-Sleep -Seconds 30
}

Write-Host ("[{0}] Run LogCL da xong. Chuyen sang FUSED." -f (Get-Date -Format "HH:mm:ss"))

# Bật fusion: đổi tên file pkl về
if (Test-Path "cogntke_path_scores.pkl.bak") {
    if (Test-Path "cogntke_path_scores.pkl") { Remove-Item "cogntke_path_scores.pkl" -Force }
    Rename-Item "cogntke_path_scores.pkl.bak" "cogntke_path_scores.pkl"
    Write-Host "[fusion] da doi ten pkl ve -> fusion BAT"
} elseif (Test-Path "cogntke_path_scores.pkl") {
    Write-Host "[fusion] pkl da co san -> fusion BAT"
} else {
    Write-Host "[CANH BAO] KHONG tim thay cogntke_path_scores.pkl(.bak) -> fused se chay nhu LogCL rieng!"
}

$log = "fused_run_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss")
Write-Host ("[{0}] Bat dau FUSED, log -> {1}" -f (Get-Date -Format "HH:mm:ss"), $log)

python src/main.py -d ICEWS14 --train-history-len 7 --test-history-len 7 --dilate-len 1 --lr 0.001 --n-layers 2 --evaluate-every 1 --gpu=0 --n-hidden 200 --self-loop --decoder convtranse --encoder uvrgcn --layer-norm --weight 0.5 --entity-prediction --angle 10 --discount 1 --pre-weight 0.9 --pre-type all --add-static-graph --temperature 0.03 --use-cl *> $log

Write-Host ("[{0}] FUSED xong. Xem ket qua o cuoi file {1}" -f (Get-Date -Format "HH:mm:ss"), $log)
