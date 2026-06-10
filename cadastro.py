"""
cadastro.py — Módulo auxiliar iDrugs
======================================
Responsabilidades:
  • Validação e formatação de CNPJ (algoritmo oficial Receita Federal)
  • Validação de CPF (algoritmo oficial Lei 9.454/97)
  • Validação de e-mail (formato RFC)
  • Envio de OTP por e-mail (SMTP com detecção automática de provedor)
  • Cadastro de farmácia com validação completa

Uso standalone:
    python cadastro.py          # sobe na porta 5001
    python cadastro.py --test   # roda a bateria de testes internos

Endpoints:
    POST /enviar-codigo          { "email": "..." }
    POST /verificar-codigo       { "email": "...", "codigo": "..." }
    POST /api/cadastrar-farmacia { "nome":"...", "cnpj":"...", "email":"...", "senha":"...", ... }
    POST /api/validar-cnpj       { "cnpj": "..." }       ← utilitário de teste
"""

from __future__ import annotations

import os
import re
import sys
import random
import string
import logging
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash
from frete import regiao_do_bairro, BAIRROS_JUAZEIRO

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO SMTP
# ─────────────────────────────────────────────────────────────────────────────
EMAIL_USER      = os.getenv('EMAIL_USER',      'seuemail@gmail.com')
EMAIL_PASSWORD  = os.getenv('EMAIL_PASSWORD',  'sua_senha_de_app')
EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'iDrugs Farmácia')

# Tabela de provedores (domínio → host, porta, starttls?)
_SMTP_PROVIDERS: dict[str, tuple[str, int, bool]] = {
    'gmail.com':      ('smtp.gmail.com',          587, True),
    'hotmail.com':    ('smtp.office365.com',       587, True),
    'outlook.com':    ('smtp.office365.com',       587, True),
    'live.com':       ('smtp.office365.com',       587, True),
    'yahoo.com':      ('smtp.mail.yahoo.com',      587, True),
    'yahoo.com.br':   ('smtp.mail.yahoo.com',      587, True),
    'icloud.com':     ('smtp.mail.me.com',         587, True),
    'me.com':         ('smtp.mail.me.com',         587, True),
    'zoho.com':       ('smtp.zoho.com',            587, True),
    'uol.com.br':     ('smtp.uol.com.br',          587, True),
    'terra.com.br':   ('smtp.terra.com.br',        587, True),
    'ig.com.br':      ('smtp.ig.com.br',           587, True),
    'bol.com.br':     ('smtp.bol.com.br',          587, True),
    'protonmail.com': ('smtp.protonmail.ch',       587, True),
    'proton.me':      ('smtp.protonmail.ch',       587, True),
    'mailtrap.io':    ('sandbox.smtp.mailtrap.io', 2525, False),  # ambiente de teste
}


# ─────────────────────────────────────────────────────────────────────────────
# ARMAZENAMENTO DE OTPs EM MEMÓRIA
# Em produção substitua por tabela no banco de dados (ver app.py → CodigoVerificacao)
# ─────────────────────────────────────────────────────────────────────────────
# Estrutura: { email: { 'codigo': str, 'expira': datetime, 'usado': bool } }
_codigos: dict[str, dict] = {}


# =============================================================================
# ██████  VALIDAÇÃO DE CNPJ — ALGORITMO OFICIAL RECEITA FEDERAL
# =============================================================================
#
# Norma de referência:
#   • Instrução Normativa RFB nº 1.634/2016
#   • Manual técnico CNPJ — Receita Federal do Brasil
#
# Estrutura do CNPJ (14 dígitos):
#   RR RRR RRR OOOO DD
#   ├──────────┤    ├┤
#   Raiz (8)  Ord(4) Dígitos verificadores (2)
#
# Cálculo dos dígitos verificadores:
#   1° dígito: multiplica os 12 primeiros dígitos pelos pesos
#              [5,4,3,2,9,8,7,6,5,4,3,2], soma, resto = soma%11,
#              DV = 0 se resto < 2, senão DV = 11 - resto.
#   2° dígito: multiplica os 13 primeiros dígitos pelos pesos
#              [6,5,4,3,2,9,8,7,6,5,4,3,2], mesmo cálculo.
#
# =============================================================================

# Pesos oficiais — tabelas fixas conforme manual da Receita Federal
_PESOS_CNPJ_D1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]      # para os 12 primeiros dígitos
_PESOS_CNPJ_D2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]   # para os 13 primeiros dígitos

