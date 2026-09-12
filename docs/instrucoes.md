# 🏗️ Projeto Bancada — Instruções de Sistema (Refatorado)

> **Versão:** 2.0 · **Status:** Ativo · **Atualizado:** 2026-09-11
>
> Assistente de automação via **OpenCode CLI** para triagem, inventário técnico e backup forense pré-formatação de máquinas Windows conectadas à rede da bancada via SSH.

---

## 📖 Sumário

1. [Visão Geral e Arquitetura](#-visão-geral-e-arquitetura)
2. [Conexão e Comunicação SSH](#-conexão-e-comunicação-ssh)
3. [Etapa 1 — Coleta de Inventário](#-etapa-1--coleta-de-inventário)
4. [Etapa 2 — Backup com Robocopy (módulo externo)](#-etapa-2--backup-com-robocopy-módulo-externo)
5. [Etapa 3 — Geração do Manifesto](#-etapa-3--geração-do-manifesto)
6. [Etapa 4 — Desbloat e Etapa 5 — Pós-instalação (módulo externo)](#-etapa-4--desbloat-windows-11-e--etapa-5--pós-instalação-módulo-externo)
7. [Orquestração em Python](#-orquestração-em-python)
8. [Menu Interativo](#-menu-interativo)
9. [Tratamento de Erros e Validação](#-tratamento-de-erros-e-validação)
10. [Segurança e Boas Práticas](#-segurança-e-boas-práticas)
11. [Fluxo de Execução Completo](#-fluxo-de-execução-completo)
12. [🔗 Fontes](#-fontes)

---

## 🎯 Visão Geral e Arquitetura

### Objetivo
Executar de forma **automatizada e não-interativa** o processo de:
1. **Triagem** — identificar quem usa a máquina (perfis em `C:\Users`).
2. **Inventário técnico** — extrair chave OEM da BIOS e mapear softwares instalados.
3. **Backup forense** — copiar dados do usuário (Desktop, Documents, Downloads, Pictures) para o storage central com `robocopy`.
4. **Manifesto** — gerar relatório em Markdown para registro e checklist de reinstalação.

### Arquitetura dos Componentes

```text
+---------------------+        SSH (paramiko)        +-----------------------+
|  Orquestrador       |  ------------------------>  |  Máquina Alvo Windows |
|  (Python local)     |  <------------------------  |  PowerShell remoto    |
+---------------------+        JSON / stdout        +-----------------------+
        |
        | robocopy (via recursos administrativos / net share)
        v
+---------------------+
|  Storage Central    |
|  (caminho \\NAS\...)|
+---------------------+
        |
        | gera manifesto
        v
+---------------------+
|  Obsidian / Vault   |
+---------------------+
```

### Fluxo de Trabalho (Visão Geral)

| Etapa | Ação | Saída |
| :--- | :--- | :--- |
| `1` | Coleta de Inventário | JSON estruturado (usuários, chave OEM, softwares) |
| `2` | Backup Robocopy | Logs de cópia + exit code |
| `3` | Manifesto Obsidian/Markdown | `MANIFESTO_<CLIENTE>_<DATA>.md` em `manifests/` |

---

## 🔌 Conexão e Comunicação SSH

### Mecanismo
- Conectar à máquina alvo via SSH usando **client Python `paramiko`** ou cliente nativo OpenSSH.
- O Windows 10/11 moderno já inclui o **OpenSSH Server** opcional; verifique/instale na máquina alvo (via GUI: *Configurações → Aplicativos → Recursos Opcionais → OpenSSH Server*).

### 🧪 Caso Real (2026-09-11) — VM Windows 11 no Proxmox

> **Contexto:** a máquina alvo era uma **VM Windows 11** (VMID 101) rodando no Proxmox do GEEKOM (host `10.0.0.3`). O script `setup-ssh-pri.ps1` rodou e o serviço `sshd` estava **RUNNING**, mas a porta 22 **não respondia de nenhum lugar** (nem do próprio host Proxmox).

**Sintomas observados:**
- `ping` na VM → falha (ICMP bloqueado, normal)
- Portas 22, 445, 3389 → todas filtradas
- MAC da VM = prefixo `BC:24:11` (Proxmox) → confirmou que era VM
- `qm guest exec` inicialmente falhou (`QEMU guest agent is not running`)

**🔬 Diagnóstico remoto (via host Proxmox + guest agent):**
```bash
# No host Proxmox — testar porta direto pela bridge (elimina roteamento)
timeout 4 bash -c 'cat < /dev/null > /dev/tcp/10.0.0.217/22'

# Quando o QEMU Guest Agent estiver ativo (após instalar guest tools na VM):
qm guest exec 101 -- cmd /c "sc query sshd"                # serviço
qm guest exec 101 -- cmd /c "netstat -an | findstr :22"    # porta
qm guest exec 101 -- powershell -Command "Get-NetConnectionProfile | Select Name, NetworkCategory"
```

**🎯 Causa raiz (3 camadas — diagnóstico em cascata):**
1. **Firewall do Proxmox:** estava **DESABILITADO** (`Status: disabled/running`, sem `/etc/pve/firewall/cluster.fw`) → **não era o bloqueio** (a interface tinha `firewall=1`, mas sem config global não filtra).
2. **Serviço `sshd`:** **RUNNING** e porta **LISTENING** (`0.0.0.0:22`) → não era problema.
3. **Firewall do Windows:** 🔥 **O VILÃO** — o perfil de rede era **`Public`** e a regra `OpenSSH-Server-In-TCP` **NÃO EXISTIA** no Windows Firewall (o `New-NetFirewallRule` do script não tinha criado/validado). Com perfil **Público**, o Windows **bloqueia toda entrada** sem regra explícita.

**✅ Correção aplicada (criar a regra no Windows via guest agent):**
```bash
# No host Proxmox (com guest agent ativo):
qm guest exec 101 -- netsh advfirewall firewall add rule name="OpenSSH-Server-In-TCP" dir=in action=allow protocol=TCP localport=22
```
Após isso, a conexão `ssh brces@10.0.0.217` **funcionou imediatamente**.

**💡 Lições documentadas para o projeto:**
- O script `setup-ssh-pri.ps1` foi **aprimorado** com: `-Profile Any` explícito na regra + **validação via `netsh`** + fallback (`netsh advfirewall firewall add rule`) + **teste local da porta 22** (`Test-NetConnection 127.0.0.1`).
- **Instale o QEMU Guest Agent em VMs Windows** (ISO `virtio-win` → `virtio-win-guest-tools.exe`) — permite diagnóstico/inventário via `qm guest exec` sem depender de SSH/console.
- Em notebook físico, o diagnóstico é o mesmo: verificar **perfil de rede** (`Get-NetConnectionProfile`), **regra no firewall do Windows** (`netsh advfirewall firewall show rule name="OpenSSH-Server-In-TCP"`) e **serviço** (`sc query sshd`).

### Autenticação
**Padrão recomendado (chave pública):**
```bash
# Gerar chave ed25519 (uma vez, no host orquestrador)
ssh-keygen -t ed25519 -C "bancada@$(hostname)" -f ~/.ssh/id_ed25519

# Copiar para a máquina Windows (via senha, no primeiro acesso)
# O comando abaixo funciona se o Windows tiver ssh-copy-id equivalente:
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh usuário@host "powershell -Command \"Add-Content -Path \$env:ProgramData\ssh\administrators_authorized_keys -Value (Get-Content)\""
```

> ⚠️ **Atenção:** O acesso SSH no Windows **NÃO aceita o PIN do Windows Hello**; é necessária a **senha real do usuário** ou conta local.
>
> 🔒 Em máquinas de bancada, prefira **conta local** com senha forte e chave SSH autorizada — evita dependência de domínio/AD durante formatação.

### Shell Remoto
Toda execução remota DEVE passar pelo **PowerShell**:
```bash
# Exemplo: verificar versão do Windows
ssh usuario@host "powershell.exe -NoProfile -NonInteractive -Command \"(Get-CimInstance Win32_OperatingSystem).Caption\""
```

> ⚠️ **Atenção:** Nem sempre é necessário prefixar `powershell.exe` — o `sshd` do Windows já usa PowerShell quando o shell padrão está configurado. Para garantir, use o prefixo explícito.

### Parâmetros padronizados da sessão remota
```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "<comando>"
```

| Flag | Motivo |
| :--- | :--- |
| `-NoProfile` | Evita carregar profile do usuário (perfis podem conter scripts quebrando a automação) |
| `-NonInteractive` | Impede prompts bloqueantes (essencial para automação headless) |
| `-ExecutionPolicy Bypass` | Permite executar scripts `.ps1` sem policy bloqueando |

---

## 🔍 Etapa 1 — Coleta de Inventário

### 1.1 Mapeamento de Usuários

Listar perfis em `C:\Users`, ignorando perfis de sistema:

```powershell
Get-ChildItem C:\Users -Directory |
    Where-Object { $_.Name -notin @('Public','Default','Default User','All Users') } |
    Select-Object -ExpandProperty Name
```

**Saída esperada (stdout, linha por linha):**
```
bruno
paula
```

### 1.2 Leitura da Chave de Licença (BIOS/OEM)

```powershell
(Get-CimInstance -Query 'select * from SoftwareLicensingService').OA3xOriginalProductKey
```

> 🎯 **Dica:** Se o retorno for vazio, a máquina pode ter sido instalada com Volume License ou chave genérica (não OEM). Na bancada de formatação, isso significa:
> - Coletar chave do rótulo COA físico (se houver), ou
> - Marcar no manifesto: `chave_bioss: N/A (Volume/Reinstalação)`.

### 1.3 Softwares Instalados

Mapear softwares do registro do Windows:

```powershell
$paths = @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
Get-ItemProperty $paths -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName } |
    Sort-Object DisplayName |
    Select-Object DisplayName, DisplayVersion, Publisher |
    Format-Table -AutoSize
```

> 📌 **Por que 3 caminhos de registro?**
> - `HKLM ... Uninstall` — apps de 64 bits instalados para todos os usuários.
> - `HKLM ... WOW6432Node ... Uninstall` — apps de 32 bits rodando em Windows 64 bits.
> - `HKCU ... Uninstall` — apps instalados apenas pelo usuário atual (Microsoft Store e afins).

### 1.4 Inventário Combinado em JSON (para parse fácil)

```powershell
$res = [ordered]@{
    hostname   = $env:COMPUTERNAME
    usuario    = $env:USERNAME
    windows    = (Get-CimInstance Win32_OperatingSystem).Caption
    versao     = (Get-CimInstance Win32_OperatingSystem).Version
    chave_oem  = (Get-CimInstance -Query 'select * from SoftwareLicensingService').OA3xOriginalProductKey
    usuarios   = @(Get-ChildItem C:\Users -Directory | Where-Object { $_.Name -notin @('Public','Default','Default User','All Users') } | Select-Object -ExpandProperty Name)
    softwares  = @(
        Get-ItemProperty @('HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*') -ErrorAction SilentlyContinue |
            Where-Object { $_.DisplayName } |
            Sort-Object DisplayName |
            Select-Object @{n='nome';e={$_.DisplayName}}, @{n='versao';e={$_.DisplayVersion}}, @{n='fabricante';e={$_.Publisher}}
    )
}
$res | ConvertTo-Json -Depth 3
```

> ✅ **Boa Prática:** Encapsular todo o inventário em **um único bloco PowerShell** que retorna JSON — o orquestrador Python faz `json.loads(saida)` uma única vez, sem múltiplas idas e vindas de parse.

---

## 📦 Etapa 2 — Backup com Robocopy (módulo externo)

> 💾 **Migrado:** o script `backup-robocopy.ps1` vive no repositório dedicado
> [`brcesarms/archimedes-backup`](https://github.com/brcesarms/archimedes-backup) (`windows/`).
> O orquestrador o referencia por caminho absoluto
> (`~/projetos/archimedes-backup/windows/backup-robocopy.ps1`) — sem duplicar código.
>
> 📖 **Manual completo** (parâmetros, diretórios, destino, exit codes):
> [`archimedes-backup/docs/instrucoes.md`](https://github.com/brcesarms/archimedes-backup) e
> [`docs/preparar-maquina-alvo.md`](https://github.com/brcesarms/archimedes-backup).
>
> ⚠️ Regra essencial: exit code do robocopy `>= 8` = **falha de backup** — reportar no manifesto.

---

## 📝 Etapa 3 — Geração do Manifesto

### Convenção de nomenclatura
```
MANIFESTO_<CLIENTE>_<DATA>.md
```
Exemplo: `MANIFESTO_TECNOSOFT_2026-09-11.md`

### Localização dos Manifestos
- O script e seus arquivos de saída pertencem à **gestão de infraestrutura técnica**.
- O orquestrador gera os manifestos em **`manifests/`** na raiz do projeto (ver [Template do Manifesto](../templates/MANIFESTO_TEMPLATE.md)).
- ⚠️ `manifests/` é **ignorado pelo Git** (`.gitignore`) — manifestos reais contêm chaves OEM e dados de clientes e **nunca** devem ser commitados no repositório público.
- Para alterar o destino, use o flag `--saida` do orquestrador (ex: apontar para uma pasta local do vault, se desejado).

### Estrutura do Manifesto (`templates/MANIFESTO_TEMPLATE.md`)
1. **Cabeçalho** — cliente, data, técnico, hostname.
2. **Inventário** — Windows, versão, chave OEM, usuários.
3. **Status de cópia** — tabela por pasta (copiada ⚠️ pendente / ❌ erro).
4. **Checklist de reinstalação** — softwares detectados, com checkboxes.
5. **Observações** — pendências, arquivos não copiados, peculiaridades.

---

## 🧹 Etapa 4 — Desbloat Windows 11 e 🪟 Etapa 5 — Pós-instalação (módulo externo)

> 🔄 **Migrado em 2026-09-12** para o repositório dedicado
> [brcesarms/archimedes-win11-setup](https://github.com/brcesarms/archimedes-win11-setup).

Os scripts `pos-instalacao.ps1`, `Win11Debloat.ps1`, `Win11Debloat.zip` e `Win11Debloat/`
**saíram** de `scripts/powershell/` e agora vivem em
`~/projetos/archimedes-win11-setup/windows/` — o orquestrador referencia por
**caminho absoluto**, sem duplicar código (mesmo padrão do `backup-robocopy.ps1`).

> 📖 **Manual completo** (requisitos, flags, modos de uso, tabela de apps/runtimes):
> [`archimedes-win11-setup/docs/instrucoes.md`](https://github.com/brcesarms/archimedes-win11-setup)

### Disparo remoto (via orquestrador)

```bash
python3 scripts/python/orquestrador.py --host <IP> --usuario <user> --chave ~/.ssh/id_ed25519 --pos completa
python3 scripts/python/orquestrador.py --host <IP> --usuario <user> --chave ~/.ssh/id_ed25519 --debloat lite
```

| Flag | Modos |
| :--- | :--- |
| `--pos` | `completa` (padrão), `ajustes`, `sem-runtimes`, `sem-apps` |
| `--debloat` | `completo` (padrão), `lite` |

> 🧠 **Ordem ideal da bancada:** Etapa 4 (Desbloat) → Etapa 5 (Pós-instalação) — primeiro
> remove o que não serve, depois instala o que é essencial.

## 🐍 Orquestração em Python

### 🗺️ Arquitetura geral

```text
┌─────────────────────────────────────────────────────────────┐
│  🐍 PYTHON (o maestro)                                      │
│  scripts/python/orquestrador.py                             │
│                                                             │
│  • conecta via SSH                                          │
│  • envia os scripts .ps1                                    │
│  • executa e interpreta o JSON                              │
│  • gera o manifesto Markdown                                │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  🪟 POWERSHELL (os braços)                                  │
│  scripts/powershell/                                        │
│                                                             │
│  • inventario.ps1        → coleta dados da máquina          │
│  • backup-robocopy.ps1   → copia pastas (archimedes-backup) │
│  • pos-instalacao.ps1    → apps+runtimes (after-install)    │
│  • Win11Debloat.ps1      → limpa bloatware (after-install)  │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  📋 MARKDOWN (o resultado)                                  │
│  manifests/MANIFESTO_<cliente>_<data>.md                    │
└─────────────────────────────────────────────────────────────┘
```

> 🧠 **Em uma frase:** Python decide e orquestra; PowerShell executa no Windows; Markdown documenta.

### Estrutura sugerida

```text
scripts/
├── python/
│   ├── orquestrador.py      # Motor headless: orquestra as etapas (CLI)
│   ├── menu.py              # Menu interativo opcional (usa o motor)
│   └── tests/               # Testes pytest (orquestrador + menu)
└── powershell/
    ├── inventario.ps1       # Bloco de inventário JSON (Etapa 1)
    └── [backup-robocopy.ps1 → MOVIDO para archimedes-backup/windows/]
    └── [pos-instalacao.ps1 + Win11Debloat.* → MOVIDOS para archimedes-win11-setup/windows/]
```

### Dependências Python
```bash
pip install paramiko
```

### Orquestrador implementado (`scripts/python/orquestrador.py`)

O orquestrador está **implementado e funcional**. Fluxo executado por chamada:

```text
main() ──► conectar()                    (SSH via chave ed25519)
   ├──► enviar_script(inventario.ps1)    (SFTP → C:\Windows\Temp\archimedes-orquestrador\)
   ├──► coletar_inventario()             (executa PS1 → json.loads → dict)
   ├──► enviar_script(backup-robocopy.ps1)  # de ~/projetos/archimedes-backup/windows/
   ├──► executar_backup(destino)         (executa PS1 com -Destino → json.loads)
   ├──► enviar_script(pos-instalacao.ps1)   # de ~/projetos/archimedes-win11-setup/windows/ (--pos)
   ├──► enviar_script(Win11Debloat.zip)     # idem (--debloat)
   └──► gerar_manifesto()                (markdown → manifests/MANIFESTO_<cliente>_<data>.md)
```

**Destaques da implementação:**
- 🔌 `conectar` — sessão SSH com `AutoAddPolicy` e timeout de 10s.
- 📤 `enviar_script` — upload via **SFTP** com criação automática de diretório remoto.
- 📊 `parse_json_saida` — converte JSON do PowerShell com diagnóstico de erro (imprime amostra da saída bruta).
- 🧩 `coletar_inventario` / `executar_backup` — executam os `.ps1` e retornam estruturas Python.
- 📝 `gerar_manifesto` — monta o Markdown final a partir dos dados (tabelas + checklist de reinstalação).
- 🚦 `main` — CLI com `--host`, `--usuario`, `--chave`, `--cliente`, `--destino` (opcional — pula backup se ausente) e `--saida` (destino alternativo do manifesto).

### 🧪 Caso Real (2026-09-11) — Bug do SFTP corrigido

> **Sintoma:** ao rodar o orquestrador pela 1ª vez na VM Windows 11, falhou com:
> ```
> ✖ Falha ao enviar script via SFTP: [Errno 2] No such file
> ```
> Mesmo com `inventario.ps1` existindo localmente.

**Causa raiz (bug de lógica no `enviar_script`):**
- A função recebia o caminho **do arquivo** remoto: `C:\Windows\Temp\archimedes-orquestrador\inventario.ps1`
- O bloco de criação de diretório fazia `sftp.stat(caminho_do_arquivo)` seguido de `sftp.mkdir(caminho_do_arquivo)` — ou seja, tentava criar um **diretório com o nome do arquivo**!
- Quando `C:\Windows\Temp\archimedes-orquestrador\` não existia, o `mkdir` (que era do "arquivo") não criava o **diretório pai**, e o `sftp.put` falhava com `No such file`.

**Correção aplicada:**
```python
# Antes (bug): mkdir no caminho completo do ARQUIVO
try:
    sftp.stat(destino_remoto)
except FileNotFoundError:
    sftp.mkdir(destino_remoto)   # ❌ tentava criar dir "inventario.ps1"

# Depois (fix): separa diretório e cria SÓ o diretório, com barras normais
dir_remoto = posixpath.dirname(destino_remoto).replace("\\", "/")
try:
    sftp.stat(dir_remoto)
except FileNotFoundError:
    sftp.mkdir(dir_remoto)       # ✅ cria C:/Windows/Temp/archimedes-orquestrador
sftp.put(origem_local, destino_remoto.replace("\\", "/"))  # barras normais
```

**Lições registradas:**
- 💡 O `sftp-server` do **Windows OpenSSH aceita caminhos com barras normais** (`C:/Windows/...`) — usar `replace("\\", "/")` evita inconsistências de separador.
- 💡 `sftp.mkdir` **não cria diretórios intermediários** — precisa criar o diretório pai antes (ou um a um).
- ✅ **Validado em execução real:** inventário coletado de `DESKTOP-3PH481H` (Windows 11 Pro, 9 softwares) e manifesto gerado com sucesso.

### Flags da CLI

| Flag | Obrigatório | Descrição |
| :--- | :--- | :--- |
| `--host` | ✅ | IP/hostname da máquina alvo |
| `--usuario` | ✅ | Usuário da máquina alvo |
| `--chave` | opt | Chave privada (padrão `~/.ssh/id_ed25519`) |
| `--cliente` | ✅ | Nome do cliente para o manifesto |
| `--destino` | opt | UNC do storage (se ausente, pula backup) |
| `--saida` | opt | Caminho alternativo do manifesto |

---

## 🍽️ Menu Interativo

Camada opcional sobre o orquestrador — para quando **você** quer escolher o que fazer (backup, instalar programas, etc.) sem decorar flags. O motor headless do `orquestrador.py` fica **intacto** para automação; o menu apenas importa e chama as mesmas funções.

### Como usar

```bash
python3 scripts/python/menu.py
```

### Etapas disponíveis

| Opção | Etapa | O que faz |
| :--- | :--- | :--- |
| `1` | 📊 Inventário | Coleta dados técnicos + chave OEM (JSON) |
| `2` | 💾 Backup | Robocopy para o storage central |
| `3` | 📋 Manifesto | Gera `MANIFESTO_<CLIENTE>_<DATA>.md` (depende da etapa 1) |
| `4` | 🧹 Pós-instalação | Ajustes + apps + runtimes (pergunta o modo) |

### Modos de pós-instalação (etapa 4)

| Modo | Switches | Efeito |
| :--- | :--- | :--- |
| `C` completa | — | Ajustes + apps + runtimes (padrão) |
| `A` só ajustes | `-SkipApps -SkipRuntimes` | Não instala nada |
| `S` sem runtimes | `-SkipRuntimes` | Ajustes + apps |
| `R` sem apps | `-SkipApps` | Ajustes + runtimes |

### Regras do menu

- Escolha múltipla separada por vírgula (ex: `1,4` para inventário + pós-instalação) ou `tudo`.
- Menu **3** implica **1** automaticamente (manifesto sem inventário não faz sentido).
- Destino vazio → etapa de backup pulada com aviso.
- Conecta SSH **uma única vez** para todas as etapas escolhidas.
- Ao final, mostra o caminho do manifesto e do log de pós-instalação.

---

## 🚨 Tratamento de Erros e Validação

### Regras gerais
1. **Leia a saída de erro** — nunca invente.
2. **Reporte em PT-BR** com o erro específico.
3. **Sugira solução ou alternativa.**
4. **Nunca alucine sucesso.**

```bash
if [ $? -ne 0 ]; then
    echo "✖ Operação falhou. Erro: $?"
fi
```

### Matriz de falhas comuns

| Sintoma | Causa provável | Ação |
| :--- | :--- | :--- |
| `Connection refused` | SSH Server desativado/firewall | Habilitar OpenSSH Server + liberar porta 22 |
| `Authentication failed` | Senha errada / PIN Hello | Usar senha real, não PIN |
| `$LASTEXITCODE >= 8` | Arquivo bloqueado / permissão | Revisar log robocopy; /ZB + conta admin |
| JSON vazio no inventário | PSRM / política de execução bloqueou | Subir com `-ExecutionPolicy Bypass` |
| Comando não encontrado (`powershell.exe`) | PATH incompleto no sshd | Usar caminho completo `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` |
| `Falha ao enviar script via SFTP: No such file` | `enviar_script` com mkdir no caminho do ARQUIVO (bug antigo) | Atualizar orquestrador (fix `posixpath.dirname` + barras normais) — ver seção "Caso Real" |
| `sshd` RUNNING mas porta 22 fecha | Firewall Windows sem regra em rede `Public` | `netsh advfirewall firewall add rule name="OpenSSH-Server-In-TCP" dir=in action=allow protocol=TCP localport=22` |

### Validação pós-operação
- ✅ Conferir existência do arquivo de manifesto: `ls -la manifests/MANIFESTO_*.md`
- ✅ Conferir exit codes do robocopy: `$code -ge 8` → marcar falha
- ✅ Conferir que a chave OEM não está vazia; se vazia, marcar observação

---

## 🔒 Segurança e Boas Práticas

### Dados sensíveis
- **NUNCA** expor/comitar/logar: chaves OEM, senhas, tokens, chaves SSH, certificados (`*.key`, `*.pem`, `id_rsa`, `.env`).
- Manifestos reais com dados de cliente ficam **fora do versionamento** (ver `.gitignore` na raiz do repo) — somente o **template** é versionado.
- O repositório GitHub **`archimedes-orquestrador`** é **público** (decisão do usuário) — portanto:
  - ⚠️ **Jamais commitar manifestos reais** neste repo. Use `manifests/` local (ignorado) ou storage privado.
  - Se um manifesto real for exposto → **avisar imediatamente** e solicitar rotação da chave OEM/medidas.

### Conectividade
- Conexões SSH **apenas para máquinas documentadas** no projeto.
- Confirme o host antes de conectar (nunca rode `ssh` para máquina desconhecida sem autorização).

### Automação
- Todos os comandos remotos: **não-interativos** (`-NoProfile -NonInteractive`).
- Nunca deixar `senha` hardcoded em scripts; usar chave SSH ou variável de ambiente.
- Logs de execução podem conter hostnames → armazenar em `logs/` (ignorado pelo Git).

---

## 🔄 Fluxo de Execução Completo

```bash
# 1. (Pré) Garantir chave SSH copiada para a máquina alvo
# 2. Rodar orquestrador
python3 scripts/python/orquestrador.py \
  --host 192.168.1.50 \
  --usuario bruno \
  --chave ~/.ssh/id_ed25519 \
  --cliente TECNOSOFT \
  --destino '\\storage-central\Bancada\TECNOSOFT'

# 3. Resultado esperado
#    - Manifesto: manifests/MANIFESTO_TECNOSOFT_2026-09-11.md
#    - Backup:    \\storage-central\Bancada\TECNOSOFT\<usuarios>\...
#    - Logs:      logs/ (locais)
```

---

## 🔗 Fontes

- [Robocopy — Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)
- [Get-CimInstance SoftwareLicensingService — Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/get-ciminstance)
- [OpenSSH Server no Windows — Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- [Paramiko — Documentação](https://www.paramiko.org/)