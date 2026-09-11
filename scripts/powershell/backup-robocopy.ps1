# backup-robocopy.ps1 — Backup de pastas de usuário para storage central
# Etapa 2 do Projeto Bancada.
# Uso remoto: powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File backup-robocopy.ps1 -Destino "\\storage\Bancada\CLIENTE"

param(
    [Parameter(Mandatory = $true)]
    [string]$Destino
)

$usuarios = @(
    Get-ChildItem C:\Users -Directory |
        Where-Object { $_.Name -notin @('Public','Default','Default User','All Users') } |
        Select-Object -ExpandProperty Name
)

# Diretórios de interesse (padrão de bancada)
$pastas = @('Desktop','Documents','Downloads','Pictures')

$logDir = "C:\Windows\Temp"
$resultados = @()

foreach ($u in $usuarios) {
    foreach ($dir in $pastas) {
        $src = "C:\Users\$u\$dir"
        if (Test-Path $src) {
            $dst = "$Destino\$u\$dir"
            $log = "$logDir\robocopy_${u}_${dir}.log"
            robocopy $src $dst /E /ZB /R:1 /W:1 /XJ /XD "AppData\Local\Temp" "$RECYCLE.BIN" "System Volume Information" /LOG+:$log | Out-Null
            $code = $LASTEXITCODE
            $resultados += [ordered]@{ usuario = $u; pasta = $dir; codigo = $code }
        } else {
            $resultados += [ordered]@{ usuario = $u; pasta = $dir; codigo = -1; obs = 'pasta_inexistente' }
        }
    }
}

# Saída JSON para o orquestrador
$resultados | ConvertTo-Json -Depth 3