# Regex de formato aceito: com ou sem pontuação
_RE_CNPJ_FORMATADO = re.compile(
    r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$'   # 00.000.000/0000-00
)
_RE_CNPJ_NUMERICO = re.compile(r'^\d{14}$')  # 00000000000000


def _limpar_cnpj(cnpj: str) -> str:
    """Remove pontos, barra e hífen do CNPJ."""
    return re.sub(r'[\.\-\/\s]', '', str(cnpj))


def _calcular_dv_cnpj(digitos: str, pesos: list[int]) -> int:
    """
    Calcula um dígito verificador de CNPJ conforme o manual RFB.

    Args:
        digitos: string numérica com os dígitos base (12 ou 13 caracteres)
        pesos:   lista de pesos oficiais correspondente ao tamanho de 'digitos'

    Returns:
        Dígito verificador calculado (0–9)
    """
    soma = sum(int(d) * p for d, p in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cnpj(cnpj: str) -> bool:
    """
    Valida um CNPJ conforme o algoritmo oficial da Receita Federal do Brasil.

    Regras aplicadas:
      1. Remove pontuação (pontos, barra, hífen, espaços) antes de validar.
      2. Deve conter exatamente 14 caracteres numéricos após limpeza.
      3. Rejeita sequências de dígitos idênticos (00000000000000…).
      4. Valida o 1° dígito verificador (posição 13).
      5. Valida o 2° dígito verificador (posição 14).

    Formatos aceitos:
      • '11.222.333/0001-81'   (com formatação)
      • '11222333000181'        (apenas dígitos)

    Args:
        cnpj: string com o CNPJ a ser validado.

    Returns:
        True  — CNPJ matematicamente válido.
        False — inválido, mal formatado, sequência repetida ou dígitos errados.

    Exemplos:
        >>> validar_cnpj('33.000.167/0001-01')   # Petrobras
        True
        >>> validar_cnpj('60.746.948/0001-12')   # Bradesco
        True
        >>> validar_cnpj('00.000.000/0000-00')   # sequência repetida
        False
        >>> validar_cnpj('12.345.678/0001-00')   # dígitos errados
        False
    """
    c = _limpar_cnpj(cnpj)

    # ── Regra 1: comprimento e conteúdo ───────────────────────────────────────
    if not _RE_CNPJ_NUMERICO.match(c):
        return False

    # ── Regra 2: rejeita sequências uniformes ─────────────────────────────────
    if len(set(c)) == 1:
        return False

    # ── Regra 3: 1° dígito verificador ───────────────────────────────────────
    d1_esperado = _calcular_dv_cnpj(c[:12], _PESOS_CNPJ_D1)
    if int(c[12]) != d1_esperado:
        return False

    # ── Regra 4: 2° dígito verificador ───────────────────────────────────────
    d2_esperado = _calcular_dv_cnpj(c[:13], _PESOS_CNPJ_D2)
    if int(c[13]) != d2_esperado:
        return False

    return True


def formatar_cnpj(cnpj: str) -> str:
    """
    Formata um CNPJ para o padrão visual brasileiro: 00.000.000/0000-00.

    Aplica a formatação independente do formato de entrada
    (com ou sem pontuação). Não valida o conteúdo.

    Args:
        cnpj: string com o CNPJ (com ou sem formatação).

    Returns:
        CNPJ no formato '00.000.000/0000-00'.

    Raises:
        ValueError: se, após limpeza, o CNPJ não tiver 14 dígitos.
    """
    c = _limpar_cnpj(cnpj)
    if len(c) != 14:
        raise ValueError(f'CNPJ deve ter 14 dígitos após limpeza; recebido: {len(c)}')
    return f'{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}'


def gerar_cnpj_valido(base12: str | None = None) -> str:
    """
    Gera um CNPJ matematicamente válido.
    Útil para seeds e testes automatizados.

    Args:
        base12: string com os 12 primeiros dígitos (opcional).
                Se omitida, gera aleatoriamente.

    Returns:
        CNPJ formatado (00.000.000/0000-00) matematicamente válido.
    """
    if base12 is None:
        base12 = ''.join(random.choices(string.digits, k=12))
    c = base12[:12].zfill(12)
    d1 = _calcular_dv_cnpj(c, _PESOS_CNPJ_D1)
    d2 = _calcular_dv_cnpj(c + str(d1), _PESOS_CNPJ_D2)
    return formatar_cnpj(c + str(d1) + str(d2))


# =============================================================================
# VALIDAÇÃO DE CPF — Lei nº 9.454/97
# =============================================================================

_PESOS_CPF_D1 = list(range(10, 1, -1))   # [10,9,8,7,6,5,4,3,2]
_PESOS_CPF_D2 = list(range(11, 1, -1))   # [11,10,9,8,7,6,5,4,3,2]


def validar_cpf(cpf: str) -> bool:
    """
    Valida CPF conforme o algoritmo oficial (Lei nº 9.454/97).

    Args:
        cpf: CPF com ou sem formatação (000.000.000-00 ou 00000000000).

    Returns:
        True se válido, False caso contrário.
    """
    c = re.sub(r'[.\-\s]', '', str(cpf))
    if len(c) != 11 or not c.isdigit() or len(set(c)) == 1:
        return False

    def _dv(digitos, pesos):
        soma = sum(int(d) * p for d, p in zip(digitos, pesos))
        r = (soma * 10) % 11
        return 0 if r >= 10 else r

    return int(c[9]) == _dv(c[:9], _PESOS_CPF_D1) and \
           int(c[10]) == _dv(c[:10], _PESOS_CPF_D2)


def formatar_cpf(cpf: str) -> str:
    c = re.sub(r'[.\-\s]', '', str(cpf))
    return f'{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}'


# =============================================================================
# VALIDAÇÃO DE E-MAIL
# =============================================================================

_RE_EMAIL = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)


