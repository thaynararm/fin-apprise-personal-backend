# Finance API

API de gerenciamento de usuarios com FastAPI, PostgreSQL, Alembic e autenticacao JWT.

## Tecnologias

- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL 15
- Alembic
- JWT (python-jose)
- bcrypt

## Estrutura principal

- src/main.py: cria e configura a aplicacao FastAPI
- src/core/config.py: configuracoes e leitura de variaveis de ambiente
- src/core/database.py: engine e sessao do banco
- src/modules/users/router.py: endpoints de usuarios e autenticacao
- alembic/: migrations do banco
- docker-compose.yml: servico local do PostgreSQL

## Pre-requisitos

- Python 3.11 ou superior instalado
- Docker e Docker Compose (opcional, mas recomendado para banco)

## 1) Configurar ambiente Python

No Windows (PowerShell):

    python -m venv venv
    .\venv\Scripts\Activate.ps1

No Linux/macOS:

    python -m venv venv
    source venv/bin/activate

Instale as dependencias (o projeto ainda nao possui requirements.txt):

    pip install -r requirements.txt

## 2) Configurar variaveis de ambiente

Crie um arquivo .env na raiz do projeto com:

    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fastapi_db
    SECRET_KEY=troque-esta-chave-em-producao

Observacoes importantes:

- DATABASE_URL precisa apontar para o banco em execucao.
- SECRET_KEY deve ser forte e unica em producao.

## 3) Subir PostgreSQL com Docker

    docker compose up -d

Isso sobe o banco em localhost:5432 com:

- usuario: postgres
- senha: postgres
- database: fastapi_db

Para parar:

    docker compose down

## 4) Rodar migrations com Alembic

Aplicar migrations existentes:

    alembic upgrade head

Criar nova migration:

    alembic revision --autogenerate -m "descricao da alteracao"

## 5) Iniciar a aplicacao

    uvicorn src.main:app --reload

API disponivel em:

- http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Endpoints principais

Base path: /users

- POST /users/register
- POST /users/login
- POST /users/logout (autenticado)
- GET /users/{user_uuid} (autenticado)
- GET /users (autenticado)
- PATCH /users/{user_uuid} (autenticado e somente o proprio usuario)

## Fluxo de autenticacao JWT

1. Registrar usuario em POST /users/register
2. Fazer login em POST /users/login para receber access_token
3. Enviar token no header Authorization:

    Authorization: Bearer SEU_TOKEN

4. Consumir endpoints protegidos

Existe um guia com exemplos de requisicao em JWT_AUTHENTICATION.md.

## Erros comuns

- Erro de conexao com banco:
  - confira se o container do PostgreSQL esta ativo
  - valide DATABASE_URL no .env

- Erro 401 (Unauthorized):
  - token invalido/expirado
  - credenciais incorretas no login

- Erro 403 (Forbidden):
  - usuario inativo
  - tentativa de editar outro usuario

- Erro ao gerar migration:
  - confirme que as models estao importadas no alembic/env.py

## Comandos rapidos

Subir banco:

    docker compose up -d

Aplicar migration:

    alembic upgrade head

Rodar API:

    uvicorn src.main:app --reload