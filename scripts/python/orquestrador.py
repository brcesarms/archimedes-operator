#!/usr/bin/env python3
"""Orquestrador do Projeto Bancada — conecta via SSH e executa as 3 etapas.

Uso:
    python3 orquestrador.py --host 192.168.1.50 --usuario bruno \
        --chave ~/.ssh/id_ed25519 --cliente TECNOSOFT \
        --destino '\\\\storage-central\\Bancada\\TECNOSOFT'

Fluxo:
    1. Inventario  — envia inventario.ps1, executa e faz parse do JSON.
    2. Backup      — envia backup-robocopy.ps1, executa para o destino e parse do JSON.
    3. Manifesto   — gera MANIFESTO_<CLIENTE>_<DATA>.md em manifests/ (gitignored).
"""
import argparse
import datetime
import json
import os
import posixpath
import sys

import paramiko

# Diretórios padrão do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_PS_DIR = os.path.join(BASE_DIR, "scripts", "powershell")
MANIFESTS_DIR = os.path.join(BASE_DIR, "manifests")

# Local remoto temporário onde os .ps1 são carregados
REMOTE_SCRIPT_DIR = "C:\\Windows\\Temp\\projeto-bancada"

# Prefixo padrão do comando PowerShell remoto (não-interativo)
PS_PREFIX = (
    "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass "
)