def validar_email(email: str) -> bool:
    """Valida formato de e-mail conforme padrão RFC simplificado."""
    return bool(_RE_EMAIL.match(email.strip()))


# =============================================================================
# SMTP — DETECÇÃO AUTOMÁTICA DE PROVEDOR
# =============================================================================

def _smtp_para(email: str) -> tuple[str, int, bool]:
    """
    Detecta host SMTP, porta e modo TLS pelo domínio do e-mail.

    As variáveis de ambiente EMAIL_HOST, EMAIL_PORT e EMAIL_USE_TLS
    têm prioridade sobre a detecção automática.

    Returns:
        (host, porta, usar_starttls)
    """
    dominio = email.split('@')[-1].lower() if '@' in email else ''
    host, port, tls = _SMTP_PROVIDERS.get(dominio, (f'smtp.{dominio}', 587, True))
    return (
        os.getenv('EMAIL_HOST', host),
        int(os.getenv('EMAIL_PORT', str(port))),
        os.getenv('EMAIL_USE_TLS', str(tls)).lower() not in ('false', '0', 'no'),
    )


# =============================================================================
# TEMPLATE HTML DO E-MAIL
# =============================================================================

def _html_otp(codigo: str, titulo: str = 'Código de Verificação') -> str:
    ano = datetime.datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#F7F9FC;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px;">
<table width="480" cellpadding="0" cellspacing="0"
  style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 20px rgba(26,115,232,.12);">
  <tr>
    <td style="background:linear-gradient(135deg,#1A73E8,#4A9EEF);padding:36px 40px;text-align:center;">
      <p style="margin:0 0 4px;font-size:30px;font-weight:800;color:#fff;">&#128138; iDrugs</p>
      <p style="margin:0;font-size:13px;color:rgba(255,255,255,.80);">Farmácia Digital</p>
    </td>
  </tr>
  <tr>
    <td style="padding:36px 40px 28px;text-align:center;">
      <p style="font-size:20px;font-weight:700;color:#1E293B;margin:0 0 10px;">{titulo}</p>
      <p style="font-size:14px;color:#64748B;line-height:1.6;margin:0 0 28px;">
        Use o código abaixo para continuar.<br/>
        Ele expira em <strong>15 minutos</strong>.
      </p>
      <div style="background:#EEF2F7;border-radius:16px;padding:22px 48px;display:inline-block;">
        <p style="margin:0 0 6px;font-size:10px;font-weight:700;letter-spacing:1.5px;
                  color:#94A3B8;text-transform:uppercase;">Seu código</p>
        <p style="margin:0;font-size:46px;font-weight:800;color:#1A73E8;
                  letter-spacing:14px;font-family:monospace;">{codigo}</p>
      </div>
      <p style="font-size:12px;color:#94A3B8;margin-top:20px;">
        Se você não solicitou este código, ignore este e-mail com segurança.
      </p>
    </td>
  </tr>
  <tr>
    <td style="background:#F7F9FC;padding:16px 40px;text-align:center;border-top:1px solid #EEF2F7;">
      <p style="margin:0;font-size:11px;color:#94A3B8;">&copy; {ano} iDrugs Farmácia Digital</p>
    </td>
  </tr>
