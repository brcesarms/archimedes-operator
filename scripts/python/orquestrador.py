#!/usr/bin/env python3
"""Orquestrador do Projeto Bancada — conecta via SSH e executa as 3 etapas.

Uso:
    python3 orquestrador.py --host 192.168.1.50 --usuario bruno \
        --chave ~/.ssh/id_ed25519 --cliente TECNOSOFT \
        --destino '\\\\storage-central\\Bancada\\TECNOSOFT'

Fluxo:
    1. Inventario  — envia inventario.ps1, executa e faz parse do JSON.
    2. Backup      — envia backup-robocopy.ps1 (do archimedes-backup), executa e parse do JSON.
    3. Manifesto   — gera MANIFESTO_<CLIENTE>_<DATA>.md em manifests/ (gitignored).
    4. Pós-instalação — envia pos-instalacao.ps1 (do archimedes-win11-setup), executa.
    5. Desbloat    — envia Win11Debloat.zip (do archimedes-win11-setup), descompacta e executa.
"""
import argparse
import datetime
import json
import os
import posixpath
import sys

import paramiko

# Diretórios padrão do projeto (100% autônomo e portátil)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_PS_DIR = os.path.join(BASE_DIR, "scripts", "powershell")
SCRIPTS_BASH_DIR = os.path.join(BASE_DIR, "scripts", "bash")
MANIFESTS_DIR = os.path.join(BASE_DIR, "manifests")

# Local remoto temporário onde os scripts são carregados
REMOTE_SCRIPT_DIR = "C:\\Windows\\Temp\\archimedes-operator"

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
        # Garante caminho com barras normais (sftp do Windows aceita 'C:/...')
        destino_envio = destino_remoto.replace("\\", "/")
        # Separa diretório e arquivo: o mkdir ocorre no DIRETÓRIO, não no arquivo.
        dir_remoto = posixpath.dirname(destino_envio)
        try:
            sftp.stat(dir_remoto)
        except FileNotFoundError:
            sftp.mkdir(dir_remoto)
            print(f"✔ Diretório remoto criado: {dir_remoto}")
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
    linhas.append("_Identificação da máquina e do serviço._")
    linhas.append("")
    linhas.append("| Campo | Valor |")
    linhas.append("| :--- | :--- |")
    linhas.append(f"| **Cliente** | {cliente} |")
    linhas.append(f"| **Data** | {data} |")
    linhas.append(f"| **Hostname** | {hostname} |")
    linhas.append("")
    linhas.append("## 💻 Inventário Técnico")
    linhas.append("")
    linhas.append("_O que havia na máquina antes da formatação: sistema, chave OEM e usuários._")
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
    linhas.append("_Resultado do backup: ✅ copiado · ☐ não executado · ❌ falhou (revisar log)._")
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
    linhas.append("_Programas a reinstalar após a formatação — marque as caixas ao instalar._")
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
    linhas.append("_Pendências, arquivos não copiados e observações do técnico._")
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


# Modos de pós-instalação suportados (pos-instalacao.ps1)
SWITCHES_POS = {
    "completa": "",
    "ajustes": " -SkipApps -SkipRuntimes",
    "sem-runtimes": " -SkipRuntimes",
    "sem-apps": " -SkipApps",
}


def montar_switches_pos(modo):
    """Retorna os switches do pos-instalacao.ps1 para o modo escolhido."""
    if modo not in SWITCHES_POS:
        raise ValueError(f"Modo de pós-instalação inválido: {modo}")
    return SWITCHES_POS[modo]


def executar_pos_instalacao(client, modo="completa"):
    """Envia pos-instalacao.ps1 e executa no modo escolhido com monitoramento de log.

    Modos: 'completa' (ajustes+apps+runtimes), 'ajustes' (pula apps e
    runtimes), 'sem-runtimes' (pula runtimes), 'sem-apps' (pula apps).

    Redireciona toda a saída para log remoto (evita perda de buffer em
    execuções longas) e faz streaming progressivo para o stdout local.
    """
    import time

    script_local = os.path.join(SCRIPTS_PS_DIR, "pos-instalacao.ps1")
    script_remoto = f"{REMOTE_SCRIPT_DIR}\\pos-instalacao.ps1"

    if not enviar_script(client, script_local, script_remoto):
        return None

    switches = montar_switches_pos(modo)
    log_remoto = f"{REMOTE_SCRIPT_DIR}\\pos-instalacao.log"
    log_remoto_norm = log_remoto.replace("\\", "/")

    # Limpa log antigo se existir
    executar_remoto(
        client,
        f'{PS_PREFIX} -Command "Remove-Item \'{log_remoto}\' -Force -ErrorAction SilentlyContinue"',
    )

    comando = (
        f'{PS_PREFIX} -Command "& \'{script_remoto}\'{switches} *> \'{log_remoto}\'"'
    )
    print(f"⏳ Executando pós-instalação ({modo}) remotamente via PowerShell...")

    transport = client.get_transport()
    channel = transport.open_session()
    channel.exec_command(comando)

    sftp = client.open_sftp()
    pos = 0
    while not channel.exit_status_ready():
        time.sleep(3)
        try:
            with sftp.open(log_remoto_norm, "rb") as f:
                f.seek(pos)
                novos_bytes = f.read()
                if novos_bytes:
                    pos += len(novos_bytes)
                    texto = novos_bytes.decode("utf-16le", errors="replace")
                    sys.stdout.write(texto)
                    sys.stdout.flush()
        except IOError:
            pass

    # Lê o restante após conclusão
    try:
        with sftp.open(log_remoto_norm, "rb") as f:
            f.seek(pos)
            sobra = f.read()
            if sobra:
                texto = sobra.decode("utf-16le", errors="replace")
                sys.stdout.write(texto)
                sys.stdout.flush()
    except IOError:
        pass
    sftp.close()

    codigo = channel.recv_exit_status()
    if codigo != 0:
        print(f"✖ Pós-instalação falhou (exit {codigo}).")
        return None

    print(f"✔ Pós-instalação ({modo}) concluída — log remoto: {log_remoto}")
    return log_remoto


