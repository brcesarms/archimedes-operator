"""Testes das funções puras do orquestrador (Projeto Bancada).

Rodar com o ambiente virtual ativo:
    source .venv/bin/activate
    pytest tests/ -v
"""
import os
import sys
import tempfile

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "scripts", "python")
)

from orquestrador import gerar_manifesto, parse_json_saida


# ── parse_json_saida ──────────────────────────────────────────


def test_parse_json_valido():
    saida = '{"hostname": "DESKTOP-X", "usuarios": ["bruno"]}'
    assert parse_json_saida(saida, "inventario") == {
        "hostname": "DESKTOP-X",
        "usuarios": ["bruno"],
    }


def test_parse_json_lista():
    saida = '[{"usuario": "bruno", "pasta": "Desktop", "codigo": 0}]'
    assert parse_json_saida(saida, "backup") == [
        {"usuario": "bruno", "pasta": "Desktop", "codigo": 0}
    ]


def test_parse_json_vazio_retorna_none():
    assert parse_json_saida("", "inventario") is None


def test_parse_json_invalido_retorna_none():
    assert parse_json_saida("isto nao eh json", "inventario") is None


# ── gerar_manifesto ───────────────────────────────────────────


def _inventario_base():
    return {
        "hostname": "DESKTOP-X",
        "windows": "Microsoft Windows 11 Pro",
        "versao": "10.0.26200",
        "chave_oem": "",
        "usuarios": ["bruno"],
        "softwares": [{"nome": "VLC", "versao": "3.0.21"}],
    }


def test_gerar_manifesto_cria_arquivo():
    with tempfile.TemporaryDirectory() as tmp:
        caminho = gerar_manifesto(
            _inventario_base(),
            [],
            "Cliente Teste",
            "2026-09-11",
            os.path.join(tmp, "M.md"),
        )
        assert caminho is not None
        assert os.path.exists(caminho)


def test_manifesto_pasta_inexistente_marca_como_nao_copiada():
    """Regressão do bug: codigo == -1 deve aparecer como ☐ (não ✅)."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = os.path.join(tmp, "M.md")
        status = [
            {
                "usuario": "bruno",
                "pasta": "Desktop",
                "codigo": -1,
                "obs": "pasta_inexistente",
            }
        ]
        gerar_manifesto(_inventario_base(), status, "Cliente Teste", "2026-09-11", saida)
        texto = open(saida, encoding="utf-8").read()
        assert "☐" in texto
        assert "| `bruno/Desktop` | ☐ | code=-1" in texto
        assert "| `bruno/Desktop` | ✅" not in texto


def test_manifesto_pasta_ok_com_origem():
    """Coluna origem (local|onedrive) deve aparecer na linha de status."""
    with tempfile.TemporaryDirectory() as tmp:
        saida = os.path.join(tmp, "M.md")
        status = [
            {"usuario": "bruno", "pasta": "Documents", "codigo": 0, "origem": "local"}
        ]
        gerar_manifesto(_inventario_base(), status, "Cliente Teste", "2026-09-11", saida)
        texto = open(saida, encoding="utf-8").read()
        assert "origem=local" in texto
        assert "| `bruno/Documents` | ✅ |" in texto


def test_manifesto_sem_backup():
    with tempfile.TemporaryDirectory() as tmp:
        saida = os.path.join(tmp, "M.md")
        gerar_manifesto(_inventario_base(), [], "Cliente Teste", "2026-09-11", saida)
        texto = open(saida, encoding="utf-8").read()
        assert "Backup não executado ou sem dados" in texto


def test_manifesto_lista_softwares():
    with tempfile.TemporaryDirectory() as tmp:
        saida = os.path.join(tmp, "M.md")
        gerar_manifesto(_inventario_base(), [], "Cliente Teste", "2026-09-11", saida)
        texto = open(saida, encoding="utf-8").read()
        assert "VLC 3.0.21" in texto