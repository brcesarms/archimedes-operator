#!/bin/bash
# motor-rsync.sh — motor de backup Linux do Archimedes Backup
# Executa rsync local OU na máquina de origem remota (agent forwarding p/ destino).
#
# Uso:
#   bash motor-rsync.sh \
#     --origem-ssh "paula@10.0.0.218" \        # vazio = origem local
#     --origem "/run/media/paula/BRUNO/" \
#     --destino-ssh "backup@10.0.0.4" \
#     --destino "/srv/arquivos/backup/omarchy-paula/" \
#     --excluir "*.tmp,*.part" \
#     [--dry-run]
set -euo pipefail

ORIGEM_SSH=""
ORIGEM=""
DESTINO_SSH=""
DESTINO=""
EXCLUIR=""
DRY=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --origem-ssh)  ORIGEM_SSH="$2";  shift 2 ;;
        --origem)      ORIGEM="$2";      shift 2 ;;
        --destino-ssh) DESTINO_SSH="$2"; shift 2 ;;
        --destino)     DESTINO="$2";     shift 2 ;;
        --excluir)     EXCLUIR="$2";     shift 2 ;;
        --dry-run)     DRY="--dry-run";  shift ;;
        *) echo "✖ Argumento desconhecido: $1"; exit 2 ;;
    esac
done

[[ -z "$ORIGEM" ]]      && { echo "✖ --origem é obrigatório";      exit 2; }
[[ -z "$DESTINO_SSH" ]] && { echo "✖ --destino-ssh é obrigatório"; exit 2; }
[[ -z "$DESTINO" ]]     && { echo "✖ --destino é obrigatório";     exit 2; }

# Barra final normalizada
ORIGEM="${ORIGEM%/}/"
DESTINO="${DESTINO%/}/"

# Monta opções de exclusão
EXCL_OPTS=()
IFS=',' read -ra EXCL_LISTA <<< "$EXCLUIR"
for e in "${EXCL_LISTA[@]}"; do
    e="$(echo "$e" | xargs)"
    [[ -n "$e" ]] && EXCL_OPTS+=(--exclude="$e")
done

RSYNC_OPTS=(-aHX --partial --delete --info=progress2 ${DRY} "${EXCL_OPTS[@]}")

if [[ -n "$ORIGEM_SSH" ]]; then
    # Executa NA ORIGEM remota com agent forwarding (chave do operador → destino)
    # Política de BANCADA: aceita a 1ª host key do destino automaticamente (accept-new)
    RSH="ssh -o StrictHostKeyChecking=accept-new"
    CMD="RSYNC_RSH='${RSH}' rsync ${RSYNC_OPTS[*]} '${ORIGEM}' '${DESTINO_SSH}:${DESTINO}'"
    echo "▶ [${ORIGEM_SSH}] $CMD"
    ssh -A -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "$ORIGEM_SSH" "$CMD"
else
    # Origem local (controller) → destino remoto
    echo "▶ [local] rsync ${RSYNC_OPTS[*]} ${ORIGEM} ${DESTINO_SSH}:${DESTINO}"
    rsync "${RSYNC_OPTS[@]}" "${ORIGEM}" "${DESTINO_SSH}:${DESTINO}"
fi

echo "✔ rsync concluído (exit $?)"