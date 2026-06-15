# Autenticação com JWT

Este documento descreve como usar o sistema de autenticação JWT implementado na aplicação.

## Endpoints Implementados

### 1. Registrar Novo Usuário
**POST** `/users/register`

```bash
curl -X POST "http://localhost:8000/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "João Silva",
    "email": "joao@example.com",
    "password": "senha123456",
    "birthdate": "1990-01-15",
    "cpf": "12345678901",
    "phone_number": "11987654321"
  }'
```

**Response:**
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "João Silva",
  "email": "joao@example.com",
  "birthdate": "1990-01-15",
  "cpf": "12345678901",
  "phone_number": "11987654321",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

### 2. Login (Obter Token JWT)
**POST** `/users/login`

```bash
curl -X POST "http://localhost:8000/users/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@example.com",
    "password": "senha123456"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "João Silva",
    "email": "joao@example.com",
    "birthdate": "1990-01-15",
    "cpf": "12345678901",
    "phone_number": "11987654321",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
}
```

## Usando o Token em Requisições Autenticadas

Adicione o token ao header `Authorization` com o prefixo `Bearer`:

```bash
curl -X GET "http://localhost:8000/api/protected-endpoint" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Exemplo de Endpoint Protegido

Para criar um endpoint que requer autenticação, use a dependência `get_current_user`:

```python
from fastapi import APIRouter, Depends
from src.core.auth import get_current_user
from src.modules.users.model import User

router = APIRouter()

@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Retorna informações do usuário autenticado"""
    return {
        "uuid": str(current_user.uuid),
        "email": current_user.email,
        "full_name": current_user.full_name,
    }
```

## Configurações de JWT

As seguintes configurações podem ser ajustadas em `src/core/config.py`:

- `SECRET_KEY`: Chave secreta para assinar os tokens (defina em `.env`)
- `ALGORITHM`: Algoritmo de criptografia (padrão: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Tempo de expiração do token em minutos (padrão: 30)

## Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fastapi_db
SECRET_KEY=sua-chave-secreta-muito-segura-aqui
```

## Funções Utilitárias Disponíveis

### `hash_password(password: str) -> str`
Cria um hash seguro da senha usando bcrypt.

### `verify_password(plain_password: str, hashed_password: str) -> bool`
Verifica se uma senha corresponde a um hash.

### `create_access_token(data: dict, expires_delta: timedelta | None = None) -> str`
Cria um token JWT com os dados fornecidos.

### `decode_access_token(token: str) -> dict | None`
Decodifica e valida um token JWT.

### `get_current_user(credentials, db) -> User`
Dependência do FastAPI que extrai o usuário autenticado do token.

## Tratamento de Erros

- **401 Unauthorized**: Email/senha inválidos ou token expirado
- **403 Forbidden**: Usuário inativo
- **409 Conflict**: Email, CPF ou telefone já registrado

