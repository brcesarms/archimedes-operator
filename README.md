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
│   │   ├── inventario.ps1        <-- Inventário JSON (Etapa 1)
│   │   └── backup-robocopy.ps1   <-- Backup por usuário (Etapa 2)
│   └── python/
│       └── orquestrador.py       <-- Orquestrador completo (SFTP + JSON + manifesto)
├── templates/
│   └── MANIFESTO_TEMPLATE.md     <-- Modelo do manifesto Obsidian (Etapa 3)
├── manifests/                    <-- Manifestos REAIS (ignorados pelo Git 🛡️)
├── README.md
└── .gitignore
```

## 🔧 Requisitos

- Python 3 + `paramiko`
- GitHub CLI (`gh`) — opcional, para automações do repositório
- Máquina alvo Windows com **OpenSSH Server** habilitado (guia acima)
- Chave SSH `ed25519` configurada na máquina alvo

## ⚡ Uso Rápido

```bash
python3 scripts/python/orquestrador.py \
  --host 192.168.1.50 \
  --usuario bruno \
  --chave ~/.ssh/id_ed25519 \
  --cliente TECNOSOFT \
  --destino '\\storage-central\Bancada\TECNOSOFT'
```

> 📖 Detalhes completos em [docs/instrucoes.md](./docs/instrucoes.md)

## 🛡️ Segurança

- ⚠️ **Repositório PÚBLICO** — **NUNCA** commitar manifestos reais (contêm chaves OEM e dados de clientes). Somente o template em `templates/` é versionado.
- Credenciais, chaves e `.env` são ignorados pelo `.gitignore`.
- Conexões SSH apenas para máquinas documentadas.

---

## 🔗 Fontes

- [Robocopy — Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)
- [OpenSSH Server no Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- [Paramiko](https://www.paramiko.org/)