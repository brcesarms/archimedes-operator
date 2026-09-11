# 🪟 Preparar Máquina Windows 11 — Passo a Passo

> **Objetivo:** habilitar o acesso SSH na máquina Windows 11 para que o **Projeto Bancada** (Archimedes) consiga se conectar, coletar inventário e fazer o backup.
>
> ⏱️ **Tempo estimado:** 3–5 minutos · **Nível:** fácil

---

## 📖 Sumário

1. [Antes de começar](#-antes-de-começar)
2. [O que este guia faz](#-o-que-este-guia-faz)
3. [Passo 1 — Baixar o script](#-passo-1--baixar-o-script)
4. [Passo 2 — Abrir PowerShell como Administrador](#-passo-2--abrir-powershell-como-administrador)
5. [Passo 3 — Liberar a execução de scripts](#-passo-3--liberar-a-execuação-de-scripts)
6. [Passo 4 — Executar o setup](#-passo-4--executar-o-setup)
7. [Passo 5 — Verificar se deu certo](#-passo-5--verificar-se-deu-certo)
8. [Passo 6 — Anotar os dados e avisar o Bruno](#-passo-6--anotar-os-dados-e-avisar-o-bruno)
9. [⚠️ Solução de problemas](#️-solução-de-problemas)
10. [🔗 Fontes](#-fontes)

---

## ✅ Antes de começar

- Você precisa estar **logado com uma conta de usuário do Windows** (pode ser conta local ou Microsoft, tanto faz).
- ⚠️ **Importante:** o SSH **não aceita o PIN do Windows Hello** como senha. Será usada **chave SSH** (automática), então você **não vai precisar digitar senha** na conexão.
- A máquina precisa ter **acesso à internet** (ou à rede local) para baixar o script e, depois, para o backup.

---

## 🎯 O que este guia faz

Ele roda um script que configura **tudo automaticamente**:

| # | Ação |
| :--- | :--- |
| 1 | Instala o **OpenSSH Server** (recurso do Windows) |
| 2 | Inicia o serviço **`sshd`** e deixa ele automático |
| 3 | Cria a **regra de firewall** para a porta 22 |
| 4 | **Autoriza a chave SSH** do Bruno (sem precisar de senha depois) |
| 5 | Mostra o **IP** e o **usuário** da máquina no final |

> 💡 **Você só vai copiar e colar comandos.** Nada de digitar código na mão.

---

## 📥 Passo 1 — Baixar o script

Na máquina Windows, abra o navegador e acesse:

```
https://raw.githubusercontent.com/brcesarms/projeto-bancada/main/scripts/powershell/setup-ssh-pri.ps1
```

Se o navegador mostrar o conteúdo (texto), faça assim:

1. Pressione **Ctrl+A** (selecionar tudo)
2. **Ctrl+C** (copiar)
3. Abra o **Bloco de Notas** (Notepad)
4. **Ctrl+V** (colar)
5. **Salvar como** → nome: `setup-ssh-pri.ps1` — atenção: na caixa "Tipo", escolha **"Todos os arquivos (*.*)"** e salve em uma pasta fácil, ex: `C:\ssh-setup\`

> ✅ Pronto: o arquivo `setup-ssh-pri.ps1` está salvo na máquina.

---

## 🖥️ Passo 2 — Abrir PowerShell como Administrador

1. Clique no botão **Iniciar** (ou tecle a tecla **Windows**)
2. Digite: `powershell`
3. No resultado **"Windows PowerShell"**, clique com o **botão direito** → **Executar como administrador**
4. Clique em **Sim** na janela do UAC

> ✅ A janela do PowerShell abriu **como Administrador** (o título costuma mostrar isso).

---

## 🔓 Passo 3 — Liberar a execução de scripts

Cole este comando na janela do PowerShell e aperte **Enter**:

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
```

> 💡 Este comando libera a execução de scripts **apenas nesta janela**. Não altera nada permanente no sistema.

---

## ▶️ Passo 4 — Executar o setup

Agora navegue até a pasta onde salvou o script e execute.

**Exemplo (se salvou em `C:\ssh-setup\`):**

```powershell
cd C:\ssh-setup
.\setup-ssh-pri.ps1
```

> ⚠️ **Importante:** o comando é `.\setup-ssh-pri.ps1` — com o `.\` na frente. Isso diz ao PowerShell "o arquivo está nesta pasta".

O script vai mostrar progresso como:

```
========================================================
🏛️ Archimedes — Setup do OpenSSH Server (Windows)
========================================================

🚀 [1/4] Verificando instalacao do OpenSSH Server...
✔ OpenSSH Server ja esta instalado!

⚡ [2/4] Configurando servico sshd...
✔ Servico sshd em execucao e configurado para inicializacao automatica!
...
```

⏳ **Pode demorar um pouco** na instalação do recurso (passo 1) — é normal, espere terminar.

---

## 🔍 Passo 5 — Verificar se deu certo

No final, o script mostra:

```
🎉 Tudo pronto! SSH ativo e configurado com sucesso! ✅
👤 Usuario Windows: SEU_USUARIO
🌐 IP(s) encontrados nesta maquina:
   👉 192.168.1.50
💻 Bruno, para conectar use:
   ssh SEU_USUARIO@192.168.1.50
```

**Verificação extra (opcional):** cole e veja se o serviço está ativo:

```powershell
Get-Service sshd
```

Deve mostrar `Status: Running`.

---

## 📋 Passo 6 — Anotar os dados e avisar o Bruno

Anote estas 3 informações (vão aparecer no final do script):

1. **👤 Usuário Windows** — ex: `bruno`
2. **🌐 IP** — ex: `192.168.1.50`
3. **Nome do cliente** que está formatando (ex: `TECNOSOFT`)

Depois, é só me avisar (Archimedes) com esses dados que eu conecto, coletor inventário e faço o backup. 🚀

---

## ⚠️ Solução de problemas

| Sintoma | Causa | Solução |
| :--- | :--- | :--- |
| ❌ *"execução de scripts está desabilitada"* | ExecutionPolicy bloqueando | Rode o **Passo 3** (`Set-ExecutionPolicy ...`) depois abra de novo a janela |
| ❌ *"requires ... as Administrator"* | Janela não é admin | Repita o **Passo 2** (botão direito → Executar como administrador) |
| ❌ *"não é possível carregar o arquivo ... não existe"* | Pasta errada | Confirme o `cd` no **Passo 4** — o arquivo precisa estar na pasta |
| ❌ *"não é um cmdlet reconhecido"* | Faltou o `.\` | Use `.\setup-ssh-pri.ps1` |
| ❌ *O script rodou mas mostrou erro na instalação* | Recurso do Windows falhou ao baixar | Verifique internet e rode como admin novamente |
| ❌ *Nada acontece ao dar 2 cliques no .ps1* | Duplo clique não executa script | Sempre executar **dentro do PowerShell** (Passo 4) |

---

## 🔗 Fontes

- [Script: setup-ssh-pri.ps1](../scripts/powershell/setup-ssh-pri.ps1)
- [Documento técnico do Projeto Bancada](./instrucoes.md)
- [OpenSSH Server no Windows — Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)