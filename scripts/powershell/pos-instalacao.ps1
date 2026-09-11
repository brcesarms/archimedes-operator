﻿#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Pos-instalacao do Windows — ajustes de sistema + softwares essenciais (bancada).
.DESCRIPTION
    1. Libera a execucao de scripts do PowerShell (Unrestricted).
    2. Desativa o gerenciamento de energia (video, suspensao e hibernacao).
    3. Ativa o tema escuro no Windows.
    4. Desativa o Historico de Atividades (Activity History).
    5. Desativa aplicativos em segundo plano.
    6. Instala aplicativos essenciais via winget.
    7. Instala runtimes essenciais via winget (.NET Framework, .NET Runtime e VC++ Redistributable).
.NOTES
    Requer Windows PowerShell 5.1+ e winget (App Installer). Executar como Administrador.
#>

[CmdletBinding()]
param(
    [switch]$SkipApps,     # pula a instalacao dos aplicativos (Etapa 6)
    [switch]$SkipRuntimes  # pula a instalacao dos runtimes (Etapa 7)
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Erros = @()

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "🏛️  Archimedes — Pos-instalacao do Windows" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------
# Etapa 1 — Liberar execucao de scripts do PowerShell
# ---------------------------------------------------------------
Write-Host "`n🚀 [1/7] Liberando execucao de scripts PowerShell..." -ForegroundColor Cyan
try {
    Set-ExecutionPolicy -ExecutionPolicy Unrestricted -Scope LocalMachine -Force
    Write-Host "✔ ExecutionPolicy definida como Unrestricted!" -ForegroundColor Green
} catch {
    Write-Host "✖ Falha ao alterar ExecutionPolicy: $($_.Exception.Message)" -ForegroundColor Red
    $Erros += "ExecutionPolicy"
}

# ---------------------------------------------------------------
# Etapa 2 — Desativar gerenciamento de energia
# ---------------------------------------------------------------
Write-Host "`n🔌 [2/7] Desativando gerenciamento de energia..." -ForegroundColor Cyan
$powerCmds = @(
    "powercfg.exe /SETACVALUEINDEX SCHEME_CURRENT SUB_VIDEO VIDEOIDLE 0"
    "powercfg.exe /SETDCVALUEINDEX SCHEME_CURRENT SUB_VIDEO VIDEOIDLE 0"
    "powercfg.exe /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0"
    "powercfg.exe /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP STANDBYIDLE 0"
    "powercfg.exe /SETACVALUEINDEX SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE 0"
    "powercfg.exe /SETDCVALUEINDEX SCHEME_CURRENT SUB_SLEEP HIBERNATEIDLE 0"
)
foreach ($cmd in $powerCmds) {
    cmd /c $cmd 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✔ $cmd" -ForegroundColor Green
    } else {
        Write-Host "  ✖ Falha: $cmd (code $LASTEXITCODE)" -ForegroundColor Red
        $Erros += "powercfg: $cmd"
    }
}
powercfg.exe /SETACTIVE SCHEME_CURRENT
Write-Host "✔ Gerenciamento de energia desativado (tela, suspensao e hibernacao)!" -ForegroundColor Green