</table></td></tr></table></body></html>"""


def _html_otp_collab(nome_farmacia: str, codigo: str) -> str:
    """Template verde para cadastro do colaborador."""
    ano = datetime.datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#F0FDF4;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px;">
<table width="480" cellpadding="0" cellspacing="0"
  style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 20px rgba(22,163,74,.12);">
  <tr>
    <td style="background:linear-gradient(135deg,#16A34A,#22C55E);padding:36px 40px;text-align:center;">
      <p style="margin:0 0 4px;font-size:30px;font-weight:800;color:#fff;">&#127978; iDrugs</p>
      <p style="margin:0;font-size:13px;color:rgba(255,255,255,.80);">Portal do Colaborador</p>
    </td>
  </tr>
  <tr>
    <td style="padding:36px 40px 28px;text-align:center;">
      <p style="font-size:20px;font-weight:700;color:#1E293B;margin:0 0 8px;">
        Olá, {nome_farmacia}!
      </p>
      <p style="font-size:14px;color:#64748B;line-height:1.6;margin:0 0 28px;">
        Sua farmácia foi pré-cadastrada no <strong>iDrugs</strong>.<br/>
        Use o código abaixo para ativar sua conta de colaborador:
      </p>
      <div style="background:#DCFCE7;border-radius:16px;padding:22px 48px;display:inline-block;">
        <p style="margin:0 0 6px;font-size:10px;font-weight:700;letter-spacing:1.5px;
                  color:#16A34A;text-transform:uppercase;">Código de ativação</p>
        <p style="margin:0;font-size:46px;font-weight:800;color:#15803D;
                  letter-spacing:14px;font-family:monospace;">{codigo}</p>
      </div>
      <p style="font-size:12px;color:#94A3B8;margin-top:20px;">
        &#9201; Expira em <strong>15 minutos</strong>.
      </p>
    </td>
  </tr>
  <tr>
    <td style="background:#F0FDF4;padding:16px 40px;text-align:center;border-top:1px solid #DCFCE7;">
      <p style="margin:0;font-size:11px;color:#94A3B8;">&copy; {ano} iDrugs Farmácia Digital</p>
    </td>
  </tr>
</table></td></tr></table></body></html>"""


# =============================================================================
# ENVIO DE E-MAIL
# =============================================================================

def enviar_email(destinatario: str, assunto: str, html: str) -> bool:
    """
    Envia e-mail HTML via SMTP com detecção automática de provedor.

    Returns:
        True em sucesso, False em falha (erro logado, aplicação não quebra).
    """
    host, port, use_tls = _smtp_para(destinatario)
    dominio = EMAIL_USER.split('@')[-1] if '@' in EMAIL_USER else '?'
    log.info(f'[SMTP] {dominio} → {host}:{port} TLS={use_tls}')

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = assunto
        msg['From']    = f'{EMAIL_FROM_NAME} <{EMAIL_USER}>'
        msg['To']      = destinatario
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
            smtp.login(EMAIL_USER, EMAIL_PASSWORD)
            smtp.sendmail(EMAIL_USER, destinatario, msg.as_string())

        log.info(f'[EMAIL OK] → {destinatario} | {assunto}')
        return True

    except smtplib.SMTPAuthenticationError:
        log.error(
            f'[EMAIL ERRO] Autenticação falhou em {host}.\n'
            '  • Gmail: gere senha de app em myaccount.google.com/security → "Senhas de app"\n'
            '  • Outlook: habilite SMTP autenticado nas configurações da conta.\n'
            f'  • E-mail usado: {EMAIL_USER}'
        )
    except smtplib.SMTPConnectError:
        log.error(f'[EMAIL ERRO] Não conectou em {host}:{port}. Verifique firewall/internet.')
    except smtplib.SMTPRecipientsRefused:
        log.error(f'[EMAIL ERRO] Destinatário recusado: {destinatario}')
    except Exception as exc:
        log.error(f'[EMAIL ERRO] {type(exc).__name__}: {exc}')

    return False


# =============================================================================
# HELPERS INTERNOS
# =============================================================================

def _gerar_codigo(tamanho: int = 6) -> str:
    """Gera um código OTP numérico aleatório."""
    return ''.join(random.choices(string.digits, k=tamanho))


