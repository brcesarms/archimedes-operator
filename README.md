# 🏗️ Projeto Bancada

> Triagem, inventário técnico e backup forense pré-formatação de máquinas Windows via SSH.

Automação executada via **OpenCode CLI** para o fluxo de bancada do T.I. — coleta inventário (usuários, chave OEM, softwares), faz backup com `robocopy` e gera manifestos em Markdown para o Obsidian.

---

## 📁 Estrutura do Repositório

```text
projeto-bancada/
├── docs/
│   └── instrucoes.md          <-- Documento técnico completo (refatorado)
├── scripts/
│   ├── powershell/
│   │   ├── inventario.ps1     <-- Inventário JSON (Etapa 1)
│   │   └── backup-robocopy.ps1 <-- Backup por usuário (Etapa 2)
│   └── python/
│       └── orquestrador.py    <-- Orquestrador completo (SFTP + JSON + manifesto)
├── templates/
│   └── MANIFESTO_TEMPLATE.md  <-- Modelo do manifesto Obsidian (Etapa 3)
├── manifests/                 <-- Manifestos REAIS (ignorados pelo Git 🛡️)
├── README.md
└── .gitignore
```

## 🔧 Requisitos

- Python 3 + `paramiko`
- GitHub CLI (`gh`) — opcional, para automações do repositório
- Máquina alvo Windows com **OpenSSH Server** habilitado
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