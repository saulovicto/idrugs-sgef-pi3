from flask import Flask, request, jsonify, send_from_directory
import os, uuid
import cloudinary
import cloudinary.uploader
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import re
import random
import string
import os
import smtplib
import logging
try:
    from dotenv import load_dotenv
    load_dotenv()  # carrega .env se existir
except ImportError:
    pass  # python-dotenv não instalado — usa variáveis de ambiente do sistema
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from frete import calcular_frete, regiao_do_bairro, register_frete_routes, BAIRROS_JUAZEIRO

app = Flask(__name__)
CORS(app)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sgef_secret_key_2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'postgresql://postgres:ewq321ytr654@localhost:5432/idrugs')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ── Cloudinary — hospedagem de imagens ──────────────────────────
cloudinary.config(
    cloud_name = "dmpatqet6",
    api_key    = "668581774375955",
    api_secret = "iVSACuM9P2IA4odtwpp4AUaz4aM",
    secure     = True
)

# Pasta local como fallback (caso Cloudinary falhe)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB máximo
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ── E-mail ────────────────────────────────────────────────────────────────────
EMAIL_USER      = os.getenv('EMAIL_USER',      'seuemail@gmail.com')
EMAIL_PASSWORD  = os.getenv('EMAIL_PASSWORD',  'sua_senha_de_app')
EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'iDrugs Farmácia')

_SMTP_PROVIDERS = {
    'gmail.com':        ('smtp.gmail.com',          587, True),
    'hotmail.com':      ('smtp.office365.com',       587, True),
    'outlook.com':      ('smtp.office365.com',       587, True),
    'live.com':         ('smtp.office365.com',       587, True),
    'yahoo.com':        ('smtp.mail.yahoo.com',      587, True),
    'yahoo.com.br':     ('smtp.mail.yahoo.com',      587, True),
    'icloud.com':       ('smtp.mail.me.com',         587, True),
    'zoho.com':         ('smtp.zoho.com',            587, True),
    'uol.com.br':       ('smtp.uol.com.br',          587, True),
    'terra.com.br':     ('smtp.terra.com.br',        587, True),
    'protonmail.com':   ('smtp.protonmail.ch',       587, True),
    'mailtrap.io':      ('sandbox.smtp.mailtrap.io', 2525, False),
}

def _detectar_smtp(email_user: str) -> tuple:
    dominio = email_user.split('@')[-1].lower() if '@' in email_user else ''
    host, port, tls = _SMTP_PROVIDERS.get(dominio, ('smtp.' + dominio, 587, True))
    host = os.getenv('EMAIL_HOST', host)
    port = int(os.getenv('EMAIL_PORT', str(port)))
    tls  = os.getenv('EMAIL_USE_TLS', str(tls)).lower() not in ('false', '0', 'no')
    return host, port, tls

logging.basicConfig(level=logging.INFO)
db = SQLAlchemy(app)


# ─────────────────────────────────────────────
# TEMPLATES DE E-MAIL HTML
# ─────────────────────────────────────────────

def _html_cadastro(nome: str, codigo: str) -> str:
    ano = datetime.datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#F7F9FC;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px;">
<table width="480" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(26,115,232,.12);">
  <tr><td style="background:linear-gradient(135deg,#1A73E8,#4A9EEF);padding:36px 40px;text-align:center;">
    <p style="margin:0 0 4px;font-size:30px;font-weight:800;color:#fff;">&#128138; iDrugs</p>
    <p style="margin:0;font-size:13px;color:rgba(255,255,255,.80);">Farmácia Digital</p>
  </td></tr>
  <tr><td style="padding:36px 40px 28px;">
    <p style="margin:0 0 8px;font-size:20px;font-weight:700;color:#1E293B;">Olá, {nome}!</p>
    <p style="margin:0 0 24px;font-size:15px;color:#64748B;line-height:1.6;">
      Obrigado por se cadastrar no <strong>iDrugs</strong>.<br/>
      Use o código abaixo para confirmar seu e-mail:
    </p>
    <table width="100%"><tr><td align="center" style="padding:8px 0 28px;">
      <div style="display:inline-block;background:#EEF2F7;border-radius:16px;padding:22px 48px;">
        <p style="margin:0 0 6px;font-size:11px;font-weight:600;letter-spacing:1.5px;color:#94A3B8;text-transform:uppercase;">Código de verificação</p>
        <p style="margin:0;font-size:46px;font-weight:800;color:#1A73E8;letter-spacing:14px;font-family:monospace;">{codigo}</p>
      </div>
    </td></tr></table>
    <p style="margin:0 0 6px;font-size:13px;color:#94A3B8;text-align:center;">&#9201; Este código expira em <strong>15 minutos</strong>.</p>
    <p style="margin:0;font-size:13px;color:#94A3B8;text-align:center;">Se você não criou uma conta, ignore este e-mail.</p>
  </td></tr>
  <tr><td style="background:#F7F9FC;padding:18px 40px;text-align:center;border-top:1px solid #EEF2F7;">
    <p style="margin:0;font-size:12px;color:#94A3B8;">&copy; {ano} iDrugs Farmácia Digital</p>
  </td></tr>
</table></td></tr></table></body></html>"""


def _html_recuperacao(nome: str, codigo: str) -> str:
    ano = datetime.datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#F7F9FC;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0">
<tr><td align="center" style="padding:40px 16px;">
<table width="480" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(26,115,232,.12);">
  <tr><td style="background:linear-gradient(135deg,#1A73E8,#4A9EEF);padding:36px 40px;text-align:center;">
    <p style="margin:0 0 4px;font-size:30px;font-weight:800;color:#fff;">&#128274; iDrugs</p>
    <p style="margin:0;font-size:13px;color:rgba(255,255,255,.80);">Recuperação de senha</p>
  </td></tr>
  <tr><td style="padding:36px 40px 28px;">
    <p style="margin:0 0 8px;font-size:20px;font-weight:700;color:#1E293B;">Olá, {nome}!</p>
    <p style="margin:0 0 24px;font-size:15px;color:#64748B;line-height:1.6;">
      Recebemos uma solicitação de redefinição de senha.<br/>Use o código abaixo:
    </p>
    <table width="100%"><tr><td align="center" style="padding:8px 0 28px;">
      <div style="display:inline-block;background:#FFF3E0;border-radius:16px;padding:22px 48px;">
        <p style="margin:0 0 6px;font-size:11px;font-weight:600;letter-spacing:1.5px;color:#FB8C00;text-transform:uppercase;">Código de recuperação</p>
        <p style="margin:0;font-size:46px;font-weight:800;color:#E65100;letter-spacing:14px;font-family:monospace;">{codigo}</p>
      </div>
    </td></tr></table>
    <p style="margin:0 0 6px;font-size:13px;color:#94A3B8;text-align:center;">&#9201; Expira em <strong>15 minutos</strong>.</p>
    <p style="margin:0;font-size:13px;color:#94A3B8;text-align:center;">Se não foi você, sua senha continua segura.</p>
  </td></tr>
  <tr><td style="background:#F7F9FC;padding:18px 40px;text-align:center;border-top:1px solid #EEF2F7;">
    <p style="margin:0;font-size:12px;color:#94A3B8;">&copy; {ano} iDrugs Farmácia Digital</p>
  </td></tr>
</table></td></tr></table></body></html>"""


def _html_cadastro_collab(nome: str, codigo: str) -> str:
    digitos = ''.join(f'<span style="display:inline-block;width:44px;height:52px;line-height:52px;text-align:center;background:#ECFDF5;border:2px solid #059669;border-radius:8px;font-size:28px;font-weight:700;color:#059669;margin:0 4px;">{d}</span>' for d in codigo)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.10);">
        <tr><td style="background:linear-gradient(135deg,#059669,#0891B2);padding:32px;text-align:center;">
          <p style="margin:0;font-size:28px;font-weight:800;color:#fff;">+iDrugs</p>
          <p style="margin:6px 0 0;font-size:13px;color:rgba(255,255,255,.8);">Painel do Colaborador / Farmacêutico</p>
        </td></tr>
        <tr><td style="background:#fff;padding:36px 40px;">
          <p style="margin:0 0 8px;font-size:20px;font-weight:700;color:#0F172A;">Olá, {nome}! 🏥</p>
          <p style="margin:0 0 24px;color:#64748B;font-size:15px;line-height:1.6;">
            Sua farmácia está sendo cadastrada no <strong>iDrugs</strong>. Confirme o e-mail com o código abaixo para ativar o painel do colaborador:
          </p>
          <div style="text-align:center;margin:28px 0;">
            {digitos}
          </div>
          <p style="text-align:center;margin:16px 0 28px;color:#94A3B8;font-size:13px;">
            ⏱ Este código expira em <strong>15 minutos</strong>
          </p>
          <div style="background:#F0FDF4;border-left:4px solid #059669;border-radius:0 8px 8px 0;padding:14px 18px;margin-bottom:24px;">
            <p style="margin:0;color:#14532D;font-size:13px;">
              Após verificar, faça login no painel e complete o cadastro com foto e produtos da farmácia.
            </p>
          </div>
          <p style="margin:0;color:#CBD5E1;font-size:12px;text-align:center;">
            iDrugs · Painel do Colaborador · E-mail automático
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def enviar_email(destinatario: str, assunto: str, html: str) -> bool:
    host, port, use_tls = _detectar_smtp(EMAIL_USER)
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = assunto
        msg['From']    = f'{EMAIL_FROM_NAME} <{EMAIL_USER}>'
        msg['To']      = destinatario
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.ehlo(); smtp.starttls(); smtp.ehlo()
            smtp.login(EMAIL_USER, EMAIL_PASSWORD)
            smtp.sendmail(EMAIL_USER, destinatario, msg.as_string())
        logging.info(f'[EMAIL OK] Para: {destinatario} | {assunto}')
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error(f'[EMAIL ERRO] Autenticação falhou em {host}.')
    except Exception as exc:
        logging.error(f'[EMAIL ERRO] {type(exc).__name__}: {exc}')
    return False


