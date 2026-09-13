#!/bin/bash
# setup-ssh.sh — autoriza a chave do operador na máquina alvo (Linux OU Windows).
#
# 100% por ARGUMENTO — sem prompts, sem digitação manual (auxiliar do orquestrador).
# Dados do alvo são passados na chamada (o Archimedes usa os valores do perfil).
#
# Uso:
#   bash setup-ssh.sh usuario@ip [--so linux|windows]
#
# Exemplos:
#   bash setup-ssh.sh paula@10.0.0.218            # assume Linux
#   bash setup-ssh.sh bruno@10.0.0.217 --so windows
set -euo pipefail

CHAVE="${SSH_CHAVE:-$HOME/.ssh/id_ed25519.pub}"
ALVO=""
SO=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --so)       SO="$2"; shift 2 ;;
        -h|--help)  echo "Uso: bash setup-ssh.sh usuario@ip [--so linux|windows]"; exit 0 ;;
        *)          ALVO="$1"; shift ;;
    esac
done

[[ -z "$ALVO" ]] && { echo "✖ Informe o alvo: bash setup-ssh.sh usuario@ip [--so linux|windows]"; exit 2; }
[[ -z "$SO" ]] && SO="linux"

# ---------- VALIDAÇÃO ----------
if [[ ! -f "$CHAVE" ]]; then
    echo "✖ Chave pública não encontrada: $CHAVE"
    echo "  Gere uma com: ssh-keygen -t ed25519"
    exit 2
fi
IP="${ALVO##*@}"
USUARIO="${ALVO%@*}"

# ---------- 1. TESTAR PORTA 22 ----------
echo "🔍 Testando SSH em ${IP}:22..."
if ! timeout 3 bash -c "cat < /dev/null > /dev/tcp/${IP}/22" 2>/dev/null; then
    echo "✖ Porta 22 fechada/filtrada em ${IP}. Ative o SSH no alvo:"
    echo "   🐧 Arch/Omarchy: sudo pacman -S --noconfirm openssh && sudo systemctl enable --now sshd"
    echo "   🐧 Debian/Ubuntu: sudo apt install -y openssh-server && sudo systemctl enable --now ssh"
    echo "   🪟 Windows: Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"
    exit 1
fi

# ---------- 2. AUTORIZAR CHAVE ----------
if [[ "$SO" == "windows" ]]; then
    echo "🪟 Autorizando chave no Windows em ${ALVO}..."
    CHAVE_FILE="chave_$(date +%s).pub"
    scp -q "$CHAVE" "${ALVO}:${CHAVE_FILE}"
    # Anexa a chave ao authorized_keys do usuário e remove o temporário
    ssh "$ALVO" "powershell -NoProfile -Command \"New-Item -ItemType Directory -Force \$env:USERPROFILE\\.ssh | Out-Null; Get-Content \$env:USERPROFILE\\${CHAVE_FILE} | Add-Content \$env:USERPROFILE\\.ssh\\authorized_keys; Remove-Item \$env:USERPROFILE\\${CHAVE_FILE}\""
else
    echo "🐧 Autorizando chave no Linux em ${ALVO}..."
    ssh-copy-id -i "$CHAVE" "$ALVO"
fi

# ---------- 3. VERIFICAR LOGIN SEM SENHA ----------
echo "✅ Verificando login com chave (sem senha)..."
if ssh -o BatchMode=yes -o ConnectTimeout=10 "$ALVO" "echo OK-do-alvo"; then
    echo "✔ Chave autorizada e login sem senha funcionando em ${ALVO}!"
else
    echo "⚠️  Ainda exige senha (normal na 1ª vez / senha vazia). Repita o script ou use ssh-copy-id."
    exit 3
fi