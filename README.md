Idrugs – Sistema de Gestão de Entrega para Farmácias

> Projeto acadêmico desenvolvido como trabalho de conclusão de curso / disciplina de Engenharia de Software.

Sobre o Projeto

O **iDrugs** é uma plataforma web de delivery de medicamentos focada em **Juazeiro do Norte – CE**. Conecta clientes a farmácias locais, permitindo busca de produtos, pedidos online e acompanhamento de entrega com cálculo de frete baseado na localização real dos bairros da cidade.

Funcionalidades

### Cliente (index.html)
- Cadastro e login com verificação por e-mail (OTP)
- Busca de farmácias e medicamentos
- Carrinho de compras individual por usuário
- Cálculo de frete automático por bairro
- Checkout com múltiplas formas de pagamento (Pix, Dinheiro, Cartão)
- Histórico de pedidos
- Endereço de entrega com cascata Estado → Cidade → Bairro

### Farmacêutico / Colaborador (colaborador.html)
- Painel de gerenciamento de pedidos em tempo real
- Cadastro e edição de produtos
- Gestão de dados da farmácia (endereço, foto, contato)
- Chat com clientes
- Dashboard com métricas

### Backend (app.py)
- API REST com Flask
- Autenticação JWT
- Integração com PostgreSQL via SQLAlchemy
- Cálculo de frete por coordenadas GPS (fórmula de Haversine)
- Envio de e-mail para verificação de conta e recuperação de senha

## Cálculo de Frete

O frete é calculado com base na distância real (Haversine) entre os bairros de Juazeiro do Norte:

| Distância | Frete | Tempo estimado |
|-----------|-------|----------------|
| até 2 km  | Grátis | ~15 min |
| até 5 km  | R$ 4,99 | ~25 min |
| até 10 km | R$ 8,99 | ~40 min |
| acima de 10 km | R$ 12,99 | ~60 min |

Farmácias fora de Juazeiro do Norte exibem **"Frete sob encomenda"**.

## Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3 + Flask |
| Banco de dados | PostgreSQL |
| ORM | SQLAlchemy |
| Autenticação | JWT (Flask-JWT-Extended) |
| Frontend | HTML5 + CSS3 + JavaScript puro |
| E-mail | SMTP (Gmail) |

## Estrutura do Projeto

```
idrugs/
├── app.py                  # Backend Flask — rotas e lógica principal
├── frete.py                # Módulo de cálculo de frete (Haversine + tabela)
├── cadastro.py             # Rotas de cadastro e autenticação
├── index.html              # Interface do cliente
├── colaborador.html        # Painel do farmacêutico
├── schema.sql              # Estrutura do banco de dados
├── migration_frete.sql     # Migração: colunas de endereço estruturado
├── static/
│   ├── js/
│   │   └── bairros.js      # Cascata Estado→Cidade→Bairro + frete no front
│   └── uploads/            # Fotos de produtos e farmácias (não versionado)
├── idrugs.env.example      # Template de variáveis de ambiente
└── requirements.txt        # Dependências Python
```

## Como Executar Localmente

### Pré-requisitos
- Python 3.10+
- PostgreSQL 14+
- pip

### Passo a passo

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/idrugs.git
cd idrugs

# 2. Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
copy idrugs.env.example idrugs.env
# Edite idrugs.env com suas credenciais

# 5. Crie o banco de dados
psql -U postgres -c "CREATE DATABASE idrugs;"
psql -d idrugs -f schema.sql
psql -d idrugs -f migration_frete.sql

# 6. Inicie o servidor
flask run
```

Acesse em: `http://localhost:5000`

## Variáveis de Ambiente

Crie um arquivo `idrugs.env` baseado no template:

```env
DATABASE_URL=postgresql://postgres:sua_senha@localhost:5432/idrugs
SECRET_KEY=sua-chave-secreta-aqui
EMAIL_USER=seu.email@gmail.com
EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_FROM_NAME=iDrugs Farmácias
FLASK_ENV=development
```

> **Nunca versione o arquivo `idrugs.env` com credenciais reais.**

## Regiões de Juazeiro do Norte Suportadas

| Região | Bairros |
|--------|---------|
| CENTRAL | Centro, Socorro, Salesianos, São Miguel, Franciscanos, Pirajá, Pio XII |
| NORTE | Horto, Salgadinho, Fátima, Santa Tereza, Juvêncio Santana |
| SUL | Aeroporto, Betolândia, Novo Juazeiro, Leandro Bezerra, Tiradentes, Limoeiro |
| OESTE | João Cabral, Frei Damião, Campo Alegre, Jardim Gonzaga, Cidade Universitária |
| LESTE | Lagoa Seca, Planalto, Triângulo, São José, Romeirão, Antônio Vieira |

## Autores

Desenvolvido como projeto acadêmico — [Instituição / Curso / Ano]

## Licença

Este projeto é de uso acadêmico. Para outros fins, entre em contato com os autores.
