# iDrugs — Feature Frete + Endereço estruturado

Implementação da regra simplificada de distância/frete/tempo entre farmácia e
cliente, com cascata Estado → Cidade → Bairro (CE / Juazeiro do Norte).

## Arquivos entregues

| Arquivo | O que é | Onde vai |
|---|---|---|
| `migration_frete.sql` | Migração idempotente (novas colunas em `farmacias` e `clientes`) | rodar no Postgres `idrugs` |
| `frete.py` | **Função única** `calcular_frete(...)` + catálogo de bairros + rotas auxiliares Flask | raiz do projeto (mesma pasta de `app.py`) |
| `static/js/bairros.js` | Catálogo + cascata + cálculo no front + helper de card | `static/js/bairros.js` |
| `patches/app.py.patch.md` | Onde editar o `app.py` | guia de colagem |
| `patches/cadastro.py.patch.md` | Onde editar o `cadastro.py` | guia de colagem |
| `patches/colaborador.html.patch.md` | Onde editar o painel do colaborador | guia de colagem |
| `patches/index.html.patch.md` | Onde editar o app do cliente | guia de colagem |

> Os arquivos HTML originais têm 1.877 e 2.679 linhas. Reescrever os dois
> inteiros aumenta o risco de quebrar funcionalidades já prontas. Por isso a
> entrega é em forma de patches cirúrgicos + módulos novos isolados.

## Regra de frete (centralizada em `frete.py` e `bairros.js`)

| Situação | Distância | Tempo | Frete |
|---|---|---|---|
| Mesmo bairro | 1 km | 15 min | R$ 0,00 (Grátis) |
| Mesma região (CENTRAL/NORTE/SUL/OESTE/LESTE) | 3 km | 20 min | R$ 4,99 |
| Regiões diferentes (em Juazeiro) | 7 km | 30 min | R$ 8,99 |
| Farmácia fora de Juazeiro do Norte | — | — | 🚚 Frete sob encomenda |

## Passo a passo

1. **Banco**: `psql -d idrugs -f migration_frete.sql`
2. Copiar `frete.py` para a raiz do projeto.
3. Copiar `static/js/bairros.js` para `static/js/`.
4. Aplicar os 4 patches (guias em `patches/`).
5. Reiniciar Flask, abrir o app, cadastrar/editar farmácia e cliente
   selecionando Estado → Cidade → Bairro.

## Componentes / telas alteradas

- **Cadastro de Farmácia** (`colaborador.html`) — cascata
- **Editar Farmácia** (`colaborador.html`) — cascata pré-preenchida
- **Cadastro de Cliente** (`index.html`) — cascata
- **Editar Endereço do Cliente** (`index.html`) — cascata pré-preenchida
- **Dashboard do Cliente** — cards no formato do wireframe (📍 🚚 🕒)
- **Tela da Farmácia** — Estado, Cidade, Bairro, Região, Distância, Frete, Tempo
- **Checkout** — Subtotal / Frete / Tempo / Total

## Função única reutilizada em todo o sistema

Backend: `frete.calcular_frete(farm_cidade, farm_bairro, cli_cidade, cli_bairro)`
Front:   `IDRUGS.calcularFrete(farmCidade, farmBairro, cliCidade, cliBairro)`

Ambas retornam o mesmo shape (`frete_label`, `distancia_label`, `tempo_label`,
`sob_encomenda`, `regiao_farmacia`, …).

## Endpoints auxiliares criados (via `register_frete_routes`)

- `GET  /api/localidades/estados`
- `GET  /api/localidades/cidades?estado=CE`
- `GET  /api/localidades/bairros?cidade=Juazeiro%20do%20Norte`
- `POST /api/frete/calcular`

## Checklist

- ✅ Estados carregam (somente CE)
- ✅ Cidades carregam (somente Juazeiro do Norte)
- ✅ Bairros aparecem só para Juazeiro do Norte (agrupados por região)
- ✅ Frete calculado por região (mesmo bairro / mesma região / regiões diferentes)
- ✅ Distância exibida no dashboard
- ✅ Tempo exibido no dashboard
- ✅ Cards seguem o wireframe (📍 distância • 🚚 frete • 🕒 tempo)
- ✅ Farmácias fora de Juazeiro exibem "🚚 Frete sob encomenda"
