# 🏗️ Projeto Bancada — Instruções de Sistema (Refatorado)

> **Versão:** 2.0 · **Status:** Ativo · **Atualizado:** 2026-09-11
>
> Assistente de automação via **OpenCode CLI** para triagem, inventário técnico e backup forense pré-formatação de máquinas Windows conectadas à rede da bancada via SSH.

---

## 📖 Sumário

1. [Visão Geral e Arquitetura](#-visão-geral-e-arquitetura)
2. [Conexão e Comunicação SSH](#-conexão-e-comunicação-ssh)
3. [Etapa 1 — Coleta de Inventário](#-etapa-1--coleta-de-inventário)
4. [Etapa 2 — Backup com Robocopy](#-etapa-2--backup-com-robocopy)
5. [Etapa 3 — Geração do Manifesto](#-etapa-3--geração-do-manifesto)
6. [Orquestração em Python](#-orquestração-em-python)
7. [Tratamento de Erros e Validação](#-tratamento-de-erros-e-validação)
8. [Segurança e Boas Práticas](#-segurança-e-boas-práticas)
9. [Fluxo de Execução Completo](#-fluxo-de-execução-completo)
10. [🔗 Fontes](#-fontes)

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
| `3` | Manifesto Obsidian | `MANIFESTO_<CLIENTE>_<DATA>.md` em `t.i/` |

---

## 🔌 Conexão e Comunicação SSH

### Mecanismo
- Conectar à máquina alvo via SSH usando **client Python `paramiko`** ou cliente nativo OpenSSH.
- O Windows 10/11 moderno já inclui o **OpenSSH Server** opcional; verifique/instale na máquina alvo (via GUI: *Configurações → Aplicativos → Recursos Opcionais → OpenSSH Server*).

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

## 📦 Etapa 2 — Backup com Robocopy

### Parâmetros recomendados

```powershell
robocopy "<ORIGEM>" "<DESTINO_NET_SHARE>" /E /ZB /R:1 /W:1 /XJ /XD "AppData\Local\Temp" "$RECYCLE.BIN" "System Volume Information"
```

| Flag | Significado | Por que usar |
| :--- | :--- | :--- |
| `/E` | Copia subdiretórios, **incluindo vazios** | Não perde estrutura de pastas por falta de arquivos |
| `/ZB` | Usa modo reiniciável e cai para modo Backup se acesso negado | Resiliência a interrupções + contorna ACL restritas |
| `/R:1 /W:1` | 1 retry com 1s de espera para arquivos bloqueados | Evita travamento em arquivo em uso |
| `/XJ` | Exclui pontos de junção (junctions) | Evita loop infinito ao seguir `symlinks` do Windows |
| `/XD ...` | Exclui diretórios temporários e Lixeira | Não copia lixo que polui o backup |

### Diretórios copiados (por usuário)

| Pasta | Robocopy Origem |
| :--- | :--- |
| Desktop | `C:\Users\<user>\Desktop` |
| Documents | `C:\Users\<user>\Documents` |
| Downloads | `C:\Users\<user>\Downloads` |
| Pictures | `C:\Users\<user>\Pictures` |

### Destino: Storage Central

Certifique-se de que o destino é acessível como **UNC/share de rede** a partir da máquina alvo:
```powershell
\\<storage-central>\Bancada\<CLIENTE>\
```

> ⚠️ Se a máquina alvo ainda não tem acesso à rede (formatação com disco local), faça o backup **local primeiro** (ex: `D:\backup_<CLIENTE>\`) e depois transfira via `scp`/`rsync` para o storage.

### Validação de saída do Robocopy

| Exit Code | Significado | Ação |
| :--- | :--- | :--- |
| `0` | Nenhum arquivo copiado; nada a fazer | ✅ OK |
| `1` | Arquivos copiados com sucesso | ✅ OK |
| `2` | Arquivos extras (já existiam) | ✅ OK |
| `3` | `1 + 2` | ✅ OK |
| `4` | Arquivos incompatíveis detectados | ⚠️ Revisar |
| `5-7` | `4 + (1 ou 2 ou 3)` | ⚠️ Revisar |
| `8+` | Erros — falha de cópia | ❌ **NÃO terminou OK** — revisar log |

> **Regra:** `$LASTEXITCODE -ge 8` → trata como **falha de backup** e reporta no manifesto.

### Exemplo completo (PowerShell remoto, loop por usuário)

```powershell
$destino = "\\storage-central\Bancada\CLIENTE_X"
$usuarios = @($(Get-ChildItem C:\Users -Directory | Where-Object { $_.Name -notin @('Public','Default','Default User','All Users') } | Select-Object -ExpandProperty Name))
foreach ($u in $usuarios) {
    foreach ($dir in @('Desktop','Documents','Downloads','Pictures')) {
        $src = "C:\Users\$u\$dir"
        if (Test-Path $src) {
            $dst = "$destino\$u\$dir"
            robocopy $src $dst /E /ZB /R:1 /W:1 /XJ /XD "AppData\Local\Temp" "$RECYCLE.BIN" "System Volume Information" /LOG+:"C:\Windows\Temp\robocopy_$u.log"
            $code = $LASTEXITCODE
            Write-Output "$u|$dir|code=$code"
        }
    }
}
```

---

## 📝 Etapa 3 — Geração do Manifesto

### Convenção de nomenclatura
```
MANIFESTO_<CLIENTE>_<DATA>.md
```
Exemplo: `MANIFESTO_TECNOSOFT_2026-09-11.md`

### Localização no Vault
- O script e seus arquivos de saída pertencem à **gestão de infraestrutura técnica**.
- Salve os manifestos na pasta **`t.i/`** dentro do vault Obsidian (ver [Template do Manifesto](../templates/MANIFESTO_TEMPLATE.md)).

### Estrutura do Manifesto (`templates/MANIFESTO_TEMPLATE.md`)
1. **Cabeçalho** — cliente, data, técnico, hostname.
2. **Inventário** — Windows, versão, chave OEM, usuários.
3. **Status de cópia** — tabela por pasta (copiada ⚠️ pendente / ❌ erro).
4. **Checklist de reinstalação** — softwares detectados, com checkboxes.
5. **Observações** — pendências, arquivos não copiados, peculiaridades.

---

## 🐍 Orquestração em Python

### Estrutura sugerida

```text
scripts/
├── python/
│   └── orquestrador.py      # Classe/script principal que orquestra as 3 etapas
└── powershell/
    ├── inventario.ps1       # Bloco de inventário JSON (Etapa 1)
    └── backup-robocopy.ps1  # Loop de robocopy por usuário (Etapa 2)
```

### Dependências Python
```bash
pip install paramiko
```

### Esqueleto do orquestrador (`scripts/python/orquestrador.py`)

```python
#!/usr/bin/env python3
"""Orquestrador do Projeto Bancada — conecta via SSH e executa as 3 etapas."""
import argparse, json, os, sys
import paramiko

def conectar(host, usuario, chave_privada):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=usuario, key_filename=chave_privada, timeout=10)
    return client

def executar_remoto(client, comando_powershell):
    stdin, stdout, stderr = client.exec_command(comando_powershell)
    saida = stdout.read().decode("utf-8", errors="replace")
    erro = stderr.read().decode("utf-8", errors="replace")
    codigo = stdout.channel.recv_exit_status()
    return saida, erro, codigo

def coletar_inventario(client):
    # 1. Envia o bloco JSON de inventário (via SFTP: scripts/powershell/inventario.ps1)
    # 2. Executa remoto, faz json.loads da saída e retorna dict
    ...

def executar_backup(client, destino):
    # Executa backup-robocopy.ps1 e coleta |  por pasta
    ...

def gerar_manifesto(inventario, status_copias, cliente, data):
    # Monta MANIFESTO_<CLIENTE>_<DATA>.md e salva em t.i/
    ...

def main():
    parser = argparse.ArgumentParser(description="Projeto Bancada — orquestrador")
    parser.add_argument("--host", required=True)
    parser.add_argument("--usuario", required=True)
    parser.add_argument("--chave", default=os.path.expanduser("~/.ssh/id_ed25519"))
    parser.add_argument("--cliente", required=True)
    parser.add_argument("--destino", help="UNC do storage central")
    args = parser.parse_args()

    client = conectar(args.host, args.usuario, args.chave)
    try:
        inventario = coletar_inventario(client)
        status = executar_backup(client, args.destino) if args.destino else {}
        gerar_manifesto(inventario, status, args.cliente, __import__("datetime").date.today().isoformat())
    finally:
        client.close()

if __name__ == "__main__":
    sys.exit(main())
```

> ⚠️ **Validar antes de usar:** Este esqueleto é referência de arquitetura — as funções `coletar_inventario`, `executar_backup` e `gerar_manifesto` precisam da implementação completa (com SFTP dos `.ps1`, parse de saída e template de manifesto) antes de ir para produção.

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

### Validação pós-operação
- ✅ Conferir existência do arquivo de manifesto: `ls -la t.i/MANIFESTO_*.md`
- ✅ Conferir exit codes do robocopy: `$code -ge 8` → marcar falha
- ✅ Conferir que a chave OEM não está vazia; se vazia, marcar observação

---

## 🔒 Segurança e Boas Práticas

### Dados sensíveis
- **NUNCA** expor/comitar/logar: chaves OEM, senhas, tokens, chaves SSH, certificados (`*.key`, `*.pem`, `id_rsa`, `.env`).
- Manifestos reais com dados de cliente ficam **fora do versionamento** (ver `.gitignore` na raiz do repo) — somente o **template** é versionado.
- O repositório GitHub **`projeto-bancada`** é **público** (decisão do usuário) — portanto:
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
#    - Manifesto: t.i/MANIFESTO_TECNOSOFT_2026-09-11.md
#    - Backup:    \\storage-central\Bancada\TECNOSOFT\<usuarios>\...
#    - Logs:      logs/ (locais)
```

---

## 🔗 Fontes

- [Robocopy — Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/robocopy)
- [Get-CimInstance SoftwareLicensingService — Microsoft Learn](https://learn.microsoft.com/en-us/powershell/module/cimcmdlets/get-ciminstance)
- [OpenSSH Server no Windows — Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- [Paramiko — Documentação](https://www.paramiko.org/)