# ─────────────────────────────────────────────
# MODELOS
# ─────────────────────────────────────────────

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id           = db.Column(db.Integer, primary_key=True)
    nome         = db.Column(db.String(150), nullable=False)
    email        = db.Column(db.String(150), unique=True, nullable=False)
    cpf          = db.Column(db.String(14),  unique=True, nullable=False)
    senha_hash   = db.Column(db.String(256), nullable=False)
    telefone     = db.Column(db.String(20),  nullable=True)
    endereco     = db.Column(db.String(255), nullable=True)
    addr_rua     = db.Column(db.String(150), nullable=True)
    addr_num     = db.Column(db.String(20),  nullable=True)
    addr_bairro  = db.Column(db.String(100), nullable=True)
    addr_cep     = db.Column(db.String(10),  nullable=True)
    addr_ref     = db.Column(db.String(200), nullable=True)
    addr_estado  = db.Column(db.String(2),   nullable=True)
    addr_cidade  = db.Column(db.String(100), nullable=True)
    addr_regiao  = db.Column(db.String(20),  nullable=True)
    ativo        = db.Column(db.Boolean, default=True)
    criado_em    = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self):
        return {
            'id':          self.id,
            'nome':        self.nome,
            'email':       self.email,
            'cpf':         self.cpf,
            'telefone':    self.telefone    or '',
            'endereco':    self.endereco    or '',
            'addr_rua':    self.addr_rua    or '',
            'addr_num':    self.addr_num    or '',
            'addr_bairro': self.addr_bairro or '',
            'addr_cep':    self.addr_cep    or '',
            'addr_ref':    self.addr_ref    or '',
            'addr_estado': self.addr_estado or '',
            'addr_cidade': self.addr_cidade or '',
            'addr_regiao': self.addr_regiao or '',
            'ativo':       self.ativo,
            'criado_em':   self.criado_em.isoformat()
        }


class Farmacia(db.Model):
    __tablename__ = 'farmacias'
    id         = db.Column(db.Integer, primary_key=True)
    nome       = db.Column(db.String(150), nullable=False)
    cnpj       = db.Column(db.String(18),  unique=True, nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256))
    telefone   = db.Column(db.String(20))
    endereco   = db.Column(db.String(255))
    cidade     = db.Column(db.String(100))
    estado     = db.Column(db.String(2))
    bairro     = db.Column(db.String(100))
    regiao     = db.Column(db.String(20))
    ativo      = db.Column(db.Boolean, default=True)
    imagem_url = db.Column(db.Text,      nullable=True)
    criado_em  = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash or '', senha)

    def to_dict(self):
        return {
            'id':          self.id,
            'nome':        self.nome,
            'cnpj':        self.cnpj,
            'email':       self.email,
            'telefone':    self.telefone    or '',
            'endereco':    self.endereco    or '',
            'cidade':      self.cidade      or '',
            'estado':      self.estado      or '',
            'bairro':      self.bairro      or '',
            'regiao':      self.regiao      or '',
            'imagem_url':  self.imagem_url  or '',
            'ativo':       self.ativo
        }


class Produto(db.Model):
    __tablename__ = 'produtos'
    id          = db.Column(db.Integer, primary_key=True)
    farmacia_id = db.Column(db.Integer, db.ForeignKey('farmacias.id'), nullable=False)
    nome        = db.Column(db.String(200), nullable=False)
    descricao   = db.Column(db.Text)
    preco       = db.Column(db.Numeric(10, 2), nullable=False)
    estoque     = db.Column(db.Integer, default=0)
    categoria   = db.Column(db.String(100))
    imagem_url  = db.Column(db.Text)
    ativo       = db.Column(db.Boolean, default=True)
    criado_em   = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    farmacia    = db.relationship('Farmacia', backref='produtos')

    def to_dict(self):
        return {
            'id': self.id, 'farmacia_id': self.farmacia_id,
            'nome': self.nome, 'descricao': self.descricao,
            'preco': float(self.preco), 'estoque': self.estoque,
            'categoria': self.categoria, 'imagem_url': self.imagem_url, 'ativo': self.ativo
        }


class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id          = db.Column(db.Integer, primary_key=True)
    cliente_id  = db.Column(db.Integer, db.ForeignKey('clientes.id'),  nullable=False)
    farmacia_id = db.Column(db.Integer, db.ForeignKey('farmacias.id'), nullable=False)
    status      = db.Column(db.String(50), default='pendente')
    total       = db.Column(db.Numeric(10, 2))
    forma_pagto = db.Column(db.String(50))
    criado_em   = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    cliente     = db.relationship('Cliente', backref='pedidos')
    farmacia    = db.relationship('Farmacia', backref='pedidos')


class ItemPedido(db.Model):
    __tablename__ = 'itens_pedido'
    id         = db.Column(db.Integer, primary_key=True)
    pedido_id  = db.Column(db.Integer, db.ForeignKey('pedidos.id'),  nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey('produtos.id'), nullable=True)
    quantidade = db.Column(db.Integer, nullable=False)
    preco_unit = db.Column(db.Numeric(10, 2), nullable=False)
    nome_item  = db.Column(db.String(150), nullable=True)
    nome_farm  = db.Column(db.String(150), nullable=True)
    pedido     = db.relationship('Pedido', backref='itens')
    produto    = db.relationship('Produto')


class CodigoVerificacao(db.Model):
    __tablename__ = 'codigos_verificacao'
    id        = db.Column(db.Integer, primary_key=True)
    email     = db.Column(db.String(150), nullable=False)
    codigo    = db.Column(db.String(6),   nullable=False)
    usado     = db.Column(db.Boolean, default=False)
    expira_em = db.Column(db.DateTime, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.datetime.utcnow)


# ─────────────────────────────────────────────
# ROTAS AUXILIARES DE LOCALIDADE / FRETE
# ─────────────────────────────────────────────
register_frete_routes(app, db=db, Farmacia=Farmacia, Cliente=Cliente)

# ─────────────────────────────────────────────
# HELPERS DE VALIDAÇÃO
# ─────────────────────────────────────────────

def validar_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email))


def validar_cpf(cpf: str) -> bool:
    c = re.sub(r'[.\-]', '', cpf)
    if len(c) != 11 or not c.isdigit() or c == c[0] * 11:
        return False
    soma = sum(int(c[i]) * (10 - i) for i in range(9))
    r = (soma * 10) % 11
    if r in (10, 11): r = 0
    if r != int(c[9]): return False
    soma = sum(int(c[i]) * (11 - i) for i in range(10))
    r = (soma * 10) % 11
    if r in (10, 11): r = 0
    return r == int(c[10])


def formatar_cpf(cpf: str) -> str:
    c = re.sub(r'[.\-]', '', cpf)
    return f'{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}'


