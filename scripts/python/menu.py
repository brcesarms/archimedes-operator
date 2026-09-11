#!/usr/bin/env python3
"""Menu interativo do Projeto Bancada — escolha o que fazer.

Camada opcional sobre o orquestrador.py: o fluxo headless continua intacto
para automação; o menu apenas coleta dados e chama as mesmas funções do motor.

Uso:
    python3 menu.py
"""
import datetime
import os
import sys

# Permite importar orquestrador.py do mesmo diretório
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import orquestrador as bd  # noqa: E402

ETAPAS = {
    1: (
        "📊 Inventário Técnico",
        "Mapeia perfis em C:\\Users, softwares instalados e extrai a chave OEM da BIOS.",
    ),
    2: (
        "💾 Backup Forense (Robocopy)",
        "Copia Desktop, Documentos, Downloads e Fotos para o storage central (com suporte a OneDrive).",
    ),
    3: (
        "📋 Manifesto Markdown",
        "Gera o checklist para o Obsidian com status de cópia e lista de apps a reinstalar.",
    ),
    4: (
        "🪟 Pós-Instalação Completo",
        "Aplica ajustes de energia/privacidade e instala 10 apps essenciais + 19 runtimes via winget.",
    ),
    5: (
        "🧹 Desbloat Windows 11 (Opcional pós-formatação)",
        "Remove bloatware, telemetria e widgets usando o Win11Debloat com ponto de restauração.",
    ),
}

MODOS_POS = {
    "c": ("completa", "Completa (ajustes + apps + runtimes)", False, False),
    "a": ("ajustes", "Só ajustes (pular apps e runtimes)", True, True),
    "s": ("sem-runtimes", "Sem runtimes (ajustes + apps)", False, True),
    "r": ("sem-apps", "Sem apps (ajustes + runtimes)", True, False),
}

DEFAULT_ETAPAS = "1,2,3"


def render_painel():
    """Gera a string do painel de operações com opções e descrições."""
    linhas = [
        "=" * 66,
        "🏛️ PROJETO BANCADA — PAINEL DE OPERAÇÕES",
        "=" * 66,
        "",
        "Etapas disponíveis:",
    ]
    for num, (titulo, desc) in ETAPAS.items():
        linhas.append(f"\n  [{num}] {titulo}")
        linhas.append(f"      └── {desc}")
    linhas.append("\n" + "=" * 66)
    return "\n".join(linhas)


def exibir_painel_inicial():
    """Exibe o painel de boas-vindas com todas as etapas e descrições."""
    print(render_painel())


def parse_etapas(entrada, default=DEFAULT_ETAPAS):
    """Normaliza a escolha de etapas para lista ordenada de inteiros [1..5].

    - vazio/"tudo"/"T"/"*" → default
    - "3,1" → [1, 3] (ordena e remove duplicados)
    - inválidos (99, abc) são ignorados; se nada sobrar → default
    """
    texto = (entrada or "").strip().lower()
    if not texto or texto in ("tudo", "t", "*"):
        return sorted({int(p) for p in default.split(",")})
    numeros = []
    for parte in texto.split(","):
        parte = parte.strip()
        if parte.isdigit():
            n = int(parte)
            if 1 <= n <= 5:
                numeros.append(n)
    if not numeros:
        return sorted({int(p) for p in default.split(",")})
    return sorted(set(numeros))


def expandir_etapas(etapas):
    """Garante dependências: manifesto (3) exige inventário (1)."""
    result = set(etapas)
    if 3 in result:
        result.add(1)
    return sorted(result)


def perguntar(texto, default=""):
    """input() exibindo o default; Enter assume o default."""
    sufixo = f" [{default}]" if default else ""
    valor = input(f"{texto}{sufixo}: ").strip()
    return valor or default


def escolher_modo_pos():
    """Pergunta o modo da pós-instalação e retorna a chave do modo."""
    print("\nModo da pós-instalação:")
    for chave, (_, desc, _, _) in MODOS_POS.items():
        print(f"  [{chave.upper()}] {desc}")
    while True:
        escolha = input("Modo [C]: ").strip().lower() or "c"
        if escolha in MODOS_POS:
            return MODOS_POS[escolha][0]
        print("✖ Opção inválida. Use C, A, S ou R.")


def executar():
    exibir_painel_inicial()

    escolha = input(
        f"\nEscolha as etapas (ex: 1,2,3,4,5 — Enter = {DEFAULT_ETAPAS}): "
    ).strip()
    etapas = expandir_etapas(parse_etapas(escolha))

    modo_pos = None
    if 4 in etapas:
        modo_pos = escolher_modo_pos()

    if not etapas:
        print("✖ Nenhuma etapa para executar.")
        return 1

    print("\n--- 🔌 Configuração da Conexão ---")
    host = perguntar("Host", "10.0.0.217")
    usuario = perguntar("Usuário", "brces")
    chave = perguntar("Chave SSH", os.path.expanduser("~/.ssh/id_ed25519"))

    cliente = ""
    if 3 in etapas or 2 in etapas:
        cliente = perguntar("Cliente")
        if not cliente:
            print("✖ Cliente é obrigatório para manifesto/backup.")
            return 1
    else:
        cliente = perguntar("Cliente (opcional)", "BANCADA")

    destino = ""
    if 2 in etapas:
        destino = perguntar("Destino backup (vazio = pula)")
        if not destino:
            print("\n⚠ Destino vazio — etapa de backup será pulada.")
            etapas = [e for e in etapas if e != 2]

    if not etapas:
        print("✖ Nenhuma etapa restante para executar.")
        return 1

    data = datetime.date.today().isoformat()
    print(f"\n⏳ Conectando a {host} como {usuario}...")

    client = bd.conectar(host, usuario, chave)
    try:
        inventario = None
        status = {}
        manifesto = None
        log_pos = None
        log_debloat = None

        for etapa in etapas:
            if etapa == 1:
                inventario = bd.coletar_inventario(client)
                if inventario is None:
                    print("✖ Inventário falhou — abortando.")
                    return 1
            elif etapa == 2:
                status = bd.executar_backup(client, destino)
                if status is None:
                    print("⚠ Backup falhou — manifesto sem status de cópia.")
                    status = {}
            elif etapa == 3:
                if inventario is None:
                    print("✖ Manifesto exige inventário — abortando.")
                    return 1
                manifesto = bd.gerar_manifesto(inventario, status, cliente, data)
                if manifesto is None:
                    return 1
            elif etapa == 4:
                log_pos = bd.executar_pos_instalacao(client, modo_pos)
                if log_pos is None:
                    print("⚠ Pós-instalação falhou (sem log).")
            elif etapa == 5:
                log_debloat = bd.executar_debloat(client)
                if log_debloat is None:
                    print("⚠ Desbloat falhou (sem log).")

        print("\n🎯 Resumo:")
        print(f"  ✅ Etapas executadas: {', '.join(str(e) for e in etapas)}")
        if manifesto:
            print(f"  📄 Manifesto: {manifesto}")
        if log_pos:
            print(f"  🪟 Log pós-instalação: {log_pos}")
        if log_debloat:
            print(f"  🧹 Log debloat: {log_debloat}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(executar())