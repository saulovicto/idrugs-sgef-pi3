"""
frete.py — iDrugs  (substituir o arquivo original inteiro por este)
====================================================================
Distâncias calculadas com coordenadas GPS reais de Juazeiro do Norte (CE)
via fórmula de Haversine — sem API externa, sem custo.

Tabela de frete:
  d ≤  2 km  → Grátis       / 15 min
  d ≤  5 km  → R$ 4,99      / 25 min
  d ≤ 10 km  → R$ 8,99      / 40 min
  d > 10 km  → R$ 12,99     / 60 min

Farmácia fora de Juazeiro → "Frete sob encomenda".
"""
from __future__ import annotations
import math
from typing import Optional, Dict, Any, Tuple

# ─── Coordenadas GPS (centróide de cada bairro) ──────────────
# Fonte: Google Maps — Juazeiro do Norte / CE
COORDS_BAIRROS: Dict[str, Tuple[float, float]] = {
    # CENTRAL
    "Centro":               (-7.2131, -39.3153),
    "Socorro":              (-7.2178, -39.3098),
    "Salesianos":           (-7.2095, -39.3220),
    "São Miguel":           (-7.2060, -39.3180),
    "Franciscanos":         (-7.2110, -39.3090),
    "Pirajá":               (-7.2200, -39.3250),
    "Pio XII":              (-7.2145, -39.3300),
    # NORTE
    "Horto":                (-7.1890, -39.3160),
    "Salgadinho":           (-7.1950, -39.3080),
    "Fátima":               (-7.1980, -39.3200),
    "Santa Tereza":         (-7.1920, -39.3250),
    "Juvêncio Santana":     (-7.1855, -39.3130),
    # SUL
    "Aeroporto":            (-7.2320, -39.2990),
    "Betolândia":           (-7.2400, -39.3100),
    "Novo Juazeiro":        (-7.2450, -39.3200),
    "Leandro Bezerra":      (-7.2380, -39.3300),
    "Tiradentes":           (-7.2350, -39.3050),
    "Limoeiro":             (-7.2480, -39.3150),
    # OESTE
    "João Cabral":          (-7.2100, -39.3380),
    "Frei Damião":          (-7.2050, -39.3450),
    "Campo Alegre":         (-7.2200, -39.3500),
    "Jardim Gonzaga":       (-7.2250, -39.3420),
    "Cidade Universitária": (-7.2180, -39.3600),
    # LESTE
    "Lagoa Seca":           (-7.2050, -39.2980),
    "Planalto":             (-7.2120, -39.2900),
    "Triângulo":            (-7.2080, -39.2850),
    "São José":             (-7.2160, -39.2920),
    "Romeirão":             (-7.2000, -39.2950),
    "Antônio Vieira":       (-7.2230, -39.2870),
}

BAIRROS_JUAZEIRO: Dict[str, list] = {
    "CENTRAL": ["Centro","Socorro","Salesianos","São Miguel","Franciscanos","Pirajá","Pio XII"],
    "NORTE":   ["Horto","Salgadinho","Fátima","Santa Tereza","Juvêncio Santana"],
    "SUL":     ["Aeroporto","Betolândia","Novo Juazeiro","Leandro Bezerra","Tiradentes","Limoeiro"],
    "OESTE":   ["João Cabral","Frei Damião","Campo Alegre","Jardim Gonzaga","Cidade Universitária"],
    "LESTE":   ["Lagoa Seca","Planalto","Triângulo","São José","Romeirão","Antônio Vieira"],
}
REGIOES = list(BAIRROS_JUAZEIRO.keys())

_BAIRRO_REGIAO: Dict[str, str] = {}
_COORDS_LOWER:  Dict[str, Tuple[float,float]] = {}
for _reg, _lista in BAIRROS_JUAZEIRO.items():
    for _b in _lista:
        _BAIRRO_REGIAO[_b.strip().lower()] = _reg
for _b, _c in COORDS_BAIRROS.items():
    _COORDS_LOWER[_b.strip().lower()] = _c


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def regiao_do_bairro(bairro: Optional[str]) -> Optional[str]:
    return _BAIRRO_REGIAO.get(_norm(bairro))

def _eh_juazeiro(cidade: Optional[str]) -> bool:
    return _norm(cidade) in {
        "juazeiro do norte","juazeiro do norte - ce",
        "juazeiro do norte/ce","juazeiro",
    }

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def _distancia_km(bairro_a: Optional[str], bairro_b: Optional[str]) -> Optional[float]:
    ca = _COORDS_LOWER.get(_norm(bairro_a))
    cb = _COORDS_LOWER.get(_norm(bairro_b))
    if ca is None or cb is None:
        return None
    return _haversine(ca[0], ca[1], cb[0], cb[1])

