# Arquitetura do Projeto

## Camadas

- `run.py`: ponto de entrada local.
- `app/__init__.py`: criação da aplicação Flask.
- `app/routes.py`: rotas HTTP e regras de fluxo.
- `app/db.py`: conexão, criação do banco e usuário inicial.
- `app/auth.py`: controle de sessão e proteção administrativa.
- `app/templates`: interface Bootstrap.
- `app/static`: CSS, JS e uploads.

## Decisões técnicas

- SQLite para facilitar uso em localhost e WSL.
- Flask app factory para facilitar evolução.
- Templates separados por módulo.
- Exclusão lógica com `deleted_at`.
- Uploads separados por correção.
- Lista `tipos_banco` para permitir expansão de bancos no futuro.

## Segurança básica

- Senha com hash via Werkzeug.
- Rotas administrativas protegidas por sessão.
- Upload limitado por extensão.
- `secure_filename` para nomes de arquivos.
- Configurações via `.env`.