def validar_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ conforme o algoritmo oficial da Receita Federal do Brasil.

    Regras aplicadas:
      1. Remove toda pontuação (pontos, barra, hífen) antes de validar.
      2. Exige exatamente 14 dígitos numéricos após limpeza.
      3. Rejeita sequências de dígitos idênticos (ex: 11111111111111).
      4. Calcula e confere o 1° dígito verificador usando os pesos
         [5,4,3,2,9,8,7,6,5,4,3,2] sobre os 12 primeiros dígitos.
      5. Calcula e confere o 2° dígito verificador usando os pesos
         [6,5,4,3,2,9,8,7,6,5,4,3,2] sobre os 13 primeiros dígitos.

    Fórmula dos dígitos verificadores (padrão Receita Federal):
      soma = Σ(dígito[i] × peso[i])
      resto = soma % 11
      dígito verificador = 0  se resto < 2,  senão  11 − resto

    Formatos aceitos:
      '11.222.333/0001-81'  — com formatação brasileira padrão
      '11222333000181'       — apenas os 14 dígitos

    Args:
        cnpj: string com o CNPJ a validar (qualquer formato).

    Returns:
        True  — CNPJ matematicamente válido.
        False — inválido, mal formatado ou com dígitos verificadores errados.

    Exemplos:
        >>> validar_cnpj('33.000.167/0001-01')   # Petrobras — True
        >>> validar_cnpj('60.746.948/0001-12')   # Bradesco  — True
        >>> validar_cnpj('00.000.000/0000-00')   # sequência — False
        >>> validar_cnpj('12.345.678/0001-00')   # DV errado — False
    """
    # ── 1. Remove tudo que não for número ─────────────────────────────────────
    cnpj = re.sub(r'\D', '', cnpj)

    # ── 2. Tamanho correto ────────────────────────────────────────────────────
    if len(cnpj) != 14:
        return False

    # ── 3. Evita sequências do tipo 11111111111111 ────────────────────────────
    if cnpj == cnpj[0] * 14:
        return False

    # ── 4 & 5. Calcula e verifica os dois dígitos verificadores ──────────────
    def calcular_digito(cnpj: str, pesos: list) -> int:
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(len(pesos)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    peso1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    peso2 = [6] + peso1   # [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    digito1 = calcular_digito(cnpj, peso1)
    digito2 = calcular_digito(cnpj, peso2)

    return cnpj[-2:] == f'{digito1}{digito2}'


def formatar_cnpj(cnpj: str) -> str:
    """
    Formata um CNPJ para o padrão visual brasileiro: 00.000.000/0000-00.

    Aceita o CNPJ com ou sem formatação. Não valida o conteúdo.
    Para validar antes de formatar use validar_cnpj().

    Args:
        cnpj: string com o CNPJ (com ou sem pontuação).

    Returns:
        CNPJ no formato '00.000.000/0000-00'.
    """
    cnpj = re.sub(r'\D', '', cnpj)
    return f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}'


def _gerar_codigo() -> str:
    return ''.join(random.choices(string.digits, k=6))


def _invalidar_codigos_anteriores(email: str) -> None:
    """Invalida todos os OTPs não usados de um e-mail antes de gerar um novo."""
    CodigoVerificacao.query.filter_by(email=email, usado=False).update({'usado': True})


# ─────────────────────────────────────────────
# DECORATORS DE AUTENTICAÇÃO
# ─────────────────────────────────────────────

def token_requerido(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'erro': 'Token não fornecido'}), 401
        try:
            dados = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            cliente_atual = Cliente.query.get(dados['cliente_id'])
            if not cliente_atual:
                return jsonify({'erro': 'Usuário não encontrado'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'erro': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'erro': 'Token inválido'}), 401
        return f(cliente_atual, *args, **kwargs)
    return decorated


def collab_token_requerido(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'erro': 'Token não fornecido'}), 401
        try:
            dados = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            farmacia = Farmacia.query.get(dados.get('farmacia_id'))
            if not farmacia:
                return jsonify({'erro': 'Farmácia não encontrada'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'erro': 'Token expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'erro': 'Token inválido'}), 401
        return f(farmacia, *args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# ROTAS — AUTENTICAÇÃO CLIENTE
# ─────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────
# UPLOAD DE IMAGENS
# ──────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────
# CHAT EM TEMPO REAL — COLABORADOR E CLIENTE
# ──────────────────────────────────────────────────────────────

@app.route('/api/chat/mensagens', methods=['GET'])
@token_requerido
def cliente_mensagens(cliente_atual):
    """Mensagens entre o cliente autenticado e uma farmácia."""
    farmacia_id = request.args.get('farmacia_id', type=int)
    after_id    = request.args.get('after', 0, type=int)
    if not farmacia_id:
        return jsonify({'erro': 'farmacia_id obrigatório'}), 400
    try:
        q = Mensagem.query.filter_by(
            cliente_id=cliente_atual.id, farmacia_id=farmacia_id
        ).filter(Mensagem.id > after_id).order_by(Mensagem.criado_em).all()
        for m in q:
            if m.remetente == 'farmacia' and not m.lida:
                m.lida = True
        db.session.commit()
        return jsonify([m.to_dict() for m in q]), 200
    except Exception as e:
        return jsonify([]), 200


@app.route('/api/chat/enviar', methods=['POST'])
@token_requerido
def cliente_enviar_mensagem(cliente_atual):
    """Cliente envia mensagem para uma farmácia."""
    dados       = request.get_json() or {}
    farmacia_id = dados.get('farmacia_id')
    texto       = (dados.get('texto') or '').strip()
    if not farmacia_id or not texto:
        return jsonify({'erro': 'farmacia_id e texto obrigatórios'}), 400
    msg = Mensagem(
        cliente_id  = cliente_atual.id,
        farmacia_id = farmacia_id,
        texto       = texto,
        remetente   = 'cliente',
        lida        = False
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@app.route('/api/collab/chat/conversas', methods=['GET'])
@collab_token_requerido
def collab_listar_conversas(farmacia):
    """Lista clientes que têm mensagens com esta farmácia + não lidas."""
    try:
        msgs = Mensagem.query.filter_by(farmacia_id=farmacia.id)                             .order_by(Mensagem.criado_em.desc()).all()
    except Exception as e:
        app.logger.error(f"Erro ao buscar mensagens: {e}")
        return jsonify([]), 200

    vistos = {}
    for m in msgs:
        cid = m.cliente_id
        if cid not in vistos:
            cli = Cliente.query.get(cid)
            if cli:
                vistos[cid] = {
                    'cliente_id':      cid,
                    'nome':            cli.nome,
                    'ultima_mensagem': m.texto[:50],
                    'hora':            m.criado_em.strftime('%H:%M') if m.criado_em else '',
                    'nao_lidas':       0
                }
        if m.remetente == 'cliente' and not m.lida:
            if cid in vistos:
                vistos[cid]['nao_lidas'] += 1

    # return FORA do loop — era o bug principal
    return jsonify(list(vistos.values())), 200


@app.route('/api/collab/chat/mensagens', methods=['GET'])
@collab_token_requerido
def collab_mensagens(farmacia):
    """Mensagens com um cliente específico."""
    cliente_id = request.args.get('cliente_id', type=int)
    after_id   = request.args.get('after', 0, type=int)
    if not cliente_id:
        return jsonify({'erro': 'cliente_id obrigatório'}), 400
    q = Mensagem.query.filter_by(
        farmacia_id=farmacia.id, cliente_id=cliente_id
    ).filter(Mensagem.id > after_id).order_by(Mensagem.criado_em).all()
    # Marca mensagens do cliente como lidas
    for m in q:
        if m.remetente == 'cliente' and not m.lida:
            m.lida = True
    db.session.commit()
    return jsonify([m.to_dict() for m in q]), 200


@app.route('/api/collab/chat/enviar', methods=['POST'])
@collab_token_requerido
def collab_enviar_mensagem(farmacia):
    """Farmácia envia mensagem para um cliente."""
    dados      = request.get_json() or {}
    cliente_id = dados.get('cliente_id')
    texto      = (dados.get('texto') or '').strip()
    if not cliente_id or not texto:
        return jsonify({'erro': 'cliente_id e texto obrigatórios'}), 400
    msg = Mensagem(
        cliente_id  = cliente_id,
        farmacia_id = farmacia.id,
        texto       = texto,
        remetente   = 'farmacia',
        lida        = False
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify(msg.to_dict()), 201


@app.route('/api/collab/produtos/<int:produto_id>', methods=['DELETE'])
@collab_token_requerido
def collab_remover_produto(farmacia, produto_id):
    """Remove um produto da farmácia."""
    produto = Produto.query.filter_by(id=produto_id, farmacia_id=farmacia.id).first()
    if not produto:
        return jsonify({'erro': 'Produto não encontrado'}), 404
    db.session.delete(produto)
    db.session.commit()
    return jsonify({'mensagem': 'Produto removido com sucesso'}), 200

@app.route('/api/upload', methods=['POST'])
def upload_imagem():
    """
    Recebe multipart/form-data com campo 'file'.
    Envia para Cloudinary e retorna URL pública.
    """
    if 'file' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'erro': 'Arquivo sem nome'}), 400
    if not allowed_file(file.filename):
        return jsonify({'erro': 'Use PNG, JPG ou WEBP (máx 5MB).'}), 400

    try:
        # Envia direto para Cloudinary (sem salvar em disco)
        result = cloudinary.uploader.upload(
            file,
            folder       = 'idrugs',
            resource_type= 'image',
            quality      = 'auto',
            fetch_format = 'auto'
        )
        url = result['secure_url']  # https://res.cloudinary.com/...
        return jsonify({'url': url}), 200

    except Exception as e:
        app.logger.error(f"Cloudinary upload error: {e}")
        # Fallback: salva localmente
        try:
            ext      = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.stream.seek(0)
            file.save(filepath)
            url = f"/static/uploads/{filename}"
            return jsonify({'url': url, 'local': True}), 200
        except Exception as e2:
            return jsonify({'erro': f'Erro ao salvar imagem: {str(e2)}'}), 500


@app.route('/static/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/cadastro', methods=['POST'])
def cadastro():
    dados = request.get_json()
    nome  = dados.get('nome',  '').strip()
    email = dados.get('email', '').strip().lower()
    cpf   = dados.get('cpf',   '').strip()
    senha = dados.get('senha', '')

    if not all([nome, email, cpf, senha]):
        return jsonify({'erro': 'Todos os campos são obrigatórios'}), 400
    if not validar_email(email):
        return jsonify({'erro': 'E-mail inválido. Use o formato email@dominio.com'}), 400
    if not validar_cpf(cpf):
        return jsonify({'erro': 'CPF inválido. Verifique os dígitos verificadores'}), 400
    if len(senha) < 6:
        return jsonify({'erro': 'Senha deve ter no mínimo 6 caracteres'}), 400
    if Cliente.query.filter_by(email=email).first():
        return jsonify({'erro': 'E-mail já cadastrado'}), 409

    cpf_fmt = formatar_cpf(cpf)
    if Cliente.query.filter_by(cpf=cpf_fmt).first():
        return jsonify({'erro': 'CPF já cadastrado'}), 409

    cliente = Cliente(nome=nome, email=email, cpf=cpf_fmt)
    cliente.set_senha(senha)
    db.session.add(cliente)

    _invalidar_codigos_anteriores(email)
    codigo = _gerar_codigo()
    db.session.add(CodigoVerificacao(
        email=email, codigo=codigo,
        expira_em=datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    ))
    db.session.commit()

    email_enviado = enviar_email(email, 'iDrugs — Confirme seu cadastro', _html_cadastro(nome, codigo))
    resposta = {'mensagem': 'Cadastro realizado! Verifique seu e-mail para confirmar a conta.'}
    smtp_configurado = (
        EMAIL_USER and EMAIL_USER != 'seuemail@gmail.com' and
        EMAIL_PASSWORD and EMAIL_PASSWORD != 'sua_senha_de_app'
    )
    if not email_enviado:
        if smtp_configurado:
            # SMTP configurado mas falhou (ex: senha errada) — não expõe o código
            resposta['aviso'] = 'Falha ao enviar e-mail. Verifique as credenciais SMTP no .env'
        else:
            # SMTP não configurado (ambiente de desenvolvimento) — expõe o código localmente
            resposta['aviso'] = 'SMTP não configurado.'
            resposta['codigo_verificacao'] = codigo
    return jsonify(resposta), 201


@app.route('/api/verificar', methods=['POST'])
def verificar_email():
    dados  = request.get_json()
    email  = dados.get('email',  '').strip().lower()
    codigo = dados.get('codigo', '').strip()

    cod_obj = CodigoVerificacao.query.filter_by(
        email=email, codigo=codigo, usado=False
    ).order_by(CodigoVerificacao.criado_em.desc()).first()

    if not cod_obj:
        return jsonify({'erro': 'Código inválido'}), 400
    if datetime.datetime.utcnow() > cod_obj.expira_em:
        return jsonify({'erro': 'Código expirado. Solicite um novo.'}), 400

    cod_obj.usado = True
    db.session.commit()
    return jsonify({'mensagem': 'E-mail verificado com sucesso!'}), 200


@app.route('/api/login', methods=['POST'])
def login():
    dados = request.get_json()
    email = dados.get('email', '').strip().lower()
    senha = dados.get('senha', '')

    cliente = Cliente.query.filter_by(email=email).first()
    if not cliente or not cliente.check_senha(senha):
        return jsonify({'erro': 'E-mail ou senha incorretos'}), 401

    token = jwt.encode({
        'cliente_id': cliente.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token, 'cliente': cliente.to_dict()}), 200


@app.route('/api/esqueci-senha', methods=['POST'])
def esqueci_senha():
    dados = request.get_json()
    email = dados.get('email', '').strip().lower()

    if not validar_email(email):
        return jsonify({'erro': 'E-mail inválido'}), 400

    cliente = Cliente.query.filter_by(email=email).first()
    if not cliente:
        return jsonify({'mensagem': 'Se o e-mail estiver cadastrado, você receberá o código.'}), 200

    _invalidar_codigos_anteriores(email)
    codigo = _gerar_codigo()
    db.session.add(CodigoVerificacao(
        email=email, codigo=codigo,
        expira_em=datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    ))
    db.session.commit()

    email_enviado = enviar_email(email, 'iDrugs — Código de recuperação de senha', _html_recuperacao(cliente.nome, codigo))
    resposta = {'mensagem': 'Se o e-mail estiver cadastrado, você receberá o código.'}
    if not email_enviado:
        smtp_configurado_c = (
            EMAIL_USER and EMAIL_USER != 'seuemail@gmail.com' and
            EMAIL_PASSWORD and EMAIL_PASSWORD != 'sua_senha_de_app'
        )
        if smtp_configurado_c:
            resposta['aviso'] = 'Falha ao enviar e-mail. Verifique as credenciais SMTP no .env'
        else:
            resposta['aviso'] = 'SMTP não configurado.'
            resposta['codigo_verificacao'] = codigo
    return jsonify(resposta), 200


@app.route('/api/redefinir-senha', methods=['POST'])
def redefinir_senha():
    dados      = request.get_json()
    email      = dados.get('email',      '').strip().lower()
    codigo     = dados.get('codigo',     '').strip()
    nova_senha = dados.get('nova_senha', '')

    cod_obj = CodigoVerificacao.query.filter_by(
        email=email, codigo=codigo, usado=False
    ).order_by(CodigoVerificacao.criado_em.desc()).first()

    if not cod_obj or datetime.datetime.utcnow() > cod_obj.expira_em:
        return jsonify({'erro': 'Código inválido ou expirado'}), 400
    if len(nova_senha) < 6:
        return jsonify({'erro': 'Senha deve ter no mínimo 6 caracteres'}), 400

    cliente = Cliente.query.filter_by(email=email).first()
    cliente.set_senha(nova_senha)
    cod_obj.usado = True
    db.session.commit()
    return jsonify({'mensagem': 'Senha redefinida com sucesso!'}), 200


# ─────────────────────────────────────────────
# ROTAS — FARMÁCIAS (CLIENTE)
# ─────────────────────────────────────────────

@app.route('/api/farmacias', methods=['GET'])
@token_requerido
def listar_farmacias(cliente_atual):
    farmacias = Farmacia.query.filter_by(ativo=True).all()
    out = []
    for f in farmacias:
        info = calcular_frete(
            farm_cidade=f.cidade,
            farm_bairro=f.bairro,
            cli_cidade=getattr(cliente_atual, 'addr_cidade', None),
            cli_bairro=getattr(cliente_atual, 'addr_bairro', None),
        )
        d = f.to_dict()
        d['frete'] = info
        out.append(d)
    return jsonify(out), 200


# ─────────────────────────────────────────────
# ROTAS — PRODUTOS (CLIENTE)
# ─────────────────────────────────────────────

@app.route('/api/produtos/aleatorios', methods=['GET'])
@token_requerido
def produtos_aleatorios(cliente_atual):
    produtos = Produto.query.filter_by(ativo=True).order_by(db.func.random()).limit(6).all()
    return jsonify([p.to_dict() for p in produtos]), 200


@app.route('/api/produtos', methods=['GET'])
@token_requerido
def listar_produtos(cliente_atual):
    farmacia_id = request.args.get('farmacia_id', type=int)
    busca       = request.args.get('q', '')
    query = Produto.query.filter_by(ativo=True)
    if farmacia_id:
        query = query.filter_by(farmacia_id=farmacia_id)
    if busca:
        query = query.filter(Produto.nome.ilike(f'%{busca}%'))
    return jsonify([p.to_dict() for p in query.all()]), 200


@app.route('/api/produtos/<int:produto_id>', methods=['GET'])
@token_requerido
def detalhe_produto(cliente_atual, produto_id):
    produto = Produto.query.get_or_404(produto_id)
    return jsonify(produto.to_dict()), 200


# ─────────────────────────────────────────────
# ROTAS — PEDIDOS (CLIENTE)
# ─────────────────────────────────────────────

@app.route('/api/pedidos', methods=['POST'])
@token_requerido
def criar_pedido(cliente_atual):
    dados       = request.get_json() or {}
    farmacia_id = dados.get('farmacia_id')
    itens       = dados.get('itens', [])
    forma_pagto = dados.get('forma_pagamento', 'dinheiro')

    if not itens:
        return jsonify({'erro': 'Nenhum item informado'}), 400

    # Verifica se a farmácia existe no banco; se não, é demo — aceita pedido sem deduçao
    farmacia_real = Farmacia.query.get(farmacia_id) if farmacia_id else None

    total  = 0
    pedido = Pedido(
        cliente_id  = cliente_atual.id,
        farmacia_id = farmacia_id if farmacia_real else None,
        forma_pagto = forma_pagto
    )
    db.session.add(pedido)
    db.session.flush()

    for item in itens:
        produto_id  = item.get('produto_id')
        quantidade  = int(item.get('quantidade', 1))
        preco_unit  = float(item.get('preco', 0))
        nome_item   = item.get('nome', 'Produto')

        produto = Produto.query.get(produto_id) if produto_id else None

        if produto:
            # Produto real: deduz estoque
            if produto.estoque < quantidade:
                db.session.rollback()
                return jsonify({'erro': f'Estoque insuficiente para {produto.nome}'}), 400
            produto.estoque -= quantidade
            preco_unit = float(produto.preco)
        # Se produto não existe no DB (farmácia demo), registra com preço do payload

        db.session.add(ItemPedido(
            pedido_id  = pedido.id,
            produto_id = produto.id if produto else None,
            quantidade = quantidade,
            preco_unit = preco_unit,
            nome_item  = produto.nome if produto else nome_item,
            nome_farm  = farmacia_real.nome if farmacia_real else dados.get('farmacia_nome', '')
        ))
        total += preco_unit * quantidade

    # Garante que total nunca seja None/0 se há itens
    if total == 0 and pedido.itens:
        total = sum(float(it.preco_unit) * it.quantidade for it in pedido.itens)

    # Calcula frete
    info_frete = calcular_frete(
        farm_cidade=farmacia_real.cidade if farmacia_real else None,
        farm_bairro=farmacia_real.bairro if farmacia_real else None,
        cli_cidade=getattr(cliente_atual, 'addr_cidade', None),
        cli_bairro=getattr(cliente_atual, 'addr_bairro', None),
    )
    valor_frete = 0 if info_frete.get('sob_encomenda') else (info_frete.get('frete') or 0)

    pedido.total = round(total + valor_frete, 2)
    db.session.commit()
    return jsonify({
        'mensagem':    'Pedido criado com sucesso',
        'pedido_id':   pedido.id,
        'subtotal':    round(total, 2),
        'frete':       valor_frete,
        'frete_label': info_frete.get('frete_label', ''),
        'tempo_label': info_frete.get('tempo_label', ''),
        'total':       float(pedido.total),
    }), 201


@app.route('/api/pedidos', methods=['GET'])
@token_requerido
def listar_pedidos(cliente_atual):
    pedidos = Pedido.query.filter_by(cliente_id=cliente_atual.id)                         .order_by(Pedido.criado_em.desc()).all()
    resultado = []
    for p in pedidos:
        farm = Farmacia.query.get(p.farmacia_id) if p.farmacia_id else None
        itens_data = []
        for it in p.itens:
            prod = Produto.query.get(it.produto_id) if it.produto_id else None
            itens_data.append({
                'nome':       prod.nome if prod else (getattr(it,'nome_item',None) or 'Produto'),
                'quantidade': it.quantidade,
                'preco_unit': float(it.preco_unit),
                'subtotal':   float(it.preco_unit) * it.quantidade
            })
        total_calc = sum(i['subtotal'] for i in itens_data)
        val_total  = float(p.total) if p.total and float(p.total) > 0 else total_calc
        farm_nome  = farm.nome if farm else (
            getattr(p.itens[0], 'nome_farm', None) if p.itens else 'Farmácia')
        resultado.append({
            'id':               p.id,
            'farmacia_id':      p.farmacia_id,
            'farmacia_nome':    farm_nome or 'Farmácia',
            'farmacia_imagem':  farm.imagem_url or '' if farm else '',
            'status':           p.status,
            'total':            round(val_total, 2),
            'forma_pagto':      p.forma_pagto,
            'criado_em':        p.criado_em.strftime('%d/%m/%Y às %H:%M') if p.criado_em else '',
            'itens':            itens_data
        })
    return jsonify(resultado), 200


@app.route('/api/collab/cadastro', methods=['POST'])
def collab_cadastro():
    """
    Cadastra uma nova farmácia/colaborador.
    O CNPJ é validado pelo algoritmo oficial da Receita Federal.
    """
    dados  = request.get_json()
    nome   = dados.get('nome',     '').strip()
    cnpj   = dados.get('cnpj',     '').strip()
    email  = dados.get('email',    '').strip().lower()
    senha  = dados.get('senha',    '')
    tel    = dados.get('telefone', '').strip()
    ende   = dados.get('endereco', '').strip()
    cidade = dados.get('cidade',   '').strip()

    # ── Validações ────────────────────────────────────────────────────────────
    if not all([nome, cnpj, email, senha]):
        return jsonify({'erro': 'Nome, CNPJ, e-mail e senha são obrigatórios'}), 400

    if not validar_email(email):
        return jsonify({'erro': 'E-mail inválido. Use o formato email@dominio.com'}), 400

    if not validar_cnpj(cnpj):
        return jsonify({
            'erro': 'CNPJ inválido. Verifique o número informado. '
                    'Formato esperado: 00.000.000/0000-00 ou apenas os 14 dígitos.'
        }), 400

    if len(senha) < 6:
        return jsonify({'erro': 'Senha deve ter no mínimo 6 caracteres'}), 400

    if Farmacia.query.filter_by(email=email).first():
        return jsonify({'erro': 'E-mail já cadastrado'}), 409

    cnpj_fmt = formatar_cnpj(cnpj)
    if Farmacia.query.filter_by(cnpj=cnpj_fmt).first():
        return jsonify({'erro': 'CNPJ já cadastrado'}), 409

    # ── Persistência ──────────────────────────────────────────────────────────
    imagem_url_val = dados.get('imagem_url', '')
    farmacia = Farmacia(
        nome=nome, cnpj=cnpj_fmt, email=email,
        telefone=tel, endereco=ende, cidade=cidade
    )
    farmacia.set_senha(senha)
    db.session.add(farmacia)

    # OTP de ativação de conta
    _invalidar_codigos_anteriores(email)
    codigo = _gerar_codigo()
    db.session.add(CodigoVerificacao(
        email=email, codigo=codigo,
        expira_em=datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    ))
    db.session.commit()

    email_enviado = enviar_email(
        email,
        'iDrugs — Ative sua conta de colaborador',
        _html_cadastro_collab(nome, codigo)
    )
    resposta = {
        'mensagem': 'Farmácia pré-cadastrada! Verifique seu e-mail para ativar a conta.',
        'cnpj_formatado': cnpj_fmt
    }
    if not email_enviado:
        resposta['aviso'] = 'E-mail não pôde ser enviado (configure as variáveis SMTP).'
        resposta['codigo_verificacao'] = codigo  # remover em produção
    return jsonify(resposta), 201


@app.route('/api/collab/verificar', methods=['POST'])
def collab_verificar():
    """Confirma o OTP enviado ao e-mail da farmácia no cadastro."""
    dados  = request.get_json()
    email  = dados.get('email',  '').strip().lower()
    codigo = dados.get('codigo', '').strip()

    cod_obj = CodigoVerificacao.query.filter_by(
        email=email, codigo=codigo, usado=False
    ).order_by(CodigoVerificacao.criado_em.desc()).first()

    if not cod_obj:
        return jsonify({'erro': 'Código inválido'}), 400
    if datetime.datetime.utcnow() > cod_obj.expira_em:
        return jsonify({'erro': 'Código expirado. Solicite um novo.'}), 400

    cod_obj.usado = True
    db.session.commit()
    return jsonify({'mensagem': 'Conta ativada com sucesso!'}), 200


@app.route('/api/collab/login', methods=['POST'])
def collab_login():
    dados = request.get_json()
    email = dados.get('email', '').strip().lower()
    senha = dados.get('senha', '')

    farmacia = Farmacia.query.filter_by(email=email).first()
    if not farmacia or not farmacia.check_senha(senha):
        return jsonify({'erro': 'E-mail ou senha incorretos'}), 401

    token = jwt.encode({
        'farmacia_id': farmacia.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token, 'farmacia': farmacia.to_dict()}), 200


# ─────────────────────────────────────────────
# ROTAS — COLABORADOR — GESTÃO
# ─────────────────────────────────────────────

@app.route('/api/collab/farmacia', methods=['GET'])
@collab_token_requerido
def get_farmacia_collab(farmacia):
    return jsonify(farmacia.to_dict()), 200


@app.route('/api/collab/farmacia', methods=['PUT'])
@collab_token_requerido
def update_farmacia(farmacia):
    # Suporta JSON e multipart/form-data
    if request.content_type and 'multipart' in request.content_type:
        dados = request.form
        file  = request.files.get('file')
        if file and allowed_file(file.filename):
            ext      = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            farmacia.imagem_url = f"/static/uploads/{filename}"
    else:
        dados = request.get_json() or {}
        if 'imagem_url' in dados:
            img = dados['imagem_url']
            # Se for base64, salva como arquivo
            if img and img.startswith('data:image'):
                import base64, re as _re
                try:
                    header, data = img.split(',', 1)
                    ext = _re.search(r'image/(\w+)', header).group(1).replace('jpeg','jpg')
                    # Envia base64 direto ao Cloudinary
                    result = cloudinary.uploader.upload(
                        img, folder='idrugs', resource_type='image',
                        quality='auto', fetch_format='auto'
                    )
                    farmacia.imagem_url = result['secure_url']
                except Exception:
                    farmacia.imagem_url = img[:500] if img else None  # trunca se falhar
            elif img:
                farmacia.imagem_url = img

    if dados.get('nome'):     farmacia.nome     = dados['nome']
    if dados.get('telefone'): farmacia.telefone = dados['telefone']
    if dados.get('endereco'): farmacia.endereco = dados['endereco']
    if dados.get('cidade'):   farmacia.cidade   = dados['cidade']
    if dados.get('email'):    farmacia.email    = dados['email']
    # ── localidade / frete ──
    if 'estado' in dados:
        farmacia.estado = (dados.get('estado') or '').upper() or None
    if 'bairro' in dados:
        farmacia.bairro = dados.get('bairro') or None
    bairro_final = dados.get('bairro') or getattr(farmacia, 'bairro', None)
    if bairro_final:
        farmacia.regiao = regiao_do_bairro(bairro_final)
    db.session.commit()
    return jsonify({'mensagem': 'Farmácia atualizada!', 'farmacia': farmacia.to_dict()}), 200


@app.route('/api/collab/produtos', methods=['GET'])
@collab_token_requerido
def collab_listar_produtos(farmacia):
    busca = request.args.get('q', '')
    query = Produto.query.filter_by(farmacia_id=farmacia.id)
    if busca:
        query = query.filter(Produto.nome.ilike(f'%{busca}%'))
    return jsonify([p.to_dict() for p in query.all()]), 200


@app.route('/api/collab/produtos', methods=['POST'])
@collab_token_requerido
def collab_criar_produto(farmacia):
    dados = request.get_json()
    nome  = dados.get('nome', '').strip()
    preco = dados.get('preco')

    if not nome:
        return jsonify({'erro': 'Nome é obrigatório'}), 400
    if preco is None or float(preco) < 0:
        return jsonify({'erro': 'Preço inválido'}), 400

    produto = Produto(
        farmacia_id = farmacia.id,
        nome        = nome,
        descricao   = dados.get('descricao', ''),
        preco       = float(preco),
        estoque     = int(dados.get('estoque', 0)),
        categoria   = dados.get('categoria', ''),
        imagem_url  = dados.get('imagem_url') or None,
        ativo       = dados.get('ativo', True)
    )
    db.session.add(produto)
    db.session.commit()
    return jsonify({'mensagem': 'Produto criado!', 'produto': produto.to_dict()}), 201


@app.route('/api/collab/produtos/<int:produto_id>', methods=['PUT'])
@collab_token_requerido
def collab_atualizar_produto(farmacia, produto_id):
    produto = Produto.query.filter_by(id=produto_id, farmacia_id=farmacia.id).first()
    if not produto:
        return jsonify({'erro': 'Produto não encontrado'}), 404

    dados = request.get_json()
    produto.nome      = dados.get('nome',      produto.nome)
    produto.descricao = dados.get('descricao', produto.descricao)
    produto.preco     = dados.get('preco',     produto.preco)
    produto.estoque   = dados.get('estoque',   produto.estoque)
    produto.categoria = dados.get('categoria', produto.categoria)
    produto.ativo     = dados.get('ativo',     produto.ativo)
    if 'imagem_url' in dados:
        produto.imagem_url = dados['imagem_url'] or None
    db.session.commit()
    return jsonify({'mensagem': 'Produto atualizado!', 'produto': produto.to_dict()}), 200


@app.route('/api/collab/pedidos', methods=['GET'])
@collab_token_requerido
def collab_listar_pedidos(farmacia):
    status = request.args.get('status')
    query  = Pedido.query.filter_by(farmacia_id=farmacia.id)
    if status:
        query = query.filter_by(status=status)
    pedidos = query.order_by(Pedido.criado_em.desc()).all()
    return jsonify([{
        'id':          p.id,
        'cliente':     p.cliente.nome,
        'itens':       len(p.itens),
        'total':       float(p.total or 0),
        'forma_pagto': p.forma_pagto,
        'status':      p.status,
        'criado_em':   p.criado_em.isoformat()
    } for p in pedidos]), 200


@app.route('/api/collab/pedidos/<int:pedido_id>/status', methods=['PATCH'])
@collab_token_requerido
def collab_status_pedido(farmacia, pedido_id):
    pedido = Pedido.query.filter_by(id=pedido_id, farmacia_id=farmacia.id).first()
    if not pedido:
        return jsonify({'erro': 'Pedido não encontrado'}), 404

    dados       = request.get_json()
    novo_status = dados.get('status', '')
    validos     = ('pendente', 'confirmado', 'em_entrega', 'entregue', 'cancelado')
    if novo_status not in validos:
        return jsonify({'erro': f'Status inválido. Valores aceitos: {", ".join(validos)}'}), 400

    pedido.status = novo_status
    db.session.commit()
    return jsonify({'mensagem': f'Status atualizado para {novo_status}'}), 200


@app.route('/api/collab/clientes', methods=['GET'])
@collab_token_requerido
def collab_listar_clientes(farmacia):
    pedidos      = Pedido.query.filter_by(farmacia_id=farmacia.id).all()
    clientes_ids = {p.cliente_id for p in pedidos}
    clientes     = Cliente.query.filter(Cliente.id.in_(clientes_ids)).all()
    return jsonify([c.to_dict() for c in clientes]), 200


# ─────────────────────────────────────────────
# ROTA — CADASTRAR FARMÁCIA (com validação completa de CNPJ)
# ─────────────────────────────────────────────

@app.route('/api/cadastrar-farmacia', methods=['POST'])
def cadastrar_farmacia():
    """
    Cadastra uma nova farmácia validando o CNPJ pelo algoritmo oficial da Receita Federal.

    Body JSON:
        nome     (str, obrigatório) — nome da farmácia
        cnpj     (str, obrigatório) — CNPJ com ou sem formatação; validado e formatado automaticamente
        email    (str, obrigatório) — e-mail único da farmácia
        senha    (str, obrigatório) — mínimo 6 caracteres
        telefone (str, opcional)
        endereco (str, opcional)
        cidade   (str, opcional)

    Processo de validação do CNPJ:
      1. Remove pontuação com re.sub(r'[^0-9]', '', cnpj)
      2. Verifica comprimento = 14 dígitos
      3. Rejeita sequências uniformes (11111111111111 etc.)
      4. Calcula 1° DV com pesos [5,4,3,2,9,8,7,6,5,4,3,2]
      5. Calcula 2° DV com pesos [6,5,4,3,2,9,8,7,6,5,4,3,2]
      6. Armazena no formato 00.000.000/0000-00

    Retorna:
        201 — farmácia cadastrada, OTP enviado ao e-mail
        400 — dados inválidos (CNPJ, e-mail ou senha)
        409 — e-mail ou CNPJ já cadastrado
    """
    data = request.get_json() or {}

    nome     = (data.get('nome')     or '').strip()
    cnpj     = (data.get('cnpj')     or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    senha    = (data.get('senha')    or '')
    telefone = (data.get('telefone') or '').strip()
    endereco = (data.get('endereco') or '').strip()
    cidade   = (data.get('cidade')   or '').strip()

    # ── Campos obrigatórios ───────────────────────────────────────────────────
    if not all([nome, cnpj, email, senha]):
        return jsonify({'erro': 'Nome, CNPJ, e-mail e senha são obrigatórios'}), 400

    # ── Validação de CNPJ (algoritmo Receita Federal) ─────────────────────────
    if not validar_cnpj(cnpj):
        return jsonify({
            'erro': 'CNPJ inválido.',
            'detalhe': (
                'O CNPJ informado não passou na validação dos dígitos verificadores. '
                'Verifique se todos os 14 dígitos estão corretos. '
                'Formatos aceitos: 00.000.000/0000-00 ou 00000000000000.'
            )
        }), 400

    # ── Validação de e-mail ───────────────────────────────────────────────────
    if not validar_email(email):
        return jsonify({'erro': 'E-mail inválido. Use o formato email@dominio.com'}), 400

    # ── Validação de senha ────────────────────────────────────────────────────
    if len(senha) < 6:
        return jsonify({'erro': 'Senha deve ter no mínimo 6 caracteres'}), 400

    # ── Unicidade ─────────────────────────────────────────────────────────────
    if Farmacia.query.filter_by(email=email).first():
        return jsonify({'erro': 'E-mail já cadastrado para outra farmácia'}), 409

    cnpj_formatado = formatar_cnpj(cnpj)
    if Farmacia.query.filter_by(cnpj=cnpj_formatado).first():
        return jsonify({'erro': 'CNPJ já cadastrado para outra farmácia'}), 409

    # ── Hash da senha e persistência ──────────────────────────────────────────
    farmacia = Farmacia(
        nome=nome, cnpj=cnpj_formatado, email=email,
        telefone=telefone, endereco=endereco, cidade=cidade
    )
    farmacia.set_senha(senha)
    db.session.add(farmacia)

    # ── OTP de ativação ───────────────────────────────────────────────────────
    _invalidar_codigos_anteriores(email)
    codigo = _gerar_codigo()
    db.session.add(CodigoVerificacao(
        email=email, codigo=codigo,
        expira_em=datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
    ))
    db.session.commit()

    email_enviado = enviar_email(
        email,
        'iDrugs — Ative sua conta de colaborador',
        _html_cadastro_collab(nome, codigo)
    )

    resposta = {
        'mensagem':    'Farmácia cadastrada com sucesso! Verifique o e-mail para ativar a conta.',
        'cnpj':        cnpj_formatado,
        'farmacia_id': farmacia.id,
    }
    if not email_enviado:
        resposta['aviso']              = 'E-mail não pôde ser enviado (configure as variáveis SMTP).'
        resposta['codigo_verificacao'] = codigo   # ← remover em produção
    return jsonify(resposta), 201


# ─────────────────────────────────────────────
# UTILITÁRIO — VALIDAR CNPJ ISOLADO (para testes externos)
# ─────────────────────────────────────────────

@app.route('/api/utils/validar-cnpj', methods=['POST'])
def util_validar_cnpj():
    """
    Endpoint de utilidade para validar um CNPJ sem autenticação.
    Útil para validação em tempo real no frontend.
    Body: { "cnpj": "00.000.000/0000-00" }
    """
    dados = request.get_json()
    cnpj  = dados.get('cnpj', '').strip()

    if not cnpj:
        return jsonify({'erro': 'CNPJ não informado'}), 400

    valido = validar_cnpj(cnpj)
    resposta = {
        'cnpj_informado': cnpj,
        'valido': valido,
    }
    if valido:
        resposta['cnpj_formatado'] = formatar_cnpj(cnpj)
    else:
        resposta['mensagem'] = (
            'CNPJ inválido. Verifique se o número está correto. '
            'Formatos aceitos: 00.000.000/0000-00 ou 00000000000000.'
        )
    return jsonify(resposta), 200 if valido else 422

# ─────────────────────────────────────────────
# ROTAS — PERFIL DO CLIENTE
# ─────────────────────────────────────────────

@app.route('/api/perfil', methods=['GET'])
@token_requerido
def get_perfil(cliente_atual):
    """Retorna os dados do perfil do cliente autenticado."""
    return jsonify(cliente_atual.to_dict()), 200


@app.route('/api/perfil', methods=['PUT'])
@token_requerido
def update_perfil(cliente_atual):
    """
    Atualiza dados do perfil do cliente.
    Body JSON (todos opcionais):
      { "nome", "telefone", "endereco",
        "addr_rua", "addr_num", "addr_bairro", "addr_cep", "addr_ref" }
    E-mail e CPF nao podem ser alterados por este endpoint.
    """
    dados = request.get_json() or {}

    def _s(key):
        return (dados.get(key) or '').strip()

    if _s('nome'):     cliente_atual.nome     = _s('nome')
    if _s('telefone'): cliente_atual.telefone = _s('telefone')
    if _s('endereco'): cliente_atual.endereco = _s('endereco')

    # Campos detalhados de endereço
    for field in ('addr_rua', 'addr_num', 'addr_bairro', 'addr_cep', 'addr_ref',
                  'addr_estado', 'addr_cidade'):
        if field in dados:
            setattr(cliente_atual, field, _s(field) or None)

    # Recalcula região a partir do bairro salvo
    bairro_salvo = _s('addr_bairro') or getattr(cliente_atual, 'addr_bairro', None)
    if bairro_salvo:
        cliente_atual.addr_regiao = regiao_do_bairro(bairro_salvo) or cliente_atual.addr_regiao

    # Monta endereco completo se nao veio pronto
    if not _s('endereco') and (_s('addr_rua') or _s('addr_bairro')):
        partes = []
        rua = _s('addr_rua'); num = _s('addr_num')
        bairro = _s('addr_bairro'); cep = _s('addr_cep'); ref = _s('addr_ref')
        if rua:    partes.append(rua + (', ' + num if num else ''))
        if bairro: partes.append(bairro)
        if cep:    partes.append('CEP ' + cep)
        if ref:    partes.append('Ref: ' + ref)
        cliente_atual.endereco = ' — '.join(partes)

    db.session.commit()
    return jsonify({'mensagem': 'Perfil atualizado!', 'cliente': cliente_atual.to_dict()}), 200


@app.route('/api/perfil/senha', methods=['PUT'])
@token_requerido
def alterar_senha(cliente_atual):
    """
    Altera a senha do cliente autenticado.
    Body JSON: { "senha_atual": "...", "nova_senha": "..." }
    """
    dados       = request.get_json() or {}
    senha_atual = dados.get('senha_atual', '')
    nova_senha  = dados.get('nova_senha',  '')
    if not cliente_atual.check_senha(senha_atual):
        return jsonify({'erro': 'Senha atual incorreta'}), 401
    if len(nova_senha) < 6:
        return jsonify({'erro': 'Nova senha deve ter no mínimo 6 caracteres'}), 400
    cliente_atual.set_senha(nova_senha)
    db.session.commit()
    return jsonify({'mensagem': 'Senha alterada com sucesso!'}), 200


# ─────────────────────────────────────────────
# ROTAS — PEDIDOS: DETALHE, RASTREIO E CANCELAR
# ─────────────────────────────────────────────

@app.route('/api/pedidos/<int:pedido_id>', methods=['GET'])
@token_requerido
def detalhe_pedido(cliente_atual, pedido_id):
    """Retorna detalhes completos de um pedido do cliente, incluindo itens."""
    pedido = Pedido.query.filter_by(id=pedido_id, cliente_id=cliente_atual.id).first()
    if not pedido:
        return jsonify({'erro': 'Pedido não encontrado'}), 404
    return jsonify({
        'id':          pedido.id,
        'farmacia_id': pedido.farmacia_id,
        'farmacia':    pedido.farmacia.nome,
        'status':      pedido.status,
        'total':       float(pedido.total or 0),
        'forma_pagto': pedido.forma_pagto,
        'criado_em':   pedido.criado_em.isoformat(),
        'itens': [{
            'produto_id': i.produto_id,
            'produto':    i.produto.nome,
            'quantidade': i.quantidade,
            'preco_unit': float(i.preco_unit),
            'subtotal':   float(i.preco_unit) * i.quantidade,
        } for i in pedido.itens]
    }), 200


@app.route('/api/pedidos/<int:pedido_id>/confirmar-entrega', methods=['POST'])
@token_requerido
def confirmar_entrega_cliente(cliente_atual, pedido_id):
    """
    Cliente confirma que recebeu o pedido.
    Transição válida: em_entrega → entregue
    """
    pedido = Pedido.query.filter_by(id=pedido_id, cliente_id=cliente_atual.id).first()
    if not pedido:
        return jsonify({'erro': 'Pedido não encontrado'}), 404
    if pedido.status not in ('em_entrega', 'confirmado', 'pendente'):
        return jsonify({'erro': f'Não é possível confirmar entrega no status atual: {pedido.status}'}), 400
    pedido.status = 'entregue'
    db.session.commit()
    return jsonify({'mensagem': 'Entrega confirmada com sucesso!', 'status': 'entregue'}), 200


@app.route('/api/pedidos/<int:pedido_id>/rastrear', methods=['GET'])
@token_requerido
def rastrear_pedido(cliente_atual, pedido_id):
    """
    Retorna o status de rastreio detalhado de um pedido.
    Ciclo: pendente → confirmado → em_entrega → entregue | cancelado
    Resposta inclui etapas concluidas, etapa atual e dados resumidos.
    """
    pedido = Pedido.query.filter_by(id=pedido_id, cliente_id=cliente_atual.id).first()
    if not pedido:
        return jsonify({'erro': 'Pedido não encontrado'}), 404

    etapas = ['pendente', 'confirmado', 'em_entrega', 'entregue']
    labels = {
        'pendente':   'Pedido recebido pela farmácia',
        'confirmado': 'Estamos preparando seu pedido',
        'em_entrega': 'Pedido em rota de entrega!',
        'entregue':   'Pedido entregue!',
        'cancelado':  'Pedido cancelado',
    }
    status_atual = pedido.status
    idx_atual    = etapas.index(status_atual) if status_atual in etapas else -1

    rastreio = [{
        'etapa':     etapa,
        'label':     labels[etapa],
        'concluida': i <= idx_atual,
        'atual':     i == idx_atual,
    } for i, etapa in enumerate(etapas)]

    return jsonify({
        'pedido_id':  pedido.id,
        'status':     status_atual,
        'cancelado':  status_atual == 'cancelado',
        'farmacia':   pedido.farmacia.nome,
        'total':      float(pedido.total or 0),
        'criado_em':  pedido.criado_em.isoformat(),
        'rastreio':   rastreio,
        'itens':      [f"{i.quantidade}x {i.produto.nome}" for i in pedido.itens],
    }), 200


@app.route('/api/pedidos/<int:pedido_id>/cancelar', methods=['PATCH'])
@token_requerido
def cancelar_pedido(cliente_atual, pedido_id):
    """
    Cancela um pedido ainda em status 'pendente'.
    Pedidos confirmados ou em entrega nao podem ser cancelados pelo cliente.
    O estoque dos itens e restaurado automaticamente.
    """
    pedido = Pedido.query.filter_by(id=pedido_id, cliente_id=cliente_atual.id).first()
    if not pedido:
        return jsonify({'erro': 'Pedido não encontrado'}), 404
    if pedido.status != 'pendente':
        return jsonify({'erro': f'Pedido não pode ser cancelado. Status: {pedido.status}.'}), 409
    for item in pedido.itens:
        item.produto.estoque += item.quantidade
    pedido.status = 'cancelado'
    db.session.commit()
    return jsonify({'mensagem': 'Pedido cancelado com sucesso.'}), 200


# ─────────────────────────────────────────────
# ROTAS — COLABORADOR: DELETE E TOGGLE PRODUTO
# ─────────────────────────────────────────────

@app.route('/api/collab/produtos/<int:produto_id>', methods=['DELETE'])
@collab_token_requerido
def collab_deletar_produto(farmacia, produto_id):
    """Remove permanentemente um produto da farmácia."""
    produto = Produto.query.filter_by(id=produto_id, farmacia_id=farmacia.id).first()
    if not produto:
        return jsonify({'erro': 'Produto não encontrado'}), 404
    db.session.delete(produto)
    db.session.commit()
    return jsonify({'mensagem': 'Produto removido.'}), 200


@app.route('/api/collab/produtos/<int:produto_id>/toggle', methods=['PATCH'])
@collab_token_requerido
def collab_toggle_produto(farmacia, produto_id):
    """Alterna ativo/inativo de um produto sem removê-lo do banco."""
    produto = Produto.query.filter_by(id=produto_id, farmacia_id=farmacia.id).first()
    if not produto:
        return jsonify({'erro': 'Produto não encontrado'}), 404
    produto.ativo = not produto.ativo
    db.session.commit()
    estado = 'ativado' if produto.ativo else 'inativado'
    return jsonify({'mensagem': f'Produto {estado}.', 'produto': produto.to_dict()}), 200


# ─────────────────────────────────────────────
# ROTAS — COLABORADOR: DASHBOARD / MÉTRICAS
# ─────────────────────────────────────────────

@app.route('/api/collab/dashboard', methods=['GET'])
@collab_token_requerido
def collab_dashboard(farmacia):
    """
    Métricas reais do dashboard: vendas, pedidos e clientes do banco.
    Total calculado via itens_pedido como fallback para pedidos com total NULL/0.
    """
    from sqlalchemy import func

    hoje       = datetime.datetime.utcnow().date()
    inicio_dia = datetime.datetime.combine(hoje, datetime.time.min)
    fim_dia    = datetime.datetime.combine(hoje, datetime.time.max)
    ATIVOS     = ('pendente', 'confirmado', 'em_entrega', 'entregue')

    status_counts = {
        s: Pedido.query.filter_by(farmacia_id=farmacia.id, status=s).count()
        for s in ATIVOS + ('cancelado',)
    }

    def _soma_real(pedidos_lista):
        """Soma totais; usa itens como fallback quando total é NULL/0."""
        total = 0.0
        to_fix = []
        for p in pedidos_lista:
            val = float(p.total or 0)
            if val > 0:
                total += val
            else:
                itens_soma = db.session.query(
                    func.sum(ItemPedido.preco_unit * ItemPedido.quantidade)
                ).filter_by(pedido_id=p.id).scalar() or 0
                val = float(itens_soma)
                total += val
                if val > 0:
                    p.total = round(val, 2)
                    to_fix.append(p)
        if to_fix:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return round(total, 2)

    # Vendas do dia (todos os não cancelados)
    pedidos_hoje = Pedido.query.filter(
        Pedido.farmacia_id == farmacia.id,
        Pedido.status.in_(ATIVOS),
        Pedido.criado_em.between(inicio_dia, fim_dia)
    ).all()
    vendas_dia = _soma_real(pedidos_hoje)

    # Receita total histórica
    todos_pedidos = Pedido.query.filter(
        Pedido.farmacia_id == farmacia.id,
        Pedido.status.in_(ATIVOS)
    ).all()
    receita_total = _soma_real(todos_pedidos)

    estoque_baixo = Produto.query.filter(
        Produto.farmacia_id == farmacia.id,
        Produto.ativo == True,
        Produto.estoque < 10
    ).count()

    clientes_unicos = db.session.query(
        func.count(func.distinct(Pedido.cliente_id))
    ).filter_by(farmacia_id=farmacia.id).scalar() or 0

    return jsonify({
        'farmacia':       farmacia.nome,
        'pedidos':        status_counts,
        'vendas_hoje':    vendas_dia,
        'pedidos_hoje':   len(pedidos_hoje),
        'receita_total':  receita_total,
        'estoque_baixo':  estoque_baixo,
        'clientes_total': clientes_unicos,
    }), 200



@app.route('/api/collab/vendas-por-dia', methods=['GET'])
@collab_token_requerido
def collab_vendas_por_dia(farmacia):
    """
    Retorna total de vendas por dia para o período solicitado.
    Parâmetros: dias (default 15), data_inicio, data_fim (YYYY-MM-DD)
    """
    from sqlalchemy import func, cast, Date

    # Período
    try:
        dias = int(request.args.get('dias', 15))
        dias = min(max(dias, 1), 365)
    except Exception:
        dias = 15

    data_inicio_str = request.args.get('data_inicio')
    data_fim_str    = request.args.get('data_fim')

    hoje = datetime.datetime.utcnow().date()
    if data_fim_str:
        try: data_fim = datetime.date.fromisoformat(data_fim_str)
        except Exception: data_fim = hoje
    else:
        data_fim = hoje

    if data_inicio_str:
        try: data_inicio = datetime.date.fromisoformat(data_inicio_str)
        except Exception: data_inicio = data_fim - datetime.timedelta(days=dias-1)
    else:
        data_inicio = data_fim - datetime.timedelta(days=dias-1)

    # Consulta agrupada por dia
    rows = db.session.query(
        cast(Pedido.criado_em, Date).label('dia'),
        func.sum(Pedido.total).label('total'),
        func.count(Pedido.id).label('qtd')
    ).filter(
        Pedido.farmacia_id == farmacia.id,
        Pedido.status.in_(['confirmado', 'em_entrega', 'entregue']),
        Pedido.criado_em >= datetime.datetime.combine(data_inicio, datetime.time.min),
        Pedido.criado_em <= datetime.datetime.combine(data_fim,    datetime.time.max)
    ).group_by(cast(Pedido.criado_em, Date))     .order_by(cast(Pedido.criado_em, Date)).all()

    # Recalcula totais via itens onde necessário
    vendas_map = {}
    for r in rows:
        dia_str = str(r.dia)
        total_dia = float(r.total or 0)
        if total_dia == 0:
            # Fallback: soma dos itens para esse dia
            from sqlalchemy import cast as _cast, Date as _Date
            total_itens = db.session.query(
                func.sum(ItemPedido.preco_unit * ItemPedido.quantidade)
            ).join(Pedido, ItemPedido.pedido_id == Pedido.id).filter(
                Pedido.farmacia_id == farmacia.id,
                Pedido.status.in_(['pendente','confirmado','em_entrega','entregue']),
                _cast(Pedido.criado_em, _Date) == r.dia
            ).scalar() or 0
            total_dia = float(total_itens)
        vendas_map[dia_str] = {'total': total_dia, 'qtd': int(r.qtd)}
    resultado  = []
    d = data_inicio
    while d <= data_fim:
        ds = str(d)
        resultado.append({
            'data':  ds,
            'label': d.strftime('%d/%m'),
            'total': vendas_map.get(ds, {}).get('total', 0),
            'qtd':   vendas_map.get(ds, {}).get('qtd',   0),
        })
        d += datetime.timedelta(days=1)

    return jsonify({
        'data_inicio': str(data_inicio),
        'data_fim':    str(data_fim),
        'vendas':      resultado,
        'total_geral': sum(v['total'] for v in resultado),
        'total_pedidos': sum(v['qtd'] for v in resultado),
    }), 200


@app.route('/api/collab/notificacoes', methods=['GET'])
@collab_token_requerido
def collab_notificacoes(farmacia):
    """Últimas 20 ações dos clientes nesta farmácia."""
    pedidos = Pedido.query.filter_by(farmacia_id=farmacia.id)                          .order_by(Pedido.criado_em.desc()).limit(20).all()
    agora = datetime.datetime.utcnow()
    resultado = []
    for p in pedidos:
        cli = Cliente.query.get(p.cliente_id)
        nome = cli.nome.split()[0] if cli else 'Cliente'
        diff = agora - p.criado_em if p.criado_em else datetime.timedelta(0)
        mins = int(diff.total_seconds() / 60)
        if mins < 60:    tempo = f'{mins} min atrás'
        elif mins < 1440: tempo = f'{mins//60}h atrás'
        else:             tempo = f'{mins//1440}d atrás'

        acao_map = {
            'pendente':   'Realizou um novo pedido',
            'confirmado': 'Pedido confirmado',
            'em_entrega': 'Pedido saiu para entrega',
            'entregue':   'Pedido entregue',
            'cancelado':  'Cancelou o pedido',
        }
        resultado.append({
            'cliente': nome,
            'acao':    acao_map.get(p.status, 'Atualizou pedido'),
            'tempo':   tempo,
            'status':  p.status,
            'pedido_id': p.id,
        })
    return jsonify(resultado), 200

# ─────────────────────────────────────────────
# ROTAS — CHAT (base para integração futura)
# ─────────────────────────────────────────────

@app.route('/api/chat/conversas', methods=['GET'])
@token_requerido
def listar_conversas(cliente_atual):
    """
    Lista farmácias com que o cliente trocou mensagens.
    Inclui preview da última mensagem e contagem não lidas.
    """
    try:
        # Farmácias com mensagens
        msgs = Mensagem.query.filter_by(cliente_id=cliente_atual.id)                             .order_by(Mensagem.criado_em.desc()).all()
        farm_seen = {}
        for m in msgs:
            fid = m.farmacia_id
            if fid not in farm_seen:
                farm_seen[fid] = {
                    'ultima_msg':   m.texto[:60],
                    'hora':         m.criado_em.strftime('%H:%M') if m.criado_em else '',
                    'nao_lidas':    0
                }
            if m.remetente == 'farmacia' and not m.lida:
                farm_seen[fid]['nao_lidas'] += 1

        resultado = []
        for fid, info in farm_seen.items():
            farm = Farmacia.query.get(fid)
            if farm:
                resultado.append({
                    'farmacia_id':   farm.id,
                    'farmacia_nome': farm.nome,
                    'imagem_url':    farm.imagem_url or '',
                    'ultima_msg':    info['ultima_msg'],
                    'hora':          info['hora'],
                    'nao_lidas':     info['nao_lidas'],
                })

        # Farmácias com pedidos mas sem mensagens ainda
        pedidos = Pedido.query.filter_by(cliente_id=cliente_atual.id).all()
        farm_ids_pedido = list({p.farmacia_id for p in pedidos if p.farmacia_id})
        for fid in farm_ids_pedido:
            if fid not in farm_seen:
                farm = Farmacia.query.get(fid)
                if farm:
                    resultado.append({
                        'farmacia_id':   farm.id,
                        'farmacia_nome': farm.nome,
                        'imagem_url':    farm.imagem_url or '',
                        'ultima_msg':    'Iniciar conversa',
                        'hora':          '',
                        'nao_lidas':     0,
                    })

        return jsonify(resultado), 200
    except Exception as e:
        return jsonify([]), 200




# ─────────────────────────────────────────────
# SEED
# ─────────────────────────────────────────────

@app.route('/api/seed', methods=['GET','POST'])
def seed():
    if os.getenv('FLASK_ENV') == 'production':
        return jsonify({'erro': 'Não disponível em produção'}), 403

    if not Farmacia.query.first():
        farmacias_dados = [
            # CNPJs gerados com dígitos verificadores corretos (algoritmo RFB)
            ('iDrugs Farmácia',   '11.222.333/0001-81', 'contato@idrugs.com.br',    '(85) 99999-0000', 'Av. Beira Mar, 100',           'Fortaleza'),
            ('FarmaVida',         '98.765.432/0001-98', 'contato@farmavida.com.br', '(85) 88888-1111', 'Rua dos Jangadeiros, 55',       'Fortaleza'),
            ('Drogaria Saúde+',   '12.345.678/0001-95', 'contato@saude.com.br',     '(85) 77777-2222', 'Av. Washington Soares, 200',    'Fortaleza'),
        ]
        farmacias = []
        for nome, cnpj, email, tel, ende, cidade in farmacias_dados:
            f = Farmacia(nome=nome, cnpj=cnpj, email=email, telefone=tel, endereco=ende, cidade=cidade)
            f.set_senha('123456')
            db.session.add(f)
            farmacias.append(f)
        db.session.flush()

        f1, f2, f3 = farmacias
        produtos_por_farmacia = {
            # iDrugs — farmácia principal, alto giro
            f1.id: [
                ('Dipirona 500mg',    'Cxa 10comp',    6.49, 280, 'Analgésico'),
                ('Paracetamol 500mg', 'Cxa 20comp',    9.89, 310, 'Analgésico'),
                ('Ibuprofeno 400mg',  'Cxa 12comp',   12.89, 240, 'Anti-inflamatório'),
                ('Amoxicilina 500mg', 'Cxa 21cap',    24.90, 175, 'Antibiótico'),
                ('Ambroxol',          'Frasco 120ml', 18.50, 190, 'Expectorante'),
            ],
            # FarmaVida — foco em suplementos e crônicos
            f2.id: [
                ('Vitamina C',       'Tubo 50comp', 14.90, 350, 'Suplemento'),
                ('Loratadina 10mg',  'Cxa 12comp',   8.50, 220, 'Antialérgico'),
                ('Omeprazol 20mg',   'Cxa 28cap',   22.00, 165, 'Gastro'),
            ],
            # Drogaria Saúde+ — menor volume, produtos mais especializados
            f3.id: [
                ('Buscopan Simples', 'Cxa 10comp',  11.90, 130, 'Espasmolítico'),
                ('Rivotril 2mg',     'Cxa 30comp',  35.00,  75, 'Ansiolítico'),
            ],
        }
        for farm_id, prods in produtos_por_farmacia.items():
            for nome, desc, preco, estoque, cat in prods:
                db.session.add(Produto(farmacia_id=farm_id, nome=nome, descricao=desc,
                                       preco=preco, estoque=estoque, categoria=cat))
        db.session.commit()
        return jsonify({'mensagem': 'Seed realizado: 3 farmácias + produtos criados.'}), 201

    return jsonify({'mensagem': 'Banco já possui dados. Seed ignorado.'}), 200


# Cria tabelas automaticamente ao iniciar (funciona com flask run e python app.py)
class Mensagem(db.Model):
    __tablename__ = 'mensagens'
    id           = db.Column(db.Integer, primary_key=True)
    cliente_id   = db.Column(db.Integer, nullable=False)
    farmacia_id  = db.Column(db.Integer, nullable=False)
    texto        = db.Column(db.Text, nullable=False)
    remetente    = db.Column(db.String(20), nullable=False)  # 'cliente' ou 'farmacia'
    lida         = db.Column(db.Boolean, default=False)
    criado_em    = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            'id':         self.id,
            'cliente_id': self.cliente_id,
            'farmacia_id':self.farmacia_id,
            'texto':      self.texto,
            'remetente':  self.remetente,
            'lida':       self.lida,
            'hora':       self.criado_em.strftime('%H:%M') if self.criado_em else '',
            'criado_em':  self.criado_em.isoformat() if self.criado_em else ''
        }


with app.app_context():
    db.create_all()
    # Migração segura: adiciona colunas novas sem derrubar o banco
    try:
        from sqlalchemy import text
        migrações = [
            "ALTER TABLE farmacias    ADD COLUMN IF NOT EXISTS imagem_url  TEXT",
            "ALTER TABLE clientes     ADD COLUMN IF NOT EXISTS telefone    VARCHAR(20)",
            "ALTER TABLE clientes     ADD COLUMN IF NOT EXISTS endereco    VARCHAR(255)",
            "ALTER TABLE clientes     ADD COLUMN IF NOT EXISTS addr_rua    VARCHAR(150)",
            "ALTER TABLE clientes     ADD COLUMN IF NOT EXISTS addr_num    VARCHAR(20)",
            "ALTER TABLE clientes     ADD COLUMN IF NOT EXISTS addr_bairro VARCHAR(100)",
            "ALTER TABLE clientes     ADD COLUMN IF NOT EXISTS addr_cep    VARCHAR(10)",
            "ALTER TABLE clientes     ADD COLUMN IF NOT EXISTS addr_ref    VARCHAR(200)",
            "ALTER TABLE produtos     ADD COLUMN IF NOT EXISTS imagem_url  TEXT",
            "ALTER TABLE produtos     ADD COLUMN IF NOT EXISTS status      VARCHAR(20) DEFAULT 'ativo'",
            # Remove NOT NULL do produto_id em itens_pedido (para suportar farmácias demo)
            "ALTER TABLE itens_pedido ALTER COLUMN produto_id DROP NOT NULL",
            # Adiciona coluna nome_item para registrar nome quando produto é demo
            "ALTER TABLE itens_pedido ADD COLUMN IF NOT EXISTS nome_item  VARCHAR(150)",
            "ALTER TABLE itens_pedido ADD COLUMN IF NOT EXISTS nome_farm  VARCHAR(150)",
            # Adiciona total ao pedido se não existir
            "ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS total NUMERIC(10,2) DEFAULT 0",
            # Colunas de localidade — farmácia
            "ALTER TABLE farmacias ADD COLUMN IF NOT EXISTS estado VARCHAR(2)",
            "ALTER TABLE farmacias ADD COLUMN IF NOT EXISTS bairro VARCHAR(100)",
            "ALTER TABLE farmacias ADD COLUMN IF NOT EXISTS regiao VARCHAR(20)",
            # Colunas de localidade — cliente
            "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS addr_estado VARCHAR(2)",
            "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS addr_cidade VARCHAR(100)",
            "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS addr_regiao VARCHAR(20)",
            # Recalcula total de pedidos onde total está zerado/nulo
            """UPDATE pedidos SET total = sub.soma
               FROM (
                 SELECT pedido_id, SUM(preco_unit * quantidade) AS soma
                 FROM itens_pedido GROUP BY pedido_id
               ) sub
               WHERE pedidos.id = sub.pedido_id
               AND (pedidos.total IS NULL OR pedidos.total = 0)""",
        ]
        with db.engine.connect() as conn:
            for sql in migrações:
                try:
                    conn.execute(text(sql))
                except Exception:
                    pass
            conn.commit()
        print("✅ Migrações aplicadas com sucesso")
    except Exception as e:
        print(f"⚠️  Migração: {e}")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