# ---------------------------------------------------------------
# Etapa 3 — Ativar tema escuro (apps + sistema)
# ---------------------------------------------------------------
Write-Host "`n🌙 [3/7] Ativando tema escuro..." -ForegroundColor Cyan
$darkReg = @(
    @{ Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"; Name = "AppsUseLightTheme";   Value = 0 }
    @{ Path = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"; Name = "SystemUsesLightTheme"; Value = 0 }
)
foreach ($reg in $darkReg) {
    New-Item -Path $reg.Path -Force | Out-Null
    Set-ItemProperty -Path $reg.Path -Name $reg.Name -Value $reg.Value -Type DWord
}
Write-Host "✔ Tema escuro ativado (apps e sistema)!" -ForegroundColor Green

# ---------------------------------------------------------------
# Etapa 4 — Desativar Historico de Atividades
# ---------------------------------------------------------------
Write-Host "`n🕵️  [4/7] Desativando Historico de Atividades..." -ForegroundColor Cyan
try {
    $advPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
    New-Item -Path $advPath -Force | Out-Null
    Set-ItemProperty -Path $advPath -Name "Start_TrackDocs" -Value 0 -Type DWord
    Write-Host "✔ Historico de Atividades desativado!" -ForegroundColor Green
} catch {
    Write-Host "✖ Falha ao desativar Historico de Atividades: $($_.Exception.Message)" -ForegroundColor Red
    $Erros += "Start_TrackDocs"
}

# ---------------------------------------------------------------
# Etapa 5 — Desativar aplicativos em segundo plano
# ---------------------------------------------------------------
Write-Host "`n📵  [5/7] Desativando aplicativos em segundo plano..." -ForegroundColor Cyan
try {
    $bgPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
    New-Item -Path $bgPath -Force | Out-Null
    Set-ItemProperty -Path $bgPath -Name "GlobalUserDisabled" -Value 1 -Type DWord
    Write-Host "✔ Aplicativos em segundo plano desativados!" -ForegroundColor Green
} catch {
    Write-Host "✖ Falha ao desativar Background Apps: $($_.Exception.Message)" -ForegroundColor Red
    $Erros += "BackgroundAccessApplications"
}

# ---------------------------------------------------------------
# Helper — instalar pacote via winget
# ---------------------------------------------------------------
function Install-WinGetApp {
    param(
        [Parameter(Mandatory)][string]$ID,
        [string]$Categoria = "Aplicativo"
    )
    Write-Host "  📦 [$Categoria] Instalando $ID ..." -ForegroundColor Yellow
    winget install --id=$ID -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✔ $ID instalado com sucesso!" -ForegroundColor Green
    } else {
        Write-Host "  ✖ Falha ao instalar $ID (winget code: $LASTEXITCODE)" -ForegroundColor Red
        $script:Erros += "$ID (winget code $LASTEXITCODE)"
    }
}

# ---------------------------------------------------------------
# Etapa 6 — Aplicativos essenciais
# ---------------------------------------------------------------
if (-not $SkipApps) {
    Write-Host "`n🧩 [6/7] Instalando aplicativos essenciais..." -ForegroundColor Cyan
    Install-WinGetApp -ID "Microsoft.PowerShell"        -Categoria "Terminal"
    Install-WinGetApp -ID "Microsoft.WindowsTerminal"   -Categoria "Terminal"
    Install-WinGetApp -ID "7zip.7zip"                   -Categoria "Utilidades"
    Install-WinGetApp -ID "Mozilla.Firefox"             -Categoria "Navegador"
    Install-WinGetApp -ID "Foxit.FoxitReader"           -Categoria "Documentos"
    Install-WinGetApp -ID "Google.Chrome"               -Categoria "Navegador"
    Install-WinGetApp -ID "TheDocumentFoundation.LibreOffice.LTS" -Categoria "Documentos"
    Install-WinGetApp -ID "Skillbrains.Lightshot"       -Categoria "Utilidades"
    Install-WinGetApp -ID "RustDesk.RustDesk"           -Categoria "Remoto"
    Install-WinGetApp -ID "VideoLAN.VLC"                -Categoria "Multimidia"
} else {
    Write-Host "`n⏭️  [6/7] Instalacao de aplicativos pulada (-SkipApps)." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------
# Etapa 7 — Runtimes essenciais (.NET + Visual C++ Redistributable)
# ---------------------------------------------------------------
if (-not $SkipRuntimes) {
    Write-Host "`n⚙️  [7/7] Instalando runtimes essenciais..." -ForegroundColor Cyan
    Install-WinGetApp -ID "Microsoft.DotNet.Framework.DeveloperPack_4"    -Categoria "Runtime .NET"
    Install-WinGetApp -ID "Microsoft.DotNet.Framework.DeveloperPack.4.5"  -Categoria "Runtime .NET"
    Install-WinGetApp -ID "Microsoft.DotNet.Runtime.5"                    -Categoria "Runtime .NET"
    Install-WinGetApp -ID "Microsoft.DotNet.Runtime.6"                    -Categoria "Runtime .NET"
    Install-WinGetApp -ID "Microsoft.DotNet.Runtime.7"                    -Categoria "Runtime .NET"
    Install-WinGetApp -ID "Microsoft.DotNet.Runtime.8"                    -Categoria "Runtime .NET"
    Install-WinGetApp -ID "Microsoft.VCRedist.2005.x86"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2005.x64"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2008.x86"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2008.x64"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2010.x86"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2010.x64"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2012.x86"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2012.x64"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2013.x86"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2013.x64"                   -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2015+.x86"                  -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Microsoft.VCRedist.2015+.x64"                  -Categoria "VC++ Redist"
    Install-WinGetApp -ID "Oracle.JavaRuntimeEnvironment"                 -Categoria "Java"
} else {
    Write-Host "`n⏭️  [7/7] Instalacao de runtimes pulada (-SkipRuntimes)." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------
# Resumo final
# ---------------------------------------------------------------
Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "📊 Resumo da Pos-instalacao" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
if ($Erros.Count -eq 0) {
    Write-Host "✅ Todas as etapas concluidas sem erros!" -ForegroundColor Green
} else {
    Write-Host "⚠️  $($Erros.Count) falha(s) identificada(s):" -ForegroundColor Yellow
    $Erros | ForEach-Object { Write-Host "  ✖ $_" -ForegroundColor Red }
    Write-Host "`n💡 Dica: rode 'winget upgrade --all' apos o processo para atualizar tudo." -ForegroundColor DarkGray
}
Write-Host "`n🔄 Reinicie o Windows para aplicar todas as alteracoes de visual." -ForegroundColor DarkGray
