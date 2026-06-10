/**
 * bairros.js — iDrugs
 * ====================
 * Catálogo de bairros de Juazeiro do Norte + cascata Estado→Cidade→Bairro
 * + cálculo de frete no front (mesmo shape que frete.py no back)
 *
 * Expõe o objeto global window.IDRUGS com:
 *   IDRUGS.BAIRROS_JUAZEIRO   — catálogo por região
 *   IDRUGS.ligarCascata(opts) — inicializa selects em cascata
 *   IDRUGS.calcularFrete(...)  — calcula frete igual ao back
 *   IDRUGS.renderInfoFrete(info) — HTML do card de frete
 */

(function (global) {
  'use strict';

  // ─────────────────────────────────────────────────────────────
  // CATÁLOGO DE BAIRROS — espelho de frete.py
  // ─────────────────────────────────────────────────────────────
  const BAIRROS_JUAZEIRO = {
    CENTRAL: ['Centro', 'Socorro', 'Salesianos', 'São Miguel',
              'Franciscanos', 'Pirajá', 'Pio XII'],
    NORTE:   ['Horto', 'Salgadinho', 'Fátima', 'Santa Tereza',
              'Juvêncio Santana'],
    SUL:     ['Aeroporto', 'Betolândia', 'Novo Juazeiro',
              'Leandro Bezerra', 'Tiradentes', 'Limoeiro'],
    OESTE:   ['João Cabral', 'Frei Damião', 'Campo Alegre',
              'Jardim Gonzaga', 'Cidade Universitária'],
    LESTE:   ['Lagoa Seca', 'Planalto', 'Triângulo', 'São José',
              'Romeirão', 'Antônio Vieira'],
  };

  // índice reverso normalizado → região
  const _bairroRegiao = {};
  for (const [reg, lista] of Object.entries(BAIRROS_JUAZEIRO)) {
    for (const b of lista) {
      _bairroRegiao[b.trim().toLowerCase()] = reg;
    }
  }

  function _norm(s) { return (s || '').trim().toLowerCase(); }

  function _ehJuazeiro(cidade) {
    const c = _norm(cidade);
    return c === 'juazeiro do norte'
        || c === 'juazeiro do norte - ce'
        || c === 'juazeiro do norte/ce';
  }

  function regiaoDosBairro(bairro) {
    return _bairroRegiao[_norm(bairro)] || null;
  }

  // ─────────────────────────────────────────────────────────────
  // CÁLCULO DE FRETE (mesmo shape que frete.py)
  // ─────────────────────────────────────────────────────────────
  function _resultado(km, min, valor, regF, regC) {
    let label;
    if (valor <= 0) {
      label = 'Grátis';
    } else {
      label = 'R$ ' + valor.toFixed(2).replace('.', ',');
    }
    return {
      sob_encomenda:    false,
      distancia_km:     km,
      tempo_min:        min,
      frete:            valor,
      frete_label:      label,
      distancia_label:  km + ' km',
      tempo_label:      min + ' min',
      regiao_farmacia:  regF,
      regiao_cliente:   regC,
    };
  }

  function calcularFrete(farmCidade, farmBairro, cliCidade, cliBairro) {
    // Farmácia fora de Juazeiro
    if (!_ehJuazeiro(farmCidade)) {
      return {
        sob_encomenda:   true,
        distancia_km:    null, tempo_min: null, frete: null,
        frete_label:     'Frete sob encomenda',
        distancia_label: '—', tempo_label: '—',
        regiao_farmacia: null, regiao_cliente: null,
      };
    }

    const regF = regiaoDosBairro(farmBairro);

    // Sem endereço do cliente
    if (!cliBairro || !_ehJuazeiro(cliCidade)) {
      return {
        sob_encomenda:   false,
        distancia_km:    3, tempo_min: 20, frete: 4.99,
        frete_label:     'A partir de R$ 4,99',
        distancia_label: '~3 km', tempo_label: '~20 min',
        regiao_farmacia: regF, regiao_cliente: null,
      };
    }

    const regC = regiaoDosBairro(cliBairro);

    if (_norm(farmBairro) === _norm(cliBairro)) return _resultado(1, 15, 0.0,  regF, regC);
    if (regF && regC && regF === regC)           return _resultado(3, 20, 4.99, regF, regC);
    return                                              _resultado(7, 30, 8.99, regF, regC);
  }

  // ─────────────────────────────────────────────────────────────
  // RENDER DE CARD DE FRETE (usado no index.html)
  // ─────────────────────────────────────────────────────────────
  function renderInfoFrete(info) {
    if (!info) return '';
    if (info.sob_encomenda) {
      return `<div class="frete-info sob-encomenda">🚚 Frete sob encomenda</div>`;
    }
    return `<div class="frete-info">
      📍 ${info.distancia_label || '—'} &nbsp;·&nbsp;
      🚚 ${info.frete_label || '—'} &nbsp;·&nbsp;
      🕒 ${info.tempo_label || '—'}
    </div>`;
  }

  // ─────────────────────────────────────────────────────────────
  // CASCATA ESTADO → CIDADE → BAIRRO
  // ─────────────────────────────────────────────────────────────
  /**
   * ligarCascata(opts)
   *
   * opts = {
   *   estadoEl,      // <select> de estado
   *   cidadeEl,      // <select> de cidade
   *   bairroEl,      // <select> de bairro
   *   bairroWrapEl,  // elemento pai do select de bairro (pode ser null)
   *   valoresIniciais: { estado, cidade, bairro } | null
   * }
   */
  function ligarCascata({ estadoEl, cidadeEl, bairroEl, bairroWrapEl, valoresIniciais }) {
    if (!estadoEl || !cidadeEl) return;

    // ── Popula estados ────────────────────────────────────────
    function popularEstados(valorPre) {
      estadoEl.innerHTML = '<option value="">Selecione o estado</option>';
      const estados = [{ sigla: 'CE', nome: 'Ceará' }];
      for (const { sigla, nome } of estados) {
        const opt = document.createElement('option');
        opt.value = sigla;
        opt.textContent = nome;
        if (valorPre && valorPre.toUpperCase() === sigla) opt.selected = true;
        estadoEl.appendChild(opt);
      }
    }

    // ── Popula cidades ────────────────────────────────────────
    function popularCidades(uf, valorPre) {
      cidadeEl.innerHTML = '<option value="">Selecione a cidade</option>';
      cidadeEl.disabled = !uf;
      if (uf && uf.toUpperCase() === 'CE') {
        const opt = document.createElement('option');
        opt.value = 'Juazeiro do Norte';
        opt.textContent = 'Juazeiro do Norte';
        if (valorPre && _norm(valorPre) === 'juazeiro do norte') opt.selected = true;
        cidadeEl.appendChild(opt);
      }
    }

    // ── Popula bairros ────────────────────────────────────────
    function popularBairros(cidade, valorPre) {
      if (!bairroEl) return;
      const temBairros = _ehJuazeiro(cidade);

      if (bairroWrapEl) bairroWrapEl.style.display = temBairros ? '' : 'none';

      bairroEl.innerHTML = '<option value="">Selecione o bairro</option>';
      bairroEl.disabled  = !temBairros;

      if (temBairros) {
        for (const [regiao, lista] of Object.entries(BAIRROS_JUAZEIRO)) {
          const group = document.createElement('optgroup');
          group.label = regiao.charAt(0) + regiao.slice(1).toLowerCase();
          for (const nome of lista) {
            const opt = document.createElement('option');
            opt.value = nome;
            opt.textContent = nome;
            if (valorPre && _norm(valorPre) === _norm(nome)) opt.selected = true;
            group.appendChild(opt);
          }
          bairroEl.appendChild(group);
        }
      }
    }

    // ── Inicialização ─────────────────────────────────────────
    const pre = valoresIniciais || {};
    popularEstados(pre.estado);
    popularCidades(pre.estado, pre.cidade);
    popularBairros(pre.cidade, pre.bairro);

    // ── Eventos ───────────────────────────────────────────────
    estadoEl.addEventListener('change', function () {
      popularCidades(this.value, null);
      popularBairros(null, null);
    });

    cidadeEl.addEventListener('change', function () {
      popularBairros(this.value, null);
    });
  }

  // ─────────────────────────────────────────────────────────────
  // EXPORTA
  // ─────────────────────────────────────────────────────────────
  global.IDRUGS = {
    BAIRROS_JUAZEIRO,
    regiaoDosBairro,
    calcularFrete,
    renderInfoFrete,
    ligarCascata,
  };

})(window);