def conectar(host, usuario, chave_privada):
    """Abre sessão SSH com a máquina alvo usando chave ed25519."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=usuario,
        key_filename=chave_privada,
        timeout=10,
    )
    return client


def executar_remoto(client, comando_powershell):
    """Executa comando PowerShell remoto de forma não-interativa.

    Retorna (saida, erro, codigo_exit).
    """
    stdin, stdout, stderr = client.exec_command(comando_powershell)
    saida = stdout.read().decode("utf-8", errors="replace")
    erro = stderr.read().decode("utf-8", errors="replace")
    codigo = stdout.channel.recv_exit_status()
    return saida.strip(), erro.strip(), codigo


def enviar_script(client, origem_local, destino_remoto):
    """Envia um arquivo .ps1 via SFTP para a máquina remota.

    Cria o diretório remoto se necessário. Retorna True em sucesso.
    """
    if not os.path.isfile(origem_local):
        print(f"✖ Script local não encontrado: {origem_local}")
        return False

    sftp = client.open_sftp()
    try:
        # Separa diretório e arquivo: o mkdir ocorre no DIRETÓRIO, não no arquivo.
        dir_remoto = posixpath.dirname(destino_remoto)
        # Garante caminho com barras normais (sftp do Windows aceita 'C:/...')
        dir_remoto = dir_remoto.replace("\\", "/")
        try:
            sftp.stat(dir_remoto)
        except FileNotFoundError:
            sftp.mkdir(dir_remoto)
            print(f"✔ Diretório remoto criado: {dir_remoto}")
        # Envia para o caminho no formato aceito pelo sftp-server do Windows
        destino_envio = destino_remoto.replace("\\", "/")
        sftp.put(origem_local, destino_envio)
        print(f"✔ Script enviado: {os.path.basename(origem_local)}")
        return True
    except Exception as e:
        print(f"✖ Falha ao enviar script via SFTP: {e}")
        return False
    finally:
        sftp.close()


def parse_json_saida(saida, contexto="comando"):
    """Converte a saída JSON do PowerShell para dict/list.

    Em caso de erro de parse, imprime diagnóstico e retorna None.
    """
    if not saida:
        print(f"⚠ Saída vazia do {contexto} — verifique se o PS1 rodou.")
        return None
    try:
        return json.loads(saida)
    except json.JSONDecodeError as e:
        print(f"✖ Falha ao parsear JSON do {contexto}: {e}")
        print(f"  Saída bruta (primeiros 500 chars): {saida[:500]}")
        return None


def coletar_inventario(client):
    """Envia inventario.ps1, executa e retorna dict com o inventário.

    Retorna None em caso de falha.
    """
    script_local = os.path.join(SCRIPTS_PS_DIR, "inventario.ps1")
    script_remoto = f"{REMOTE_SCRIPT_DIR}\\inventario.ps1"

    if not enviar_script(client, script_local, script_remoto):
        return None

    comando = f'{PS_PREFIX} -Command "& \'{script_remoto}\'"'
    saida, erro, codigo = executar_remoto(client, comando)

    if codigo != 0:
        print(f"✖ Inventário falhou (exit {codigo}). Erro: {erro}")
        return None

    inventario = parse_json_saida(saida, contexto="inventario")
    if inventario is None:
        return None

    print(f"✔ Inventário coletado: {inventario.get('hostname', '?')} · "
          f"{inventario.get('windows', '?')} · "
          f"usuários={len(inventario.get('usuarios', []))} · "
          f"softwares={len(inventario.get('softwares', []))}")
    return inventario


def executar_backup(client, destino):
    """Envia backup-robocopy.ps1 e executa com o destino informado.

    Retorna lista de status por pasta, ou None em falha.
    """
    script_local = os.path.join(SCRIPTS_PS_DIR, "backup-robocopy.ps1")
    script_remoto = f"{REMOTE_SCRIPT_DIR}\\backup-robocopy.ps1"

    if not enviar_script(client, script_local, script_remoto):
        return None

    # Escape do caminho UNC para passar como argumento PowerShell
    destino_esc = destino.replace("\\", "\\\\")
    comando = (
        f'{PS_PREFIX} -Command "& \'{script_remoto}\' -Destino \'{destino_esc}\'"'
    )
    saida, erro, codigo = executar_remoto(client, comando)

    if codigo != 0:
        print(f"✖ Backup falhou (exit {codigo}). Erro: {erro}")
        return None

    status = parse_json_saida(saida, contexto="backup")
    if status is None:
        return None

    ok = sum(1 for s in status if s.get("codigo", 8) < 8)
    falhas = sum(1 for s in status if s.get("codigo", 8) >= 8)
    print(f"✔ Backup concluído: {ok} pastas ok, {falhas} com falha")
    return status


def gerar_manifesto(inventario, status_copias, cliente, data, saida=None):
    """Gera o arquivo MANIFESTO_<CLIENTE>_<DATA>.md.

    Por padrão salva em manifests/ (gitignored). Use 'saida' para sobrescrever.
    Retorna caminho do arquivo gerado ou None em falha.
    """
    if saida is None:
        os.makedirs(MANIFESTS_DIR, exist_ok=True)
        saida = os.path.join(MANIFESTS_DIR, f"MANIFESTO_{cliente}_{data}.md")

    hostname = inventario.get("hostname", "?")
    windows = inventario.get("windows", "?")
    versao = inventario.get("versao", "?")
    chave_oem = inventario.get("chave_oem", "") or "N/A (Volume/Reinstalação)"
    usuarios = inventario.get("usuarios", [])
    softwares = inventario.get("softwares", [])

    linhas = []
    linhas.append(f"# 📋 Manifesto de Bancada — {cliente}")
    linhas.append("")
    linhas.append("> ⚠️ **Documento sensível:** contém chave OEM e dados de cliente. Não commitar em repositório público.")
    linhas.append("")
    linhas.append("## 🧾 Informações Gerais")
    linhas.append("")
    linhas.append("| Campo | Valor |")
    linhas.append("| :--- | :--- |")
    linhas.append(f"| **Cliente** | {cliente} |")
    linhas.append(f"| **Data** | {data} |")
    linhas.append(f"| **Hostname** | {hostname} |")
    linhas.append("")
    linhas.append("## 💻 Inventário Técnico")
    linhas.append("")
    linhas.append("| Item | Valor |")
    linhas.append("| :--- | :--- |")
    linhas.append(f"| **Windows** | {windows} |")
    linhas.append(f"| **Versão** | {versao} |")
    linhas.append(f"| **Chave OEM (BIOS)** | {chave_oem} |")
    linhas.append(f"| **Usuários** | {', '.join(usuarios) if usuarios else '—'} |")
    linhas.append("")
    linhas.append("## 📂 Status de Cópia")
    linhas.append("")
    if status_copias:
        linhas.append("| Pasta | Status | Obs |")
        linhas.append("| :--- | :--- | :--- |")
        for item in status_copias:
            usuario = item.get("usuario", "?")
            pasta = item.get("pasta", "?")
            codigo = item.get("codigo", 8)
            obs = item.get("obs", "")
            origem = item.get("origem", "")
            if codigo == -1:
                status = "☐"
            elif codigo < 8:
                status = "✅"
            else:
                status = "❌"
            obs = f"code={codigo} {obs}".strip()
            if origem:
                obs = f"origem={origem} {obs}".strip()
            linhas.append(f"| `{usuario}/{pasta}` | {status} | {obs} |")
    else:
        linhas.append("_Backup não executado ou sem dados._")
    linhas.append("")
    linhas.append("## 📦 Checklist de Reinstalação")
    linhas.append("")
    if softwares:
        for sw in sorted(softwares, key=lambda x: x.get("nome", "")):
            nome = sw.get("nome", "?")
            versao_sw = sw.get("versao", "")
            linhas.append(f"- [ ] {nome} {versao_sw}".strip())
    else:
        linhas.append("- [ ] _(nenhum software detectado)_")
    linhas.append("")
    linhas.append("## 📝 Observações")
    linhas.append("")
    linhas.append("- _Pendências, arquivos não copiados, peculiaridades_")
    linhas.append("")
    linhas.append("---")
    linhas.append("")
    linhas.append("## 🔗 Fontes")
    linhas.append("")
    linhas.append(f"- Logs robocopy: `logs/robocopy_{hostname}.log`")
    linhas.append("")

    try:
        with open(saida, "w", encoding="utf-8") as f:
            f.write("\n".join(linhas))
        print(f"✔ Manifesto gerado: {saida}")
        return saida
    except OSError as e:
        print(f"✖ Falha ao gravar manifesto: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Projeto Bancada — orquestrador")
    parser.add_argument("--host", required=True, help="IP/hostname da máquina alvo")
    parser.add_argument("--usuario", required=True, help="Usuário da máquina alvo")
    parser.add_argument(
        "--chave",
        default=os.path.expanduser("~/.ssh/id_ed25519"),
        help="Caminho da chave privada SSH",
    )
    parser.add_argument("--cliente", required=True, help="Nome do cliente")
    parser.add_argument(
        "--destino",
        help="UNC do storage central (ex: \\\\nas\\Bancada\\CLIENTE). Sem este flag, pula backup.",
    )
    parser.add_argument(
        "--saida",
        help="Caminho alternativo do manifesto (padrão: manifests/).",
    )
    args = parser.parse_args()

    data = datetime.date.today().isoformat()

    print(f"⏳ Conectando a {args.host} como {args.usuario}...")
    client = conectar(args.host, args.usuario, args.chave)
    try:
        # Etapa 1 — Inventário (obrigatória)
        inventario = coletar_inventario(client)
        if inventario is None:
            print("✖ Abortando: inventário falhou.")
            return 1

        # Etapa 2 — Backup (opcional, só com --destino)
        status = {}
        if args.destino:
            status = executar_backup(client, args.destino)
            if status is None:
                print("⚠ Backup falhou — manifesto será gerado sem status de cópia.")
                status = {}

        # Etapa 3 — Manifesto
        manifesto = gerar_manifesto(inventario, status, args.cliente, data, args.saida)
        if manifesto is None:
            return 1

        print("🎯 Fluxo concluído com sucesso!")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())