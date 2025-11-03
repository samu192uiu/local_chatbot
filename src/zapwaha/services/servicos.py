# services/servicos.py
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Catálogo padrão (fallback se o JSON não existir)
_DEFAULT = {
    "moeda": "BRL",
    "servicos": [
        {"id": "osteopatia",   "nome": "Osteopatia",   "preco": 300.0, "unidade": "sessão", "agendavel": True},
        {"id": "fisioterapia", "nome": "Fisioterapia", "preco": 200.0, "unidade": "sessão", "agendavel": True},
        {"id": "acupuntura",   "nome": "Acupuntura",   "preco": 250.0, "unidade": "sessão", "agendavel": True},
        {"id": "pilates",      "nome": "Pilates",      "preco": None,  "unidade": "aula",   "agendavel": True,
         "observacao": "Preço definido na clínica ou por plano"}
    ]
}

def _candidates() -> List[Path]:
    """Locais onde procurar o JSON (em ordem)."""
    env = os.getenv("SERVICOS_JSON")
    paths = []
    if env:
        paths.append(Path(env))
    paths += [
        Path("/app/config/servicos.json"),
        Path("/app/services/servicos.json"),
        Path("./config/servicos.json"),
        Path("./services/servicos.json"),
    ]
    return paths

_catalogo_cache: Dict[str, Any] | None = None

def get_catalogo() -> Dict[str, Any]:
    global _catalogo_cache
    if _catalogo_cache is not None:
        return _catalogo_cache
    for p in _candidates():
        try:
            if p.exists():
                _catalogo_cache = json.loads(p.read_text(encoding="utf-8"))
                return _catalogo_cache
        except Exception:
            pass
    _catalogo_cache = _DEFAULT
    return _catalogo_cache

def lista_servicos() -> List[Dict[str, Any]]:
    return list(get_catalogo().get("servicos", []))

def get_servico_by_id(sid: str) -> Optional[Dict[str, Any]]:
    for s in lista_servicos():
        if s.get("id") == sid:
            return s
    return None

def preco_por_servico_id(sid: str) -> Optional[float]:
    s = get_servico_by_id(sid)
    return None if not s else s.get("preco")

def is_aula(sid: str) -> bool:
    s = get_servico_by_id(sid)
    return bool(s and (s.get("unidade") or "").lower() == "aula")

def _fmt_brl(v: Optional[float]) -> str:
    if v is None:
        return "preço sob consulta"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def format_menu() -> str:
    """
    Retorna um menu amigável para WhatsApp:
    1) Osteopatia — R$ 300,00 por sessão
    ...
    """
    itens = []
    for i, s in enumerate(lista_servicos(), 1):
        nome = s.get("nome", "Serviço")
        preco = _fmt_brl(s.get("preco"))
        un = s.get("unidade") or "sessão"
        if s.get("preco") is None:
            linha = f"{i}) {nome} — {preco}"
        else:
            linha = f"{i}) {nome} — {preco} por {un}"
        itens.append(linha)
    rodape = "Responda com o número do serviço."
    return "🧾 *Serviços*\n" + "\n".join(itens) + "\n\n" + rodape

def map_choice_to_id(choice: str) -> Optional[str]:
    """'1' → 'osteopatia', etc."""
    if not choice or not choice.isdigit():
        return None
    idx = int(choice) - 1
    servs = lista_servicos()
    if 0 <= idx < len(servs):
        return servs[idx].get("id")
    return None