def _invalidar_codigos_anteriores(email: str) -> None:
    """Remove qualquer OTP pendente para o e-mail antes de gerar um novo."""
    _codigos.pop(email, None)


# =============================================================================
# ROTAS FLASK
# =============================================================================

# ── POST /enviar-codigo ───────────────────────────────────────────────────────

@app.route('/enviar-codigo', methods=['POST'])
def enviar_codigo():
    """
    Gera e envia um OTP de 6 dígitos para o e-mail informado.

    Body JSON:
        email  (str, obrigatório) — destinatário
        titulo (str, opcional)   — título personalizado no corpo do e-mail

    Retorna 200 em sucesso (ou em falha SMTP com dev-code no JSON).
    Retorna 400 se e-mail ausente ou formato inválido.
    """
    dados = request.get_json(silent=True) or {}
    email = (dados.get('email') or '').strip().lower()
    titulo = dados.get('titulo', 'Código de Verificação — iDrugs')

    if not email:
        return jsonify({'erro': 'Campo "email" é obrigatório'}), 400
    if not validar_email(email):
        return jsonify({'erro': 'E-mail inválido. Formato esperado: usuario@dominio.com'}), 400

    _invalidar_codigos_anteriores(email)
    codigo = _gerar_codigo()
    _codigos[email] = {
        'codigo': codigo,
        'expira': datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
        'usado':  False,
    }

    enviado = enviar_email(email, titulo, _html_otp(codigo, titulo))

    if enviado:
        return jsonify({'mensagem': f'Código enviado para {email}'}), 200

    # Desenvolvimento: devolve o código quando SMTP não está configurado
    return jsonify({
        'mensagem': 'Código gerado. E-mail não enviado (configure EMAIL_USER/EMAIL_PASSWORD).',
        'aviso':    'Remova o campo "codigo" antes de ir para produção.',
        'codigo':   codigo,   # ← REMOVA EM PRODUÇÃO
    }), 200


# ── POST /verificar-codigo ────────────────────────────────────────────────────

@app.route('/verificar-codigo', methods=['POST'])
def verificar_codigo():
    """
    Verifica o OTP informado para o e-mail.

    Body JSON:
        email  (str) — mesmo usado em /enviar-codigo
        codigo (str) — 6 dígitos recebidos por e-mail

    Retorna 200 se correto; 400 em caso de erro/expiração.
    """
    dados  = request.get_json(silent=True) or {}
    email  = (dados.get('email')  or '').strip().lower()
    codigo = (dados.get('codigo') or '').strip()

    if not email or not codigo:
        return jsonify({'erro': 'Campos "email" e "codigo" são obrigatórios'}), 400

    registro = _codigos.get(email)

    if not registro:
        return jsonify({
            'erro': 'Nenhum código pendente para este e-mail. Solicite um novo.'
        }), 400

    if registro.get('usado'):
        return jsonify({'erro': 'Este código já foi utilizado. Solicite um novo.'}), 400

    if datetime.datetime.utcnow() > registro['expira']:
        _invalidar_codigos_anteriores(email)
        return jsonify({'erro': 'Código expirado. Solicite um novo.'}), 400

    if registro['codigo'] != codigo:
        return jsonify({'erro': 'Código incorreto. Verifique e tente novamente.'}), 400

    _invalidar_codigos_anteriores(email)
    return jsonify({'status': 'ok', 'mensagem': 'E-mail verificado com sucesso!'}), 200


# ── POST /api/cadastrar-farmacia ──────────────────────────────────────────────

