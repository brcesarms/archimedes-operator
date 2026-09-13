# 👷‍♂️ Archimedes Operator

> Braço Mecânico de Automação Remota SSH/SFTP, Bancada e Backup de Máquinas Windows.

Automação completa e **100% autossuficiente** de bancada do T.I. — integra nativamente coleta de inventário (usuários, chave OEM, softwares), motor de backup forense (Robocopy com suporte a OneDrive), suíte de pós-instalação e debloat do Windows 11, e geração automática de manifestos Markdown para o Obsidian. Não requer nenhuma dependência de repositórios externos.

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
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/brcesarms/archimedes-operator/main/scripts/powershell/setup-ssh-pri.ps1" -OutFile "$env:USERPROFILE\Downloads\setup-ssh-pri.ps1"
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
archimedes-orquestrador/
├── docs/
│   ├── instrucoes.md             <-- Documento técnico completo (refatorado)
│   └── preparar-maquina-windows.md <-- 🪟 Guia passo a passo (Windows 11)
├── scripts/
│   ├── powershell/
│   │   ├── setup-ssh-pri.ps1     <-- Configura OpenSSH Server (rodar na máq. Windows)
│   │   └── inventario.ps1        <-- Inventário JSON (Etapa 1)
│   └── python/
│       └── orquestrador.py       <-- Orquestrador (SFTP + JSON + manifesto; backup e pós-instalação via módulos externos)
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
cd ~/projetos/archimedes-orquestrador
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

## 💾 Backup — módulo separado

O backup (Windows por usuário com `robocopy` **e** Linux com `rsync`) vive no repositório dedicado:

> 🔗 **[brcesarms/archimedes-backup](https://github.com/brcesarms/archimedes-backup)**

O orquestrador deste projeto referencia o `backup-robocopy.ps1` por caminho absoluto (`~/projetos/archimedes-backup/windows/`), mantendo o fluxo da Etapa 2 da bancada **sem duplicar código**.

## 🪟 Pós-instalação e Desbloat — módulo separado

Os scripts de **pós-instalação** (ajustes + apps + runtimes) e **desbloat Windows 11** vivem no repositório dedicado:

> 🔗 **[brcesarms/archimedes-win11-setup](https://github.com/brcesarms/archimedes-win11-setup)**

O orquestrador deste projeto referencia o `pos-instalacao.ps1` e o `Win11Debloat.zip` por caminho absoluto (`~/projetos/archimedes-win11-setup/windows/`), suportando as flags `--pos` e `--debloat` **sem duplicar código**.

## 🍽️ Menu Interativo (Painel de Operações)

Para operar de forma guiada com a tela inicial explicativa:

```bash
python3 scripts/python/menu.py
```

> 📖 Detalhes completos em [docs/instrucoes.md](./docs/instrucoes.md)

## 🧹 Desbloat e 🪟 Pós-instalação — rodar direto do módulo

Após reinstalar o Windows, use os scripts do repositório dedicado **`archimedes-win11-setup`**
(README e manual lá). Resumo rápido:

```powershell
# Desbloat (PowerShell 5.1 como Admin):
.\windows\Win11Debloat.ps1 -RunDefaultsLite -Silent

# Pós-instalação (ajustes + 10 apps + 19 runtimes via winget):
.\windows\pos-instalacao.ps1
```

> ⚠️ **Removidos deste repo em 2026-09-12:** `pos-instalacao.ps1`, `Win11Debloat.ps1`,
> `Win11Debloat.zip` e `Win11Debloat/` agora vivem em
> [brcesarms/archimedes-win11-setup](https://github.com/brcesarms/archimedes-win11-setup).
> O orquestrador referencia por caminho absoluto — sem duplicação.
> 📖 Opções completas em `docs/instrucoes.md` do novo módulo.

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