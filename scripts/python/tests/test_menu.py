"""Testes do menu interativo do Projeto Bancada."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import menu
import orquestrador


def test_parse_etapas_normal():
    assert menu.parse_etapas("1,2,3") == [1, 2, 3]


def test_parse_etapas_tudo():
    assert menu.parse_etapas("tudo") == [1, 2, 3]
    assert menu.parse_etapas("T") == [1, 2, 3]
    assert menu.parse_etapas("*") == [1, 2, 3]


def test_parse_etapas_default_vazio():
    assert menu.parse_etapas("") == [1, 2, 3]


def test_parse_etapas_fora_de_ordem():
    assert menu.parse_etapas("3,1") == [1, 3]
    assert menu.parse_etapas("2,1") == [1, 2]


def test_parse_etapas_so_pos_instalacao():
    assert menu.parse_etapas("4") == [4]


def test_parse_etapas_ignora_invalidos():
    assert menu.parse_etapas("99,2") == [2]
    assert menu.parse_etapas("99,abc") == [1, 2, 3]


def test_parse_etapas_ignora_vazios():
    assert menu.parse_etapas("1,,3") == [1, 3]


def test_expandir_manifesto_implica_inventario():
    assert menu.expandir_etapas([3]) == [1, 3]
    assert menu.expandir_etapas([2, 3]) == [1, 2, 3]


def test_expandir_nao_afeta_sem_manifesto():
    assert menu.expandir_etapas([4]) == [4]
    assert menu.expandir_etapas([2]) == [2]


def test_expandir_idempotente():
    assert menu.expandir_etapas([1, 2, 3, 4]) == [1, 2, 3, 4]


def test_modos_pos_switches():
    assert orquestrador.montar_switches_pos("completa") == ""
    assert orquestrador.montar_switches_pos("ajustes") == " -SkipApps -SkipRuntimes"
    assert orquestrador.montar_switches_pos("sem-runtimes") == " -SkipRuntimes"
    assert orquestrador.montar_switches_pos("sem-apps") == " -SkipApps"


def test_modo_pos_invalido():
    try:
        orquestrador.montar_switches_pos("invalido")
        assert False, "deveria levantar ValueError"
    except ValueError as e:
        assert "inválido" in str(e)