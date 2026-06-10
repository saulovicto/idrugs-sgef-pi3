/**
 * bairros.js — iDrugs
 * Cascata Estado→Cidade→Bairro + cálculo de frete com Haversine real.
 * Coloque em: static/js/bairros.js
 */
(function (global) {
  'use strict';

  // URL relativa — funciona em localhost E produção sem alterar nada
  const BASE = '';

  /* ── Coordenadas GPS dos bairros (espelho de frete.py) ─── */
  const COORDS = {
    "Centro":[-7.2131,-39.3153],"Socorro":[-7.2178,-39.3098],
    "Salesianos":[-7.2095,-39.3220],"São Miguel":[-7.2060,-39.3180],
    "Franciscanos":[-7.2110,-39.3090],"Pirajá":[-7.2200,-39.3250],
    "Pio XII":[-7.2145,-39.3300],"Horto":[-7.1890,-39.3160],
    "Salgadinho":[-7.1950,-39.3080],"Fátima":[-7.1980,-39.3200],
    "Santa Tereza":[-7.1920,-39.3250],"Juvêncio Santana":[-7.1855,-39.3130],
    "Aeroporto":[-7.2320,-39.2990],"Betolândia":[-7.2400,-39.3100],
    "Novo Juazeiro":[-7.2450,-39.3200],"Leandro Bezerra":[-7.2380,-39.3300],
    "Tiradentes":[-7.2350,-39.3050],"Limoeiro":[-7.2480,-39.3150],
    "João Cabral":[-7.2100,-39.3380],"Frei Damião":[-7.2050,-39.3450],
    "Campo Alegre":[-7.2200,-39.3500],"Jardim Gonzaga":[-7.2250,-39.3420],
    "Cidade Universitária":[-7.2180,-39.3600],"Lagoa Seca":[-7.2050,-39.2980],
    "Planalto":[-7.2120,-39.2900],"Triângulo":[-7.2080,-39.2850],
    "São José":[-7.2160,-39.2920],"Romeirão":[-7.2000,-39.2950],
    "Antônio Vieira":[-7.2230,-39.2870],
  };

  const BAIRROS_JUAZEIRO = {
    CENTRAL:["Centro","Socorro","Salesianos","São Miguel","Franciscanos","Pirajá","Pio XII"],
    NORTE:  ["Horto","Salgadinho","Fátima","Santa Tereza","Juvêncio Santana"],
    SUL:    ["Aeroporto","Betolândia","Novo Juazeiro","Leandro Bezerra","Tiradentes","Limoeiro"],
    OESTE:  ["João Cabral","Frei Damião","Campo Alegre","Jardim Gonzaga","Cidade Universitária"],
    LESTE:  ["Lagoa Seca","Planalto","Triângulo","São José","Romeirão","Antônio Vieira"],
  };

  // índices normalizados
  const _cl = {}, _rl = {};
  for (const [b,c] of Object.entries(COORDS))             _cl[b.trim().toLowerCase()] = c;
  for (const [r,l] of Object.entries(BAIRROS_JUAZEIRO))   l.forEach(b => _rl[b.trim().toLowerCase()] = r);

  /* ── helpers ─────────────────────────────────────────── */
  const _n = s => (s||'').trim().toLowerCase();
  const _jua = c => ['juazeiro do norte','juazeiro do norte - ce','juazeiro do norte/ce','juazeiro'].includes(_n(c));

  function _hav(la1,lo1,la2,lo2){
    const R=6371, d2r=Math.PI/180;
    const dlat=(la2-la1)*d2r, dlon=(lo2-lo1)*d2r;
    const a=Math.sin(dlat/2)**2+Math.cos(la1*d2r)*Math.cos(la2*d2r)*Math.sin(dlon/2)**2;
    return R*2*Math.asin(Math.sqrt(a));
  }

  function _dist(ba,bb){
    const ca=_cl[_n(ba)], cb=_cl[_n(bb)];
    return (ca&&cb) ? _hav(ca[0],ca[1],cb[0],cb[1]) : null;
  }

  function _tab(d){
    if(d<=2)  return {frete:0,    tempo:15, label:'Grátis'   };
    if(d<=5)  return {frete:4.99, tempo:25, label:'R$ 4,99'  };
    if(d<=10) return {frete:8.99, tempo:40, label:'R$ 8,99'  };
    return          {frete:12.99,tempo:60, label:'R$ 12,99'  };
  }

  /* ── calcularFrete ───────────────────────────────────── */
  function calcularFrete(farmCidade, farmBairro, cliCidade, cliBairro){
    const regF = _rl[_n(farmBairro)]||null;
    if(!_jua(farmCidade))
      return {sob_encomenda:true,frete:null,frete_label:'Frete sob encomenda',
              distancia_label:'—',tempo_label:'—',regiao_farmacia:regF,regiao_cliente:null};
    if(!cliBairro||!_jua(cliCidade))
      return {sob_encomenda:false,frete:4.99,frete_label:'A partir de R$ 4,99',
              distancia_label:'—',tempo_label:'~20 min',regiao_farmacia:regF,regiao_cliente:null};
    const regC=_rl[_n(cliBairro)]||null;
    let d=_dist(farmBairro,cliBairro);
    if(d===null) d = _n(farmBairro)===_n(cliBairro)?0.5:(regF&&regC&&regF===regC?3:7);
    const t=_tab(d);
    return {sob_encomenda:false,distancia_km:+d.toFixed(2),tempo_min:t.tempo,
            frete:t.frete,frete_label:t.label,
            distancia_label:d.toFixed(1)+' km',tempo_label:t.tempo+' min',
            regiao_farmacia:regF,regiao_cliente:regC};
  }

  /* ── renderInfoFrete ─────────────────────────────────── */
  function renderInfoFrete(info){
    if(!info) return '';
    if(info.sob_encomenda)
      return '<div class="frete-info"><span>🚚 Frete sob encomenda</span></div>';
    const gratis = info.frete===0;
    return `<div class="frete-info">
      <span style="${gratis?'color:var(--green-dark,#16a34a);font-weight:700':''}">
        ${gratis?'🎉':'🚚'} ${info.frete_label}</span>
      <span>⏱ ${info.tempo_label}</span>
      ${info.distancia_label&&info.distancia_label!=='—'?`<span>📍 ${info.distancia_label}</span>`:''}
    </div>`;
  }

  /* ── cascata Estado→Cidade→Bairro ────────────────────── */
  async function _api(path){
    const r=await fetch(BASE+path); if(!r.ok) throw new Error(r.status); return r.json();
  }

  async function ligarCascata({estadoEl,cidadeEl,bairroEl,bairroWrapEl,valoresIniciais}){
    if(!estadoEl||!cidadeEl) return;
    let estados=[];
    try{ estados=await _api('/api/localidades/estados'); }
    catch(e){ estadoEl.innerHTML='<option value="">Erro ao carregar</option>'; return; }

    estadoEl.innerHTML='<option value="">Selecione o estado</option>'+
      estados.map(e=>`<option value="${e.sigla}">${e.nome} (${e.sigla})</option>`).join('');

    estadoEl.addEventListener('change',()=>_cidades(estadoEl,cidadeEl,bairroEl,bairroWrapEl,null));
    cidadeEl.addEventListener('change',()=>_bairros(cidadeEl,bairroEl,bairroWrapEl,null));

    if(valoresIniciais?.estado){
      estadoEl.value=valoresIniciais.estado;
      await _cidades(estadoEl,cidadeEl,bairroEl,bairroWrapEl,valoresIniciais);
    }
  }

  async function _cidades(eEl,cEl,bEl,bWEl,vals){
    const uf=eEl.value;
    cEl.innerHTML='<option value="">Carregando…</option>'; cEl.disabled=true;
    if(bEl) bEl.innerHTML='<option value="">Selecione o bairro</option>';
    if(bWEl) bWEl.style.display='none';
    if(!uf){ cEl.innerHTML='<option value="">Selecione o estado primeiro</option>'; return; }
    let list=[];
    try{ list=await _api('/api/localidades/cidades?estado='+encodeURIComponent(uf)); }
    catch(e){ cEl.innerHTML='<option value="">Erro</option>'; return; }
    cEl.innerHTML='<option value="">Selecione a cidade</option>'+
      list.map(c=>`<option value="${c.nome}">${c.nome}</option>`).join('');
    cEl.disabled=false;
    if(vals?.cidade){ cEl.value=vals.cidade; await _bairros(cEl,bEl,bWEl,vals); }
  }

  async function _bairros(cEl,bEl,bWEl,vals){
    if(!bEl) return;
    const cidade=cEl.value;
    bEl.innerHTML='<option value="">Carregando…</option>';
    if(bWEl) bWEl.style.display='none';
    if(!cidade) return;
    let data={};
    try{ data=await _api('/api/localidades/bairros?cidade='+encodeURIComponent(cidade)); }
    catch(e){ return; }
    if(!data.tem_bairros){ if(bWEl) bWEl.style.display='none'; return; }
    let html='<option value="">Selecione o bairro</option>';
    for(const [reg,lista] of Object.entries(data.regioes||{})){
      html+=`<optgroup label="${reg}">${lista.map(b=>`<option value="${b}">${b}</option>`).join('')}</optgroup>`;
    }
    bEl.innerHTML=html;
    if(bWEl) bWEl.style.display='block';
    if(vals?.bairro) bEl.value=vals.bairro;
  }

  /* ── export ─────────────────────────────────────────── */
  global.IDRUGS={ligarCascata,calcularFrete,renderInfoFrete,
                  regiaoDoNom:b=>_rl[_n(b)]||null,BAIRROS_JUAZEIRO,COORDS};
})(window);
