#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Configura o OpenSSH Server no Windows e autoriza a chave SSH do Bruno.
.DESCRIPTION
    1. Instala o recurso OpenSSH.Server no Windows (se não estiver instalado).
    2. Inicia o serviço sshd e define como inicialização automática.
    3. Cria a regra de firewall para a porta 22 (TCP).
    4. Configura a chave pública do Bruno tanto para usuários comuns (~/.ssh/authorized_keys)
       quanto para administradores (__PROGRAMDATA__/ssh/administrators_authorized_keys).
    5. Exibe o IP da máquina para conexão SSH.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "🏛️ Archimedes — Setup do OpenSSH Server (Windows)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Instalar OpenSSH Server
Write-Host "`n🚀 [1/4] Verificando instalacao do OpenSSH Server..." -ForegroundColor Cyan
$sshCap = Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH.Server*'
if ($sshCap.State -ne 'Installed') {
    Write-Host "📦 Instalando OpenSSH.Server (pode levar alguns instantes)..." -ForegroundColor Yellow
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
    Write-Host "✔ OpenSSH Server instalado com sucesso!" -ForegroundColor Green
} else {
    Write-Host "✔ OpenSSH Server ja esta instalado!" -ForegroundColor Green
}

# 2. Iniciar e habilitar o servico sshd
Write-Host "`n⚡ [2/4] Configurando servico sshd..." -ForegroundColor Cyan
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
Write-Host "✔ Servico sshd em execucao e configurado para inicializacao automatica!" -ForegroundColor Green

# 3. Regra de Firewall
Write-Host "`n🛡️ [3/4] Verificando regra de Firewall..." -ForegroundColor Cyan
$regraExiste = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if (-not $regraExiste) {
    # Cria a regra cobrindo TODOS os perfis (inclusive Publico — onde o Windows bloqueia tudo por padrao)
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -Profile Any | Out-Null
    Write-Host "✔ Regra de Firewall criada para a porta 22 (todos os perfis)!" -ForegroundColor Green
} else {
    Write-Host "✔ Regra de Firewall para porta 22 ja existe!" -ForegroundColor Green
}

# Validacao extra: confirmar que o firewall realmente permite (fallback netsh se o cmdlet falhar silenciosamente)
$validaRegra = netsh advfirewall firewall show rule name="OpenSSH-Server-In-TCP" 2>$null
if ($validaRegra -notmatch "OpenSSH-Server-In-TCP") {
    Write-Host "⚠️ Regra nao detectada via netsh — criando com fallback..." -ForegroundColor Yellow
    netsh advfirewall firewall add rule name="OpenSSH-Server-In-TCP" dir=in action=allow protocol=TCP localport=22 | Out-Null
    Write-Host "✔ Regra criada com fallback netsh!" -ForegroundColor Green
} else {
    Write-Host "✔ Validacao netsh: regra em vigor!" -ForegroundColor Green
}

# 4. Autorizar chave SSH do Bruno
Write-Host "`n🔑 [4/4] Autorizando chave SSH publica do Bruno..." -ForegroundColor Cyan
$brunoPubkey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILiS0LKTWLy0WVbY7O515TKpR9yxxDrJjXH0c3zcWELZ brcesarms@gmail.com"

# Perfil do usuario atual
$userSshDir = "$env:USERPROFILE\.ssh"
if (-not (Test-Path $userSshDir)) {
    New-Item -ItemType Directory -Path $userSshDir -Force | Out-Null
}
$userAuthKeys = "$userSshDir\authorized_keys"
if (-not (Test-Path $userAuthKeys) -or -not (Get-Content $userAuthKeys -ErrorAction SilentlyContinue | Select-String -SimpleMatch $brunoPubkey)) {
    Add-Content -Path $userAuthKeys -Value $brunoPubkey
    Write-Host "✔ Chave adicionada ao authorized_keys do usuario ($env:USERNAME)!" -ForegroundColor Green
} else {
    Write-Host "✔ Chave ja cadastrada no perfil do usuario ($env:USERNAME)!" -ForegroundColor Green
}

# Perfil de Administradores (padrao do OpenSSH no Windows)
$adminKeysPath = "$env:ProgramData\ssh\administrators_authorized_keys"
if (Test-Path "$env:ProgramData\ssh") {
    if (-not (Test-Path $adminKeysPath) -or -not (Get-Content $adminKeysPath -ErrorAction SilentlyContinue | Select-String -SimpleMatch $brunoPubkey)) {
        Add-Content -Path $adminKeysPath -Value $brunoPubkey
        # Ajustar permissoes estritas necessarias pelo OpenSSH no Windows
        icacls.exe $adminKeysPath /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F" | Out-Null
        Write-Host "✔ Chave adicionada ao administrators_authorized_keys!" -ForegroundColor Green
    } else {
        Write-Host "✔ Chave ja cadastrada em administrators_authorized_keys!" -ForegroundColor Green
    }
}

# 5. Resumo e IP
$ips = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { 
    $_.InterfaceAlias -notlike "*Loopback*" -and 
    $_.InterfaceAlias -notlike "*vEthernet*" -and 
    $_.IPAddress -notlike "169.254*" 
}).IPAddress

# 6. Teste local: confirmar que a porta 22 esta aceitando conexao
Write-Host "`n🔬 [5/5] Teste local da porta 22..." -ForegroundColor Cyan
$testePorta = Test-NetConnection -ComputerName "127.0.0.1" -Port 22 -WarningAction SilentlyContinue
if ($testePorta.TcpTestSucceeded) {
    Write-Host "✔ Porta 22 aceitando conexao localmente! SSH pronto!" -ForegroundColor Green
} else {
    Write-Host "⚠️ Porta 22 nao respondeu localmente — verifique firewall/servico." -ForegroundColor Yellow
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "🎉 Tudo pronto! SSH ativo e configurado com sucesso! ✅" -ForegroundColor Green
Write-Host "👤 Usuario Windows: $env:USERNAME" -ForegroundColor Yellow
Write-Host "🌐 IP(s) encontrados nesta maquina:" -ForegroundColor Cyan
foreach ($ip in $ips) {
    Write-Host "   👉 $ip" -ForegroundColor Yellow
}
Write-Host "`n💻 Bruno, para conectar use:" -ForegroundColor Cyan
if ($ips.Count -gt 0) {
    Write-Host "   ssh $env:USERNAME@$($ips[0])" -ForegroundColor Green
} else {
    Write-Host "   ssh $env:USERNAME@<IP_DO_NOTEBOOK>" -ForegroundColor Green
}
Write-Host "========================================================" -ForegroundColor Cyan