@app.route('/api/cadastrar-farmacia', methods=['POST'])
def cadastrar_farmacia():
    """
    Cadastra uma nova farmácia com validação completa de CNPJ.

    Body JSON:
        nome     (str, obrigatório)
        cnpj     (str, obrigatório) — qualquer formato; validado pelo algoritmo RFB
        email    (str, obrigatório)
        senha    (str, obrigatório, mínimo 6 caracteres)
        telefone (str, opcional)
        endereco (str, opcional)
        cidade   (str, opcional)

    O CNPJ é armazenado no formato 00.000.000/0000-00 após validação.
    Após cadastro bem-sucedido, um OTP é enviado ao e-mail da farmácia.

    Retorna:
        201 — cadastrado com sucesso
        400 — dados inválidos (com mensagem detalhada do campo rejeitado)
        409 — e-mail ou CNPJ já cadastrado
        500 — erro interno

    Nota: requer que as variáveis DB_* estejam configuradas, ou use
          o modo integrado com SQLAlchemy no app.py principal.
    """
    data = request.get_json(silent=True) or {}

    # ── Extração dos campos ────────────────────────────────────────────────────
    nome     = (data.get('nome')     or '').strip()
    cnpj_raw = (data.get('cnpj')     or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    senha    = (data.get('senha')    or '')
    telefone = (data.get('telefone') or '').strip()
    endereco = (data.get('endereco') or '').strip()
    cidade   = (data.get('cidade')   or '').strip()
    estado   = (data.get('estado')   or '').upper() or None
    bairro   = data.get('bairro') or None

    # Validação: se for Juazeiro do Norte, bairro deve estar na lista
    if cidade and cidade.strip().lower() == 'juazeiro do norte':
        todos = [b for lst in BAIRROS_JUAZEIRO.values() for b in lst]
        if not bairro or bairro not in todos:
            return jsonify({'erro': 'Bairro inválido para Juazeiro do Norte'}), 400

    regiao = regiao_do_bairro(bairro)

    # ── Validações de presença ─────────────────────────────────────────────────
    erros = []
    if not nome:
        erros.append('Nome da farmácia é obrigatório.')
    if not cnpj_raw:
        erros.append('CNPJ é obrigatório.')
    if not email:
        erros.append('E-mail é obrigatório.')
    if not senha:
        erros.append('Senha é obrigatória.')
    if erros:
        return jsonify({'erro': ' | '.join(erros)}), 400

    # ── Validação de formato e dígitos verificadores do CNPJ ──────────────────
    if not validar_cnpj(cnpj_raw):
        c_limpo = _limpar_cnpj(cnpj_raw)
        detalhe = (
            'O CNPJ informado não é válido conforme o algoritmo da Receita Federal. '
            'Verifique se todos os 14 dígitos estão corretos e se os dígitos '
            'verificadores (últimos 2) são matematicamente consistentes com os '
            'demais. Formato esperado: 00.000.000/0000-00.'
        )
        if len(c_limpo) != 14:
            detalhe = (
                f'O CNPJ deve ter 14 dígitos; foram informados {len(c_limpo)} '
                f'dígito(s) após remover a pontuação. Formato esperado: 00.000.000/0000-00.'
            )
        elif not c_limpo.isdigit():
            detalhe = 'O CNPJ deve conter apenas dígitos (0–9), além da pontuação opcional.'
        elif len(set(c_limpo)) == 1:
            detalhe = 'CNPJ com todos os dígitos iguais não é permitido (ex: 11.111.111/1111-11).'
        return jsonify({'erro': 'CNPJ inválido.', 'detalhe': detalhe}), 400

    # ── Validação de e-mail ────────────────────────────────────────────────────
    if not validar_email(email):
        return jsonify({
            'erro': 'E-mail inválido.',
            'detalhe': 'Use o formato usuario@dominio.com'
        }), 400

    # ── Validação de senha ─────────────────────────────────────────────────────
    if len(senha) < 6:
        return jsonify({
            'erro': 'Senha muito curta.',
            'detalhe': 'A senha deve ter no mínimo 6 caracteres.'
        }), 400

    # ── Formata CNPJ para armazenamento ───────────────────────────────────────
    cnpj_fmt = formatar_cnpj(cnpj_raw)

    # ── Hash da senha ──────────────────────────────────────────────────────────
    senha_hash = generate_password_hash(senha)

    # ── Persistência no banco de dados ─────────────────────────────────────────
    # Conexão via variável de ambiente DATABASE_URL ou parâmetros individuais.
    # Em produção use o app.py principal com SQLAlchemy.
    try:
        import psycopg2
        conn = psycopg2.connect(
            os.getenv('DATABASE_URL',
                      'postgresql://postgres:postgres@localhost:5432/sgef_db')
        )
        cur = conn.cursor()

        # Verifica unicidade de e-mail
        cur.execute('SELECT id FROM farmacias WHERE email = %s', (email,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({'erro': 'E-mail já cadastrado para outra farmácia.'}), 409

        # Verifica unicidade de CNPJ
        cur.execute('SELECT id FROM farmacias WHERE cnpj = %s', (cnpj_fmt,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({'erro': 'CNPJ já cadastrado para outra farmácia.'}), 409

        cur.execute(
            """
            INSERT INTO farmacias (nome, cnpj, email, senha_hash, telefone, endereco, cidade, estado, bairro, regiao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (nome, cnpj_fmt, email, senha_hash, telefone, endereco, cidade, estado, bairro, regiao)
        )
        farmacia_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

    except ImportError:
        # psycopg2 não instalado — modo demo/teste sem banco
        log.warning('[DB] psycopg2 não disponível. Cadastro simulado (modo demo).')
        farmacia_id = 0

    except Exception as exc:
        log.error(f'[DB ERRO] {type(exc).__name__}: {exc}')
        return jsonify({
            'erro': 'Erro interno ao salvar no banco de dados.',
            'detalhe': str(exc)
        }), 500

    # ── Envia OTP de ativação ──────────────────────────────────────────────────
    _invalidar_codigos_anteriores(email)
    codigo = _gerar_codigo()
    _codigos[email] = {
        'codigo': codigo,
        'expira': datetime.datetime.utcnow() + datetime.timedelta(minutes=15),
        'usado':  False,
    }
    email_enviado = enviar_email(
        email,
        'iDrugs — Ative sua conta de colaborador',
        _html_otp_collab(nome, codigo)
    )

    resposta: dict = {
        'mensagem':     'Farmácia cadastrada com sucesso! Verifique o e-mail para ativar a conta.',
        'farmacia_id':  farmacia_id,
        'cnpj':         cnpj_fmt,
    }
    if not email_enviado:
        resposta['aviso']  = 'E-mail não enviado. Configure EMAIL_USER e EMAIL_PASSWORD.'
        resposta['codigo'] = codigo   # ← REMOVA EM PRODUÇÃO

    return jsonify(resposta), 201


# ── POST /api/validar-cnpj ────────────────────────────────────────────────────

@app.route('/api/validar-cnpj', methods=['POST'])
def rota_validar_cnpj():
    """
    Valida um CNPJ e retorna diagnóstico detalhado.
    Útil para validação em tempo real no frontend (sem autenticação).

    Body JSON: { "cnpj": "00.000.000/0000-00" }

    Retorna 200 se válido, 422 se inválido.
    """
    dados    = request.get_json(silent=True) or {}
    cnpj_raw = (dados.get('cnpj') or '').strip()

    if not cnpj_raw:
        return jsonify({'erro': 'Campo "cnpj" é obrigatório'}), 400

    c = _limpar_cnpj(cnpj_raw)
    valido = validar_cnpj(cnpj_raw)

    if valido:
        return jsonify({
            'valido':          True,
            'cnpj_informado':  cnpj_raw,
            'cnpj_formatado':  formatar_cnpj(cnpj_raw),
            'cnpj_numerico':   c,
            'mensagem':        'CNPJ válido conforme algoritmo da Receita Federal.',
        }), 200

    # Diagnóstico do motivo de rejeição
    if not c.isdigit():
        motivo = 'Contém caracteres não numéricos além da pontuação permitida.'
    elif len(c) != 14:
        motivo = f'Comprimento incorreto: {len(c)} dígito(s). Esperado: 14.'
    elif len(set(c)) == 1:
        motivo = 'Todos os dígitos são iguais. CNPJs assim são inválidos por definição.'
    else:
        # Mostra quais dígitos verificadores eram esperados vs recebidos
        d1_esp = _calcular_dv_cnpj(c[:12], _PESOS_CNPJ_D1)
        d2_esp = _calcular_dv_cnpj(c[:13], _PESOS_CNPJ_D2)
        motivo = (
            f'Dígitos verificadores incorretos. '
            f'Esperado: {d1_esp}{d2_esp} | Recebido: {c[12]}{c[13]}.'
        )

    return jsonify({
        'valido':         False,
        'cnpj_informado': cnpj_raw,
        'cnpj_numerico':  c,
        'motivo':         motivo,
        'mensagem':       'CNPJ inválido conforme algoritmo da Receita Federal.',
        'formato_correto': '00.000.000/0000-00 ou 00000000000000 (14 dígitos)',
    }), 422


# =============================================================================
# BATERIA DE TESTES INTERNOS
# =============================================================================

def _executar_testes() -> None:
    """
    Roda a suite de testes de validação de CNPJ e CPF.
    Execute com: python cadastro.py --test
    """
    VERDE  = '\033[92m'
    VERM   = '\033[91m'
    RESET  = '\033[0m'
    NEGRI  = '\033[1m'

    print(f'\n{NEGRI}{"="*60}')
    print(' BATERIA DE TESTES — iDrugs / cadastro.py')
    print(f'{"="*60}{RESET}\n')

    # ── Testes de CNPJ ────────────────────────────────────────────────────────
    casos_cnpj = [
        # (cnpj, esperado, descrição)
        ('33.000.167/0001-01', True,  'Petrobras — CNPJ real público'),
        ('60.746.948/0001-12', True,  'Bradesco — CNPJ real público'),
        ('11.444.777/0001-61', True,  'CNPJ válido (dígitos calculados)'),
        ('11.222.333/0001-81', True,  'iDrugs demo — dígitos calculados'),
        ('98.765.432/0001-98', True,  'FarmaVida demo — dígitos calculados'),
        ('12.345.678/0001-95', True,  'Drogaria demo — dígitos calculados'),
        ('11222333000181',     True,  'Sem formatação — deve aceitar'),
        ('00.000.000/0000-00', False, 'Todos zeros — rejeitar'),
        ('11.111.111/1111-11', False, 'Todos uns — rejeitar'),
        ('99.999.999/9999-99', False, 'Todos noves — rejeitar'),
        ('12.345.678/0001-00', False, 'Dígito verificador errado'),
        ('abc',                False, 'Não numérico — rejeitar'),
        ('1234',               False, 'Muito curto — rejeitar'),
        ('',                   False, 'Vazio — rejeitar'),
        ('12.345.678/0001-9',  False, 'Incompleto — rejeitar'),
    ]

    print(f'{NEGRI}CNPJ ({len(casos_cnpj)} casos):{RESET}')
    ok_cnpj = 0
    for cnpj, esperado, desc in casos_cnpj:
        resultado = validar_cnpj(cnpj)
        passou = resultado == esperado
        if passou:
            ok_cnpj += 1
        icone = f'{VERDE}✅{RESET}' if passou else f'{VERM}❌{RESET}'
        status_esp = 'VÁLIDO  ' if esperado else 'INVÁLIDO'
        print(f'  {icone} [{status_esp}] {cnpj:30} {desc}')

    print(f'\n  Resultado CNPJ: {ok_cnpj}/{len(casos_cnpj)} passou(aram)\n')

    # ── Testes de CPF ─────────────────────────────────────────────────────────
    casos_cpf = [
        ('529.982.247-25', True,  'CPF válido'),
        ('111.444.777-35', True,  'CPF válido'),
        ('111.111.111-11', False, 'Sequência repetida'),
        ('000.000.000-00', False, 'Todos zeros'),
        ('123.456.789-00', False, 'Dígito verificador errado'),
        ('abc',            False, 'Não numérico'),
    ]

    print(f'{NEGRI}CPF ({len(casos_cpf)} casos):{RESET}')
    ok_cpf = 0
    for cpf, esperado, desc in casos_cpf:
        resultado = validar_cpf(cpf)
        passou = resultado == esperado
        if passou:
            ok_cpf += 1
        icone = f'{VERDE}✅{RESET}' if passou else f'{VERM}❌{RESET}'
        status_esp = 'VÁLIDO  ' if esperado else 'INVÁLIDO'
        print(f'  {icone} [{status_esp}] {cpf:20} {desc}')

    print(f'\n  Resultado CPF: {ok_cpf}/{len(casos_cpf)} passou(aram)')

    # ── Geração de CNPJs demo ─────────────────────────────────────────────────
    print(f'\n{NEGRI}CNPJs gerados para SEED (matematicamente válidos):{RESET}')
    bases = [
        ('112223330001', 'iDrugs Farmácia'),
        ('987654320001', 'FarmaVida'),
        ('123456780001', 'Drogaria Saúde+'),
    ]
    for base, nome in bases:
        cnpj_gerado = gerar_cnpj_valido(base)
        assert validar_cnpj(cnpj_gerado), f'ERRO: {cnpj_gerado} deveria ser válido!'
        print(f'  {VERDE}✅{RESET} {nome:20} → {cnpj_gerado}')

    total = ok_cnpj + ok_cpf
    total_max = len(casos_cnpj) + len(casos_cpf)
    print(f'\n{NEGRI}Total: {total}/{total_max} testes passaram.{RESET}')
    if total == total_max:
        print(f'{VERDE}Todos os testes passaram!{RESET}\n')
    else:
        print(f'{VERM}Alguns testes falharam. Revise o algoritmo.{RESET}\n')
        sys.exit(1)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        _executar_testes()
    else:
        print('iDrugs — cadastro.py iniciando na porta 5001...')
        print('Dica: use "python cadastro.py --test" para rodar os testes de validação.')
        app.run(debug=True, port=5001)