def executar_debloat(client, switches="-RunDefaults -Silent -CreateRestorePoint"):
    """Envia pacote Win11Debloat e executa remotamente de forma silenciosa com monitoramento de log.

    Redireciona saída para log remoto e faz streaming para o stdout local.
    """
    import time

    zip_local = os.path.join(SCRIPTS_PS_DIR, "Win11Debloat.zip")
    zip_remoto = f"{REMOTE_SCRIPT_DIR}\\Win11Debloat.zip"
    debloat_dir_remoto = f"{REMOTE_SCRIPT_DIR}\\Win11Debloat"

    if not enviar_script(client, zip_local, zip_remoto):
        return None

    # Descompacta zip no diretório remoto
    unzip_cmd = (
        f'{PS_PREFIX} -Command "Expand-Archive -Path \'{zip_remoto}\' -DestinationPath \'{debloat_dir_remoto}\' -Force"'
    )
    _, err, code = executar_remoto(client, unzip_cmd)
    if code != 0:
        print(f"✖ Falha ao descompactar Win11Debloat remotamente: {err}")
        return None

    log_remoto = f"{REMOTE_SCRIPT_DIR}\\debloat.log"
    log_remoto_norm = log_remoto.replace("\\", "/")
    script_remoto = f"{debloat_dir_remoto}\\Win11Debloat.ps1"

    # Limpa log anterior
    executar_remoto(
        client,
        f'{PS_PREFIX} -Command "Remove-Item \'{log_remoto}\' -Force -ErrorAction SilentlyContinue"',
    )

    comando = (
        f'{PS_PREFIX} -Command "& \'{script_remoto}\' {switches} *> \'{log_remoto}\'"'
    )
    print(f"⏳ Executando Win11Debloat ({switches}) remotamente via PowerShell...")

    transport = client.get_transport()
    channel = transport.open_session()
    channel.exec_command(comando)

    sftp = client.open_sftp()
    pos = 0
    while not channel.exit_status_ready():
        time.sleep(3)
        try:
            with sftp.open(log_remoto_norm, "rb") as f:
                f.seek(pos)
                novos_bytes = f.read()
                if novos_bytes:
                    pos += len(novos_bytes)
                    texto = novos_bytes.decode("utf-16le", errors="replace")
                    sys.stdout.write(texto)
                    sys.stdout.flush()
        except IOError:
            pass

    try:
        with sftp.open(log_remoto_norm, "rb") as f:
            f.seek(pos)
            sobra = f.read()
            if sobra:
                texto = sobra.decode("utf-16le", errors="replace")
                sys.stdout.write(texto)
                sys.stdout.flush()
    except IOError:
        pass
    sftp.close()

    codigo = channel.recv_exit_status()
    if codigo != 0:
        print(f"✖ Desbloat falhou (exit {codigo}).")
        return None

    print(f"✔ Desbloat concluído — log remoto: {log_remoto}")
    return log_remoto


def main():
    parser = argparse.ArgumentParser(description="Projeto Bancada — orquestrador")
    parser.add_argument("--host", required=True, help="IP/hostname da máquina alvo")
    parser.add_argument("--usuario", required=True, help="Usuário da máquina alvo")
    parser.add_argument(
        "--chave",
        default=os.path.expanduser("~/.ssh/id_ed25519"),
        help="Caminho da chave privada SSH",
    )
    parser.add_argument("--cliente", help="Nome do cliente (obrigatório para inventário/manifesto)")
    parser.add_argument(
        "--destino",
        help="UNC do storage central (ex: \\\\nas\\Bancada\\CLIENTE). Sem este flag, pula backup.",
    )
    parser.add_argument(
        "--saida",
        help="Caminho alternativo do manifesto (padrão: manifests/).",
    )
    parser.add_argument(
        "--pos",
        choices=["completa", "ajustes", "sem-runtimes", "sem-apps"],
        help="Executa pós-instalação no modo especificado",
    )
    parser.add_argument(
        "--debloat",
        choices=["completo", "lite"],
        nargs="?",
        const="completo",
        help="Executa Win11Debloat (completo ou lite)",
    )
    args = parser.parse_args()

    data = datetime.date.today().isoformat()

    print(f"⏳ Conectando a {args.host} como {args.usuario}...")
    client = conectar(args.host, args.usuario, args.chave)
    try:
        if args.pos:
            print(f"⏳ Iniciando etapa de pós-instalação (modo: {args.pos})...")
            log = executar_pos_instalacao(client, args.pos)
            if not log:
                print("✖ Pós-instalação falhou.")
                return 1

        if args.debloat:
            switches = (
                "-RunDefaults -Silent -CreateRestorePoint"
                if args.debloat == "completo"
                else "-RunDefaultsLite -Silent -CreateRestorePoint"
            )
            print(f"⏳ Iniciando etapa de debloat (modo: {args.debloat})...")
            log = executar_debloat(client, switches)
            if not log:
                print("✖ Debloat falhou.")
                return 1

        if args.cliente:
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