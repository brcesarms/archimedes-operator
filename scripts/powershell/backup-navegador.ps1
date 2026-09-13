# backup-navegador.ps1 — Backup de FAVORITOS + SENHAS (criptografadas) dos navegadores
# Chrome / Edge (detecta o navegador padrão pela associação http; fallback por instalação).
#
# ⚠️ SENHAS: copiadas SOMENTE como arquivo criptografado do navegador
# (Login Data, protegido por DPAPI no Windows) — NUNCA em texto plano.
# Restauram no mesmo usuário/máquina.
#
# Uso remoto:
#   powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File backup-navegador.ps1 -Destino "\\10.0.0.4\backup\CLIENTE"
# Saída: JSON (navegador detectado + perfis copiados)

param(
    [Parameter(Mandatory = $true)]
    [string]$Destino
)

$progId = $null
try {
    $progId = (Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice' -Name ProgId -ErrorAction Stop).ProgId
} catch { }

$browser = $null
switch -Wildcard ($progId) {
    'ChromeHTML*' { $browser = 'chrome' }
    'MSEdgeHTM*'  { $browser = 'edge' }
    default {
        # Fallback: procura por instalação
        if (Test-Path "$env:LOCALAPPDATA\Google\Chrome\User Data")      { $browser = 'chrome' }
        elseif (Test-Path "$env:LOCALAPPDATA\Microsoft\Edge\User Data") { $browser = 'edge' }
    }
}

if (-not $browser) {
    [ordered]@{ navegador = $null; obs = 'nenhum chrome/edge instalado' } | ConvertTo-Json
    exit 0
}

$userData = if ($browser -eq 'chrome') { "$env:LOCALAPPDATA\Google\Chrome\User Data" }
            else                       { "$env:LOCALAPPDATA\Microsoft\Edge\User Data" }

if (-not (Test-Path $userData)) {
    [ordered]@{ navegador = $browser; obs = "user data nao encontrado: $userData" } | ConvertTo-Json
    exit 0
}

$destNav = "$Destino\navegador\$browser"
New-Item -ItemType Directory -Force -Path $destNav | Out-Null

$resultados = @()

# Local State — chave de criptografia (ajuda a restaurar senhas no mesmo usuário)
if (Test-Path "$userData\Local State") {
    robocopy $userData $destNav "Local State" /R:1 /W:1 | Out-Null
    $resultados += [ordered]@{ tipo = 'local_state'; codigo = $LASTEXITCODE }
}

# Perfis: Default + Profile N
$perfis = @(Get-ChildItem $userData -Directory |
    Where-Object { $_.Name -eq 'Default' -or $_.Name -like 'Profile*' })

foreach ($p in $perfis) {
    $dstPerfil = "$destNav\$($p.Name)"
    New-Item -ItemType Directory -Force -Path $dstPerfil | Out-Null
    robocopy $p.FullName $dstPerfil "Bookmarks" "Bookmarks.bak" "Login Data" "Login Data-journal" /R:1 /W:1 | Out-Null
    $resultados += [ordered]@{ tipo = 'perfil'; perfil = $p.Name; codigo = $LASTEXITCODE }
}

[ordered]@{
    navegador = $browser
    progid    = $progId
    dest      = $destNav
    itens     = $resultados
} | ConvertTo-Json -Depth 4