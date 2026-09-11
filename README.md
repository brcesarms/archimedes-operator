# 🏗️ Projeto Bancada

> Triagem, inventário técnico e backup forense pré-formatação de máquinas Windows via SSH.

Automação executada via **OpenCode CLI** para o fluxo de bancada do T.I. — coleta inventário (usuários, chave OEM, softwares), faz backup com `robocopy` e gera manifestos em Markdown para o Obsidian.

---

## 🪟 Preparando uma máquina Windows 11

> **Está na máquina Windows e quer habilitar o acesso SSH?** Siga o guia:
>
> 📖 **[Passo a passo — Preparar Máquina Windows 11](./docs/preparar-maquina-windows.md)**
>
> 💡 Baixe direto o script: [`setup-ssh-pri.ps1`](./scripts/powershell/setup-ssh-pri.ps1)

### 🧪 Ambiente testado: VM Windows 11 no Proxmox

✅ **[2026-09-11]** SSH configurado e testado com sucesso numa **VM Windows 11** (VMID 101) no Proxmox do GEEKOM (host `10.0.0.3`, IP da VM `10.0.0.217`).

**Resumo da solução de problema (vitória registrada):**
- O serviço `sshd` estava ativo e a porta **LISTENING**, mas a rede era **`Public`** e a regra `OpenSSH-Server-In-TCP` **faltava** no firewall do Windows → bloqueio de entrada.
- Correção (via guest agent do Proxmox):
  ```
  netsh advfirewall firewall add rule name="OpenSSH-Server-In-TCP" dir=in action=allow protocol=TCP localport=22
  ```
- Conexão `ssh brces@10.0.0.217` funcionou imediatamente. 🎉

> 📖 [Detalhes completos do diagnóstico](./docs/instrucoes.md) (seção "Caso Real")

---

## 🚀 Comandos rápidos — copiar e colar na máquina Windows

> **Passo 1** — No **Windows PowerShell** (pode ser janela normal), baixe o script:

```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/brcesarms/projeto-bancada/main/scripts/powershell/setup-ssh-pri.ps1" -OutFile "$env:USERPROFILE\Downloads\setup-ssh-pri.ps1"
```

> **Passo 2** — Abra o **Windows PowerShell como Administrador** (botão direito → Executar como administrador) e cole os 3 comandos abaixo:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
cd $env:USERPROFILE\Downloads
.\setup-ssh-pri.ps1
```

> **Passo 3** — No final, o script mostra o **👤 usuário** e o **🌐 IP** da máquina. Anote e envie para o Bruno seguir com o backup. ✅

```powershell
# (Opcional) Verificar se o serviço ficou ativo:
Get-Service sshd
```

> ⚠️ **Já tem o arquivo baixado e deu erro `Token '}' inesperado`?** A codificação está errada. Baixe de novo com o comando do Passo 1 e execute o Passo 2.

---

## 📁 Estrutura do Repositório

```text
projeto-bancada/
├── docs/
│   ├── instrucoes.md             <-- Documento técnico completo (refatorado)
│   └── preparar-maquina-windows.md <-- 🪟 Guia passo a passo (Windows 11)
├── scripts/
│   ├── powershell/
│   │   ├── setup-ssh-pri.ps1     <-- Configura OpenSSH Server (rodar na máq. Windows)
│   │   ├── pos-instalacao.ps1    <-- 🪟 Pós-instalação: ajustes + apps + runtimes (rodar 1ª vez)
│   │   ├── inventario.ps1        <-- Inventário JSON (Etapa 1)
│   │   ├── backup-robocopy.ps1   <-- Backup por usuário (Etapa 2)
│   │   └── Win11Debloat.ps1      <-- 🧹 Remove bloatware/telemetria (pós-formatação, opcional)
│   └── python/
│       └── orquestrador.py       <-- Orquestrador completo (SFTP + JSON + manifesto)
├── templates/
│   └── MANIFESTO_TEMPLATE.md     <-- Modelo do manifesto Obsidian (Etapa 3)
├── tests/
│   └── test_orquestrador.py      <-- 🧪 Testes das funções puras (pytest)
├── manifests/                    <-- Manifestos REAIS (ignorados pelo Git 🛡️)
├── requirements.txt              <-- Dependências de runtime (paramiko)
├── requirements-dev.txt          <-- Dependências de testes (pytest)
├── README.md
└── .gitignore
```

## 🔧 Requisitos

- Python 3.10+
- Máquina alvo Windows com **OpenSSH Server** habilitado (guia acima)
- Chave SSH `ed25519` configurada na máquina alvo

## 🛠️ Setup do ambiente (Linux)

```bash
cd ~/projetos/projeto-bancada
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt        # runtime (paramiko)
# pip install -r requirements-dev.txt  # + testes (pytest)
```

> 💡 Em máquina nova: basta repetir os comandos acima — os `requirements.txt` garantem um ambiente idêntico, sem depender do Python do sistema.

## 🧪 Testes

```bash
source .venv/bin/activate
pytest tests/ -v
```

## ⚡ Uso Rápido

```bash
python3 scripts/python/orquestrador.py \
  --host 192.168.1.50 \
  --usuario bruno \
  --chave ~/.ssh/id_ed25519 \
  --cliente TECNOSOFT \
  --destino '\\storage-central\Bancada\TECNOSOFT'
