#!/bin/bash
# motor-navegador.sh — backup de FAVORITOS + SENHAS (criptografadas) do navegador
# Suporta Chrome/Chromium e Edge. Detecta o navegador padrão automaticamente.
#
# ⚠️ SENHAS: são copiadas SOMENTE como arquivo criptografado do navegador
# (Login Data / Local State) — NUNCA em texto plano. Restauram no mesmo usuário.
#
# Uso:
#   bash motor-navegador.sh \
#     --origem-ssh "paula@10.0.0.218" \
#     --destino-ssh "backup@10.0.0.4" \
#     --destino-dir "/srv/arquivos/backup/omarchy-paula" \
#     [--browser auto|chrome|edge] \
#     [--dry-run]
#
# Fluxo: o controller (este script) é enviado para a ORIGEM via scp e executado
# lá (modo remoto), copiando os arquivos do navegador para o destino com agent
# forwarding (chave do operador) — mesmo padrão do motor-rsync.sh.
set -euo pipefail

# ---------- MODO REMOTO (executa NA máquina de origem) ----------
exec_motor_remoto() {
    local browser="${BROWSER:-auto}" cfg_dir="" dest_base="${DESTINO_DIR%/}" src=""

    # 1) Descobre o navegador
    if [[ "$browser" == "auto" ]]; then
        cfg_dir=""
        local padrao
        padrao="$(xdg-settings get default-web-browser 2>/dev/null || true)"
        case "$padrao" in
            *google-chrome*|*chromium*) cfg_dir="$HOME/.config/google-chrome"; [[ -d "$cfg_dir" ]] || cfg_dir="$HOME/.config/chromium" ;;
            *microsoft-edge*)          cfg_dir="$HOME/.config/microsoft-edge" ;;
        esac
        # Fallback: procura por instalação
        [[ -z "$cfg_dir" && -d "$HOME/.config/google-chrome" ]] && cfg_dir="$HOME/.config/google-chrome"
        [[ -z "$cfg_dir" && -d "$HOME/.config/microsoft-edge" ]] && cfg_dir="$HOME/.config/microsoft-edge"
    elif [[ "$browser" == "chrome" ]]; then
        cfg_dir="$HOME/.config/google-chrome"
        [[ -d "$cfg_dir" ]] || cfg_dir="$HOME/.config/chromium"
    elif [[ "$browser" == "edge" ]]; then
        cfg_dir="$HOME/.config/microsoft-edge"
    else
        echo "✖ --browser inválido: $browser" >&2
        exit 2
    fi

    if [[ -z "$cfg_dir" || ! -d "$cfg_dir" ]]; then
        echo "ℹ Nenhum navegador Chrome/Edge encontrado em ~/.config — pulando etapa navegador."
        exit 0
    fi
    local navegador
    navegador="$(basename "$cfg_dir")"   # google-chrome | chromium | microsoft-edge
    echo "ℹ Backup do NAVEgador detectado: $navegador ($cfg_dir)"

    # 2) Local State (chave de criptografia) — ajuda a restaurar senhas no mesmo usuário
    if [[ -f "$cfg_dir/Local State" ]]; then
        echo "▶ Local State"
        RSYNC_RSH='ssh -o StrictHostKeyChecking=accept-new' rsync -a --partial ${DRY:-} \
            "$cfg_dir/Local State" \
            "$DESTINO_SSH:$dest_base/navegador/$navegador/Local State"
    fi

    # 3) Perfis (Default + Profile N): favoritos + senhas criptografadas
    local perfis=()
    while IFS= read -r -d '' p; do
        [[ -d "$p" ]] && perfis+=("$p")
    done < <(find "$cfg_dir" -maxdepth 1 -type d \( -name 'Default' -o -name 'Profile*' \) -print0)

    if [[ ${#perfis[@]} -eq 0 ]]; then
        echo "⚠ Nenhum perfil encontrado em $cfg_dir (navegador pode nunca ter sido aberto)."
        exit 0
    fi

    for p in "${perfis[@]}"; do
        local perfil
        perfil="$(basename "$p")"
        for f in 'Bookmarks' 'Bookmarks.bak' 'Login Data' 'Login Data-journal'; do
            if [[ -f "$p/$f" ]]; then
                echo "▶ $navegador/$perfil/$f"
                RSYNC_RSH='ssh -o StrictHostKeyChecking=accept-new' rsync -a --partial ${DRY:-} \
                    "$p/$f" \
                    "$DESTINO_SSH:$dest_base/navegador/$navegador/$perfil/$f"
            fi
        done
    done

    echo "✔ Navegador finalizado (exit 0)"
    exit 0
}

# Se chamado com MODO_REMOTO=1 (executado na origem) → só roda o motor remoto
if [[ "${MODO_REMOTO:-}" == "1" ]]; then
    exec_motor_remoto
fi

# ---------- CONTROLLER (roda onde o operador está) ----------
ORIGEM_SSH=""
DESTINO_SSH=""
DESTINO_DIR=""
BROWSER="auto"
DRY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --origem-ssh)  ORIGEM_SSH="$2";  shift 2 ;;
        --destino-ssh) DESTINO_SSH="$2"; shift 2 ;;
        --destino-dir) DESTINO_DIR="$2"; shift 2 ;;
        --browser)     BROWSER="$2";     shift 2 ;;
        --dry-run)     DRY="--dry-run";  shift ;;
        *) echo "✖ Argumento desconhecido: $1"; exit 2 ;;
    esac
done

[[ -z "$ORIGEM_SSH" ]]  && { echo "✖ --origem-ssh é obrigatório";      exit 2; }
[[ -z "$DESTINO_SSH" ]] && { echo "✖ --destino-ssh é obrigatório";     exit 2; }
[[ -z "$DESTINO_DIR" ]] && { echo "✖ --destino-dir é obrigatório";     exit 2; }

# Envia este próprio script para a origem e executa lá (com agent forwarding)
echo "🔌 Enviando motor-navegador para ${ORIGEM_SSH}..."
ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$ORIGEM_SSH" "mkdir -p /tmp/archimedes-backup"
scp -q -o StrictHostKeyChecking=accept-new "$0" "$ORIGEM_SSH:/tmp/archimedes-backup/motor-navegador.sh"

# Escapa args com segurança para passar como env vars ao shell remoto
DS_Q="$(printf '%q' "$DESTINO_SSH")"
DD_Q="$(printf '%q' "$DESTINO_DIR")"
BR_Q="$(printf '%q' "$BROWSER")"
DR_Q="$(printf '%q' "$DRY")"

echo "▶ Executando motor-navegador na origem..."
ssh -A -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$ORIGEM_SSH" \
    "export MODO_REMOTO=1 DESTINO_SSH=$DS_Q DESTINO_DIR=$DD_Q BROWSER=$BR_Q DRY=$DR_Q; bash /tmp/archimedes-backup/motor-navegador.sh"