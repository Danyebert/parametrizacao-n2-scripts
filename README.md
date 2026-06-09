# Parametrização N2 Scripts

Sistema Flask para consulta e manutenção de scripts SQL, correções N2, erros recorrentes, soluções aplicadas e documentação interna.

## Visual escolhido

O projeto foi construído no estilo **Dashboard Técnico Moderno**:

- Sidebar escura fixa.
- Topbar com busca geral.
- Cards de indicadores.
- Telas responsivas em Bootstrap 5.3.
- Alternância de tema: automático, claro e escuro.
- Botão **Acesso ADM** no canto superior direito.

## Tecnologias

- Python 3.11
- Flask 3+
- SQLite
- Bootstrap 5.3 via CDN
- CodeMirror via CDN
- Upload local de imagens JPG, JPEG e PNG

## Estrutura de pastas

```text
parametrizacao-n2-scripts/
├── app/
│   ├── static/
│   │   ├── css/app.css
│   │   ├── js/app.js
│   │   ├── js/theme.js
│   │   └── uploads/correcoes/
│   ├── templates/
│   │   ├── auth/
│   │   ├── correcoes/
│   │   ├── partials/
│   │   └── scripts/
│   ├── __init__.py
│   ├── auth.py
│   ├── db.py
│   ├── filters.py
│   ├── routes.py
│   └── schema.sql
├── docs/
├── instance/
├── .env.example
├── requirements.txt
└── run.py
```

## Como rodar no WSL

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

cd /home/danyebert/parametrizacao-n2-scripts
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
flask --app run.py run --host=0.0.0.0 --port=5000 --debug --no-reload
```

Acesse:

```text
http://127.0.0.1:5000
```

## Login administrativo inicial

O usuário inicial é criado automaticamente a partir do `.env`.

```env
ADMIN_USER=admin
ADMIN_PASSWORD=admin123
```

Troque esses valores antes de publicar em uma VPS.

## Regras de acesso

### Visitante

Pode acessar dashboard, busca, listagem, detalhes e copiar scripts SQL.

Não pode cadastrar, editar, excluir ou enviar imagens.

### Administrador

Pode cadastrar, editar e excluir logicamente scripts e correções N2. Também pode enviar e remover imagens das correções.

## Banco SQLite

As tabelas principais são:

- `usuarios`
- `tipos_banco`
- `scripts_sql`
- `correcoes_n2`
- `anexos`

Todos os registros usam `deleted_at` para exclusão lógica.

## Upload de imagens

As imagens das correções são salvas em:

```text
app/static/uploads/correcoes/<id-da-correcao>/arquivo.png
```

No banco fica salvo apenas o caminho relativo.

## Preparação para VPS

Para publicação futura, recomenda-se:

- Usar Gunicorn como servidor WSGI.
- Usar Nginx como proxy reverso.
- Definir `SECRET_KEY` forte no `.env`.
- Fazer backup periódico da pasta `instance/` e de `app/static/uploads/`.
- Configurar HTTPS com Certbot.

Exemplo futuro:

```bash
pip install gunicorn
gunicorn -w 3 -b 127.0.0.1:8000 run:app
```

## Padrão de branches

- `main`: versão estável.
- `develop`: integração de funcionalidades.
- `feature/nome-da-funcionalidade`: novas funcionalidades.
- `fix/nome-do-ajuste`: correções.
- `hotfix/nome-do-ajuste`: correções urgentes em produção.

## Padrão de commits

Use Conventional Commits:

```text
feat: adiciona cadastro de scripts SQL
fix: corrige filtro de tipo de banco
docs: atualiza instruções do README
refactor: reorganiza rotas de correções
```

## Módulos futuros previstos

A estrutura já permite adicionar:

- Documentações gerais.
- Gerador de link curto.
- Links úteis.
- Procedimentos operacionais.
- Base de erros conhecidos.
- Controle de versões.
- Histórico de alterações.
- Login por usuário.
- Permissões por perfil.
- Anexos PDF, TXT e DOCX.
