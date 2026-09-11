# inventario.ps1 — Coleta inventário técnico da máquina (retorna JSON)
# Etapa 1 do Projeto Bancada.
# Uso remoto: powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File inventario.ps1

$res = [ordered]@{
    hostname   = $env:COMPUTERNAME
    usuario    = $env:USERNAME
    windows    = (Get-CimInstance Win32_OperatingSystem).Caption
    versao     = (Get-CimInstance Win32_OperatingSystem).Version
    chave_oem  = (Get-CimInstance -Query 'select * from SoftwareLicensingService').OA3xOriginalProductKey
    usuarios   = @(
        Get-ChildItem C:\Users -Directory |
            Where-Object { $_.Name -notin @('Public','Default','Default User','All Users') } |
            Select-Object -ExpandProperty Name
    )
    softwares  = @(
        Get-ItemProperty @(
            'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
        ) -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName } |
            Sort-Object DisplayName |
            Select-Object @{n='nome';e={$_.DisplayName}}, @{n='versao';e={$_.DisplayVersion}}, @{n='fabricante';e={$_.Publisher}}
    )
}

$res | ConvertTo-Json -Depth 3