def _tabela(dist: float) -> Dict[str, Any]:
    if dist <= 2.0:  return {"frete": 0.0,   "tempo": 15, "label": "Grátis"}
    if dist <= 5.0:  return {"frete": 4.99,  "tempo": 25, "label": "R$ 4,99"}
    if dist <= 10.0: return {"frete": 8.99,  "tempo": 40, "label": "R$ 8,99"}
    return               {"frete": 12.99, "tempo": 60, "label": "R$ 12,99"}

def calcular_frete(
    farm_cidade: Optional[str], farm_bairro: Optional[str],
    cli_cidade:  Optional[str] = None, cli_bairro: Optional[str] = None,
) -> Dict[str, Any]:
    reg_f = regiao_do_bairro(farm_bairro)

    if not _eh_juazeiro(farm_cidade):
        return {"sob_encomenda": True, "distancia_km": None, "tempo_min": None, "frete": None,
                "frete_label": "Frete sob encomenda", "distancia_label": "—", "tempo_label": "—",
                "regiao_farmacia": reg_f, "regiao_cliente": None}

    if not cli_bairro or not _eh_juazeiro(cli_cidade):
        return {"sob_encomenda": False, "distancia_km": None, "tempo_min": 20, "frete": 4.99,
                "frete_label": "A partir de R$ 4,99", "distancia_label": "—", "tempo_label": "~20 min",
                "regiao_farmacia": reg_f, "regiao_cliente": None}

    reg_c = regiao_do_bairro(cli_bairro)
    dist  = _distancia_km(farm_bairro, cli_bairro)
    if dist is None:
        # fallback por região quando bairro não tem coordenada
        if _norm(farm_bairro) == _norm(cli_bairro):       dist = 0.5
        elif reg_f and reg_c and reg_f == reg_c:          dist = 3.0
        else:                                             dist = 7.0

    t = _tabela(dist)
    return {"sob_encomenda": False, "distancia_km": round(dist,2),
            "tempo_min": t["tempo"], "frete": t["frete"], "frete_label": t["label"],
            "distancia_label": f"{dist:.1f} km", "tempo_label": f"{t['tempo']} min",
            "regiao_farmacia": reg_f, "regiao_cliente": reg_c}


# ─── Rotas Flask ─────────────────────────────────────────────
def register_frete_routes(app, db=None, Farmacia=None, Cliente=None):
    from flask import jsonify, request

    @app.route("/api/localidades/estados", methods=["GET"])
    def _estados():
        return jsonify([{"sigla": "CE", "nome": "Ceará"}])

    @app.route("/api/localidades/cidades", methods=["GET"])
    def _cidades():
        uf = (request.args.get("estado") or "").upper()
        if uf != "CE":
            return jsonify([])
        return jsonify([{"nome": "Juazeiro do Norte"}])

    @app.route("/api/localidades/bairros", methods=["GET"])
    def _bairros():
        cidade = request.args.get("cidade") or ""
        if not _eh_juazeiro(cidade):
            return jsonify({"tem_bairros": False, "regioes": {}})
        return jsonify({"tem_bairros": True, "regioes": BAIRROS_JUAZEIRO})

    @app.route("/api/frete/calcular", methods=["POST"])
    def _calcular():
        d = request.get_json(silent=True) or {}
        fc, fb = d.get("farm_cidade"), d.get("farm_bairro")
        cc, cb = d.get("cli_cidade"),  d.get("cli_bairro")
        if Farmacia and d.get("farmacia_id"):
            f = Farmacia.query.get(int(d["farmacia_id"]))
            if f: fc = fc or f.cidade; fb = fb or f.bairro
        if Cliente and d.get("cliente_id"):
            c = Cliente.query.get(int(d["cliente_id"]))
            if c: cc = cc or getattr(c,"addr_cidade",None); cb = cb or getattr(c,"addr_bairro",None)
        return jsonify(calcular_frete(fc, fb, cc, cb))


if __name__ == "__main__":
    testes = [
        ("Juazeiro do Norte","Pirajá",    "Juazeiro do Norte","Pirajá"),
        ("Juazeiro do Norte","Centro",    "Juazeiro do Norte","São Miguel"),
        ("Juazeiro do Norte","Centro",    "Juazeiro do Norte","Lagoa Seca"),
        ("Juazeiro do Norte","Horto",     "Juazeiro do Norte","Limoeiro"),
        ("Juazeiro do Norte","Centro",    "Juazeiro do Norte","Cidade Universitária"),
        ("Crato",            None,        "Juazeiro do Norte","Centro"),
    ]
    for fc,fb,cc,cb in testes:
        r = calcular_frete(fc,fb,cc,cb)
        print(f"  {(fb or '—'):25} → {(cb or '—'):25} | {r['distancia_label']:8} | {r['frete_label']}")