```

## 🍽️ Menu Interativo (Painel de Operações)

Para operar de forma guiada com a tela inicial explicativa:

```bash
python3 scripts/python/menu.py
```

> 📖 Detalhes completos em [docs/instrucoes.md](./docs/instrucoes.md)

## 🧹 Desbloat Windows 11 (pós-formatação, opcional)

Após reinstalar o Windows, use o **Win11Debloat** para remover bloatware, telemetria e ajustar a privacidade:

```powershell
# Na máquina Windows (PowerShell 5.1 como Administrador):
.\scripts\powershell\Win11Debloat.ps1 -RunDefaultsLite -Silent
```

> ⚠️ **Requisitos:** Windows PowerShell 5.1 (não o 7/pwsh) + **Administrador** + **Ponto de Restauração** recomendado.
> 📖 Opções completas em [docs/instrucoes.md](./docs/instrucoes.md) (seção Desbloat).
> 🔗 Projeto original: [Raphire/Win11Debloat](https://github.com/Raphire/Win11Debloat) (MIT).

## 🪟 Pós-instalação (ajustes + softwares essenciais)

Para máquinas novas / recém-formatadas, rode o **pos-instalacao.ps1** — aplica ajustes de sistema (energia, tema escuro, privacidade) e instala apps + runtimes via winget:

```powershell
# Na máquina Windows (PowerShell 5.1 como Administrador):
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\scripts\powershell\pos-instalacao.ps1
```

| Etapa | O que faz |
| :--- | :--- |
| 1 | Libera ExecutionPolicy (Unrestricted) |
| 2 | Desativa energia: vídeo, standby e hibernação (AC/DC) |
| 3 | Ativa tema escuro (apps + sistema) |
| 4 | Desativa Histórico de Atividades |
| 5 | Desativa aplicativos em segundo plano |
| 6 | Instala 10 apps essenciais (Terminal, Firefox, Chrome, 7-Zip, VLC...) |
| 7 | Instala 19 runtimes (.NET Framework + .NET 5-8 + VC++ 2005-2015+ + Java) |

> ⚙️ Pode pular partes com `-SkipApps` ou `-SkipRuntimes`.
> 📖 Detalhes completos em [docs/instrucoes.md](./docs/instrucoes.md) (seção Pós-instalação).

## 🛡️ Segurança

- ⚠️ **Repositório PÚBLICO** — **NUNCA** commitar manifestos reais (contêm chaves OEM e dados de clientes). Somente o template em `templates/` é versionado.
- Credenciais, chaves e `.env` são ignorados pelo `.gitignore`.
- Conexões SSH apenas para máquinas documentadas.

---

## 🔗 Fontes

- [Robocopy — Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)
- [OpenSSH Server no Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- [Paramiko](https://www.paramiko.org/)
- [Win11Debloat — Raphire (GitHub)](https://github.com/Raphire/Win11Debloat) — licença MIT