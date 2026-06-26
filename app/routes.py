import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from flask import send_file, abort
import json

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, send_from_directory,
    session, url_for
)
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from pathlib import Path

from .auth import login_required
from .db import get_db, now

bp = Blueprint("main", __name__)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
CRITICIDADES = ["Baixa", "Média", "Alta"]
CATEGORIAS_PADRAO = ["Banco", "API", "Tela", "Integração", "Usuário"]
SISTEMAS_PADRAO = ["ERP", "Portal", "API", "Integração"]


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def soft_delete(table, item_id):
    db = get_db()
    db.execute(f"UPDATE {table} SET deleted_at = ?, updated_at = ? WHERE id = ?", (now(), now(), item_id))
    db.commit()


def get_tipos_banco():
    return get_db().execute(
        "SELECT nome FROM tipos_banco WHERE deleted_at IS NULL ORDER BY nome"
    ).fetchall()


def save_tipo_banco_if_new(nome):
    nome = (nome or "").strip()
    if not nome:
        return
    db = get_db()
    timestamp = now()
    db.execute(
        "INSERT OR IGNORE INTO tipos_banco (nome, created_at, updated_at) VALUES (?, ?, ?)",
        (nome, timestamp, timestamp),
    )


@bp.app_context_processor
def inject_globals():
    return {"is_admin": bool(session.get("admin_id")), "current_year": datetime.now().year}


@bp.route("/")
def dashboard():
    db = get_db()
    scripts_count = db.execute("SELECT COUNT(*) total FROM scripts_sql WHERE deleted_at IS NULL").fetchone()["total"]
    correcoes_count = db.execute("SELECT COUNT(*) total FROM correcoes_n2 WHERE deleted_at IS NULL").fetchone()["total"]
    updates = []
    for row in db.execute(
        """
        SELECT id, titulo, tipo_banco AS meta, updated_at, 'script' AS tipo
        FROM scripts_sql WHERE deleted_at IS NULL
        UNION ALL
        SELECT id, titulo, categoria AS meta, updated_at, 'correcao' AS tipo
        FROM correcoes_n2 WHERE deleted_at IS NULL
        ORDER BY updated_at DESC LIMIT 5
        """
    ).fetchall():
        updates.append(row)
    return render_template("dashboard.html", scripts_count=scripts_count, correcoes_count=correcoes_count, updates=updates)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        senha = request.form.get("senha", "")
        user = get_db().execute(
            "SELECT * FROM usuarios WHERE nome = ? AND deleted_at IS NULL", (nome,)
        ).fetchone()
        if user and check_password_hash(user["senha_hash"], senha):
            session.clear()
            session["admin_id"] = user["id"]
            session["admin_nome"] = user["nome"]
            flash("Login administrativo realizado com sucesso.", "success")
            return redirect(url_for("main.dashboard"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da área administrativa.", "info")
    return redirect(url_for("main.dashboard"))


@bp.route("/scripts")
def scripts_index():
    db = get_db()
    q = request.args.get("q", "").strip()
    tipo_banco = request.args.get("tipo_banco", "").strip()

    params = []
    where = ["s.deleted_at IS NULL"]

    if q:
        like = f"%{q}%"
        where.append(
            """
            (
                s.titulo LIKE ?
                OR s.descricao LIKE ?
                OR s.codigo_sql LIKE ?
                OR s.observacoes LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM scripts_sql_consultas c2
                    WHERE c2.script_id = s.id
                      AND c2.deleted_at IS NULL
                      AND (
                          c2.titulo LIKE ?
                          OR c2.nome_tabela LIKE ?
                          OR c2.sql LIKE ?
                      )
                )
            )
            """
        )
        params.extend([like, like, like, like, like, like, like])

    if tipo_banco:
        where.append("s.tipo_banco = ?")
        params.append(tipo_banco)

    rows = db.execute(
        f"""
        SELECT
            s.*,
            COUNT(c.id) AS total_consultas
        FROM scripts_sql s
        LEFT JOIN scripts_sql_consultas c
          ON c.script_id = s.id
         AND c.deleted_at IS NULL
        WHERE {' AND '.join(where)}
        GROUP BY s.id
        ORDER BY s.updated_at DESC
        """,
        params,
    ).fetchall()

    return render_template(
        "scripts/index.html",
        scripts=rows,
        tipos_banco=get_tipos_banco(),
        q=q,
        tipo_banco=tipo_banco
    )


@bp.route("/scripts/novo", methods=["GET", "POST"])
@login_required
def scripts_create():
    if request.method == "POST":
        return save_script()

    return render_template(
        "scripts/form.html",
        script=None,
        consultas=[],
        tipos_banco=get_tipos_banco()
    )


@bp.route("/scripts/<int:script_id>")
def scripts_detail(script_id):
    db = get_db()

    script = db.execute(
        """
        SELECT *
        FROM scripts_sql
        WHERE id = ?
          AND deleted_at IS NULL
        """,
        (script_id,)
    ).fetchone()

    if script is None:
        flash("Script SQL não encontrado.", "warning")
        return redirect(url_for("main.scripts_index"))

    consultas = db.execute(
        """
        SELECT *
        FROM scripts_sql_consultas
        WHERE script_id = ?
          AND deleted_at IS NULL
        ORDER BY ordem ASC, id ASC
        """,
        (script_id,)
    ).fetchall()

    return render_template(
        "scripts/detail.html",
        script=script,
        consultas=consultas
    )


@bp.route("/scripts/<int:script_id>/editar", methods=["GET", "POST"])
@login_required
def scripts_edit(script_id):
    db = get_db()

    script = db.execute(
        """
        SELECT *
        FROM scripts_sql
        WHERE id = ?
          AND deleted_at IS NULL
        """,
        (script_id,)
    ).fetchone()

    if script is None:
        flash("Script SQL não encontrado.", "warning")
        return redirect(url_for("main.scripts_index"))

    if request.method == "POST":
        return save_script(script_id)

    consultas = db.execute(
        """
        SELECT *
        FROM scripts_sql_consultas
        WHERE script_id = ?
          AND deleted_at IS NULL
        ORDER BY ordem ASC, id ASC
        """,
        (script_id,)
    ).fetchall()

    return render_template(
        "scripts/form.html",
        script=script,
        consultas=consultas,
        tipos_banco=get_tipos_banco()
    )


@bp.route("/scripts/<int:script_id>/excluir", methods=["POST"])
@login_required
def scripts_delete(script_id):
    db = get_db()
    timestamp = now()

    db.execute(
        """
        UPDATE scripts_sql
        SET deleted_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (timestamp, timestamp, script_id)
    )

    db.execute(
        """
        UPDATE scripts_sql_consultas
        SET deleted_at = ?,
            updated_at = ?
        WHERE script_id = ?
        """,
        (timestamp, timestamp, script_id)
    )

    db.commit()

    flash("Script SQL excluído logicamente.", "success")
    return redirect(url_for("main.scripts_index"))


def save_script(script_id=None):
    db = get_db()

    titulo = request.form.get("titulo", "").strip()
    tipo_banco = request.form.get("tipo_banco_novo", "").strip() or request.form.get("tipo_banco", "").strip()
    descricao = request.form.get("descricao", "").strip()
    observacoes = request.form.get("observacoes", "").strip()

    tabelas = request.form.getlist("consulta_tabela[]")
    titulos = request.form.getlist("consulta_titulo[]")
    sqls = request.form.getlist("consulta_sql[]")

    consultas_validas = []

    for index, titulo_consulta in enumerate(titulos):
        titulo_consulta = titulo_consulta.strip()
        sql = sqls[index].strip() if index < len(sqls) else ""
        nome_tabela = tabelas[index].strip() if index < len(tabelas) else ""

        if titulo_consulta and sql:
            consultas_validas.append({
                "nome_tabela": nome_tabela,
                "titulo": titulo_consulta,
                "sql": sql,
                "ordem": index + 1
            })

    if not titulo or not tipo_banco or not descricao:
        flash("Preencha título, tipo de banco e descrição.", "warning")
        return redirect(request.url)

    if not consultas_validas:
        flash("Adicione pelo menos uma consulta SQL.", "warning")
        return redirect(request.url)

    save_tipo_banco_if_new(tipo_banco)

    timestamp = now()

    codigo_sql_principal = consultas_validas[0]["sql"]

    if script_id:
        db.execute(
            """
            UPDATE scripts_sql
            SET titulo = ?,
                tipo_banco = ?,
                descricao = ?,
                codigo_sql = ?,
                observacoes = ?,
                updated_at = ?
            WHERE id = ?
              AND deleted_at IS NULL
            """,
            (
                titulo,
                tipo_banco,
                descricao,
                codigo_sql_principal,
                observacoes,
                timestamp,
                script_id
            )
        )

        db.execute(
            """
            UPDATE scripts_sql_consultas
            SET deleted_at = ?,
                updated_at = ?
            WHERE script_id = ?
            """,
            (timestamp, timestamp, script_id)
        )

        target_id = script_id
        flash("Script SQL atualizado com sucesso.", "success")

    else:
        cur = db.execute(
            """
            INSERT INTO scripts_sql (
                titulo,
                tipo_banco,
                descricao,
                codigo_sql,
                observacoes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                titulo,
                tipo_banco,
                descricao,
                codigo_sql_principal,
                observacoes,
                timestamp,
                timestamp
            )
        )

        target_id = cur.lastrowid
        flash("Script SQL cadastrado com sucesso.", "success")

    for consulta in consultas_validas:
        db.execute(
            """
            INSERT INTO scripts_sql_consultas (
                script_id,
                nome_tabela,
                titulo,
                sql,
                ordem,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_id,
                consulta["nome_tabela"],
                consulta["titulo"],
                consulta["sql"],
                consulta["ordem"],
                timestamp,
                timestamp
            )
        )

    db.commit()

    return redirect(url_for("main.scripts_detail", script_id=target_id))

@bp.route("/correcoes")
def correcoes_index():
    db = get_db()
    q = request.args.get("q", "").strip()
    categoria = request.args.get("categoria", "").strip()
    criticidade = request.args.get("criticidade", "").strip()
    params = []
    where = ["deleted_at IS NULL"]
    if q:
        like = f"%{q}%"
        where.append("(titulo LIKE ? OR sistema LIKE ? OR erro LIKE ? OR causa LIKE ? OR correcao LIKE ? OR categoria LIKE ?)")
        params.extend([like, like, like, like, like, like])
    if categoria:
        where.append("categoria = ?")
        params.append(categoria)
    if criticidade:
        where.append("criticidade = ?")
        params.append(criticidade)
    rows = db.execute(
        f"SELECT * FROM correcoes_n2 WHERE {' AND '.join(where)} ORDER BY updated_at DESC",
        params,
    ).fetchall()
    return render_template("correcoes/index.html", correcoes=rows, q=q, categoria=categoria, criticidade=criticidade, categorias=CATEGORIAS_PADRAO, criticidades=CRITICIDADES)


@bp.route("/correcoes/nova", methods=["GET", "POST"])
@login_required
def correcoes_create():
    if request.method == "POST":
        return save_correcao()
    return render_template("correcoes/form.html", correcao=None, categorias=CATEGORIAS_PADRAO, sistemas=SISTEMAS_PADRAO, criticidades=CRITICIDADES)


@bp.route("/correcoes/<int:correcao_id>")
def correcoes_detail(correcao_id):
    db = get_db()
    correcao = db.execute(
        "SELECT * FROM correcoes_n2 WHERE id = ? AND deleted_at IS NULL", (correcao_id,)
    ).fetchone()
    if correcao is None:
        flash("Correção N2 não encontrada.", "warning")
        return redirect(url_for("main.correcoes_index"))
    anexos = db.execute(
        "SELECT * FROM anexos WHERE tipo_origem='correcao_n2' AND origem_id=? AND deleted_at IS NULL ORDER BY created_at DESC",
        (correcao_id,),
    ).fetchall()
    return render_template("correcoes/detail.html", correcao=correcao, anexos=anexos)


@bp.route("/correcoes/<int:correcao_id>/editar", methods=["GET", "POST"])
@login_required
def correcoes_edit(correcao_id):
    db = get_db()
    correcao = db.execute(
        "SELECT * FROM correcoes_n2 WHERE id = ? AND deleted_at IS NULL", (correcao_id,)
    ).fetchone()
    if correcao is None:
        flash("Correção N2 não encontrada.", "warning")
        return redirect(url_for("main.correcoes_index"))
    if request.method == "POST":
        return save_correcao(correcao_id)
    anexos = db.execute(
        "SELECT * FROM anexos WHERE tipo_origem='correcao_n2' AND origem_id=? AND deleted_at IS NULL ORDER BY created_at DESC",
        (correcao_id,),
    ).fetchall()
    return render_template("correcoes/form.html", correcao=correcao, anexos=anexos, categorias=CATEGORIAS_PADRAO, sistemas=SISTEMAS_PADRAO, criticidades=CRITICIDADES)


@bp.route("/correcoes/<int:correcao_id>/excluir", methods=["POST"])
@login_required
def correcoes_delete(correcao_id):
    soft_delete("correcoes_n2", correcao_id)
    flash("Correção N2 excluída logicamente.", "success")
    return redirect(url_for("main.correcoes_index"))


def save_correcao(correcao_id=None):
    db = get_db()
    titulo = request.form.get("titulo", "").strip()
    sistema = request.form.get("sistema_novo", "").strip() or request.form.get("sistema", "").strip()
    erro = request.form.get("erro", "").strip()
    causa = request.form.get("causa", "").strip()
    correcao = request.form.get("correcao", "").strip()
    categoria = request.form.get("categoria_nova", "").strip() or request.form.get("categoria", "").strip()
    criticidade = request.form.get("criticidade", "").strip()
    if not all([titulo, sistema, erro, causa, correcao, categoria, criticidade]):
        flash("Preencha todos os campos obrigatórios da correção N2.", "warning")
        return redirect(request.url)
    timestamp = now()
    if correcao_id:
        db.execute(
            """
            UPDATE correcoes_n2 SET titulo=?, sistema=?, erro=?, causa=?, correcao=?, categoria=?, criticidade=?, updated_at=?
            WHERE id=? AND deleted_at IS NULL
            """,
            (titulo, sistema, erro, causa, correcao, categoria, criticidade, timestamp, correcao_id),
        )
        target_id = correcao_id
        flash("Correção N2 atualizada com sucesso.", "success")
    else:
        cur = db.execute(
            """
            INSERT INTO correcoes_n2 (titulo, sistema, erro, causa, correcao, categoria, criticidade, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (titulo, sistema, erro, causa, correcao, categoria, criticidade, timestamp, timestamp),
        )
        target_id = cur.lastrowid
        flash("Correção N2 cadastrada com sucesso.", "success")
    db.commit()
    handle_uploads(target_id)
    return redirect(url_for("main.correcoes_detail", correcao_id=target_id))


def handle_uploads(correcao_id):
    files = request.files.getlist("imagens")
    valid_files = [f for f in files if f and f.filename]
    if not valid_files:
        return
    db = get_db()
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "correcoes" / str(correcao_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now()
    for file in valid_files:
        if not allowed_file(file.filename):
            flash(f"Arquivo ignorado: {file.filename}. Use JPG, JPEG ou PNG.", "warning")
            continue
        original = secure_filename(file.filename)
        ext = original.rsplit(".", 1)[1].lower()
        filename = f"{uuid4().hex}.{ext}"
        full_path = upload_dir / filename
        file.save(full_path)
        caminho = f"uploads/correcoes/{correcao_id}/{filename}"
        db.execute(
            """
            INSERT INTO anexos (tipo_origem, origem_id, nome_arquivo, caminho_arquivo, created_at, updated_at)
            VALUES ('correcao_n2', ?, ?, ?, ?, ?)
            """,
            (correcao_id, original, caminho, timestamp, timestamp),
        )
    db.commit()

@bp.route("/correcoes/exportar-json")
@login_required
def correcoes_exportar_json():
    db = get_db()

    correcoes = db.execute(
        """
        SELECT titulo, sistema, erro, causa, correcao, categoria, criticidade, created_at, updated_at
        FROM correcoes_n2
        WHERE deleted_at IS NULL
        ORDER BY updated_at DESC
        """
    ).fetchall()

    dados = [dict(row) for row in correcoes]

    temp_path = Path(tempfile.gettempdir()) / "correcoes_n2_export.json"

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    return send_file(
        temp_path,
        as_attachment=True,
        download_name="correcoes_n2_export.json",
        mimetype="application/json"
    )


@bp.route("/correcoes/importar-json", methods=["POST"])
@login_required
def correcoes_importar_json():
    arquivo = request.files.get("arquivo_json")

    if not arquivo or not arquivo.filename:
        flash("Selecione um arquivo JSON.", "warning")
        return redirect(url_for("main.correcoes_index"))

    if not arquivo.filename.lower().endswith(".json"):
        flash("Arquivo inválido. Envie um arquivo .json.", "danger")
        return redirect(url_for("main.correcoes_index"))

    try:
        dados = json.load(arquivo)
    except Exception:
        flash("Não foi possível ler o arquivo JSON.", "danger")
        return redirect(url_for("main.correcoes_index"))

    if not isinstance(dados, list):
        flash("JSON inválido. O arquivo precisa conter uma lista de correções.", "danger")
        return redirect(url_for("main.correcoes_index"))

    db = get_db()
    timestamp = now()
    total = 0

    for item in dados:
        titulo = str(item.get("titulo", "")).strip()
        sistema = str(item.get("sistema", "")).strip()
        erro = str(item.get("erro", "")).strip()
        causa = str(item.get("causa", "")).strip()
        correcao = str(item.get("correcao", "")).strip()
        categoria = str(item.get("categoria", "")).strip()
        criticidade = str(item.get("criticidade", "")).strip()

        if not all([titulo, sistema, erro, causa, correcao, categoria, criticidade]):
            continue

        db.execute(
            """
            INSERT INTO correcoes_n2 (
                titulo, sistema, erro, causa, correcao,
                categoria, criticidade, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                titulo, sistema, erro, causa, correcao,
                categoria, criticidade, timestamp, timestamp
            )
        )

        total += 1

    db.commit()

    flash(f"{total} correção(ões) importada(s) com sucesso.", "success")
    return redirect(url_for("main.correcoes_index"))


@bp.route("/anexos/<int:anexo_id>/excluir", methods=["POST"])
@login_required
def anexo_delete(anexo_id):
    db = get_db()
    anexo = db.execute("SELECT * FROM anexos WHERE id=? AND deleted_at IS NULL", (anexo_id,)).fetchone()
    if anexo is None:
        flash("Anexo não encontrado.", "warning")
        return redirect(url_for("main.dashboard"))
    db.execute("UPDATE anexos SET deleted_at=?, updated_at=? WHERE id=?", (now(), now(), anexo_id))
    db.commit()
    flash("Anexo removido logicamente.", "success")
    return redirect(url_for("main.correcoes_edit", correcao_id=anexo["origem_id"]))


@bp.route("/busca")
def busca():
    db = get_db()
    q = request.args.get("q", "").strip()
    modulo = request.args.get("modulo", "todos").strip()
    resultados_scripts = []
    resultados_correcoes = []
    if q:
        like = f"%{q}%"
        if modulo in ["todos", "scripts"]:
            resultados_scripts = db.execute(
                """
                SELECT * FROM scripts_sql
                WHERE deleted_at IS NULL AND (titulo LIKE ? OR tipo_banco LIKE ? OR descricao LIKE ? OR codigo_sql LIKE ? OR observacoes LIKE ?)
                ORDER BY updated_at DESC
                """,
                (like, like, like, like, like),
            ).fetchall()
        if modulo in ["todos", "correcoes"]:
            resultados_correcoes = db.execute(
                """
                SELECT * FROM correcoes_n2
                WHERE deleted_at IS NULL AND (titulo LIKE ? OR sistema LIKE ? OR erro LIKE ? OR causa LIKE ? OR correcao LIKE ? OR categoria LIKE ?)
                ORDER BY updated_at DESC
                """,
                (like, like, like, like, like, like),
            ).fetchall()
    return render_template("busca.html", q=q, modulo=modulo, scripts=resultados_scripts, correcoes=resultados_correcoes)


@bp.errorhandler(413)
def too_large(error):
    flash("Arquivo muito grande. Ajuste MAX_CONTENT_LENGTH_MB no .env se necessário.", "danger")
    return redirect(request.referrer or url_for("main.dashboard"))


def registrar_download_datasync(nome_arquivo, caminho_arquivo):
    db = get_db()

    existente = db.execute(
        """
        SELECT id
        FROM downloads_datasync
        WHERE nome_arquivo = ?
        """,
        (nome_arquivo,)
    ).fetchone()

    if existente:
        db.execute(
            """
            UPDATE downloads_datasync
            SET total_downloads = total_downloads + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE nome_arquivo = ?
            """,
            (nome_arquivo,)
        )
    else:
        db.execute(
            """
            INSERT INTO downloads_datasync (
                nome_arquivo,
                caminho_arquivo,
                total_downloads
            )
            VALUES (?, ?, 1)
            """,
            (nome_arquivo, caminho_arquivo)
        )

    db.commit()

@bp.route("/datasync")
def datasync_index():
    projetos_path = Path(current_app.root_path) / "static" / "datasync" / "projetos"
    projetos_path.mkdir(parents=True, exist_ok=True)

    db = get_db()
    projetos = []

    for item in sorted(projetos_path.iterdir(), key=lambda p: p.name.lower()):
        nome_download = item.name

        if item.is_dir():
            arquivos = [p for p in item.iterdir() if p.is_file()]
            compactados = [
                p for p in arquivos
                if p.suffix.lower() in [".rar", ".zip", ".7z"]
            ]

            if len(arquivos) == 1 and len(compactados) == 1:
                nome_download = compactados[0].name
            else:
                nome_download = f"{item.name}.zip"

        contador = db.execute(
            """
            SELECT total_downloads
            FROM downloads_datasync
            WHERE nome_arquivo = ?
            """,
            (nome_download,)
        ).fetchone()

        projetos.append({
            "nome": item.name,
            "nome_download": nome_download,
            "tipo": "Pasta" if item.is_dir() else "Arquivo",
            "caminho": f"datasync/projetos/{item.name}",
            "url": url_for("main.datasync_download", nome=item.name),
            "downloads": contador["total_downloads"] if contador else 0
        })

    return render_template("datasync/index.html", projetos=projetos)



@bp.route("/datasync/download/<path:nome>")
def datasync_download(nome):
    projetos_path = Path(current_app.root_path) / "static" / "datasync" / "projetos"
    item_path = projetos_path / nome

    try:
        item_path = item_path.resolve()
        projetos_path = projetos_path.resolve()
    except FileNotFoundError:
        abort(404)

    if not str(item_path).startswith(str(projetos_path)):
        abort(403)

    if not item_path.exists():
        abort(404)

    if item_path.is_file():
        registrar_download_datasync(
            nome_arquivo=item_path.name,
            caminho_arquivo=str(item_path.relative_to(projetos_path))
        )

        return send_file(
            item_path,
            as_attachment=True,
            download_name=item_path.name
        )

    if item_path.is_dir():
        arquivos = [p for p in item_path.iterdir() if p.is_file()]
        compactados = [
            p for p in arquivos
            if p.suffix.lower() in [".rar", ".zip", ".7z"]
        ]

        if len(arquivos) == 1 and len(compactados) == 1:
            arquivo = compactados[0]

            registrar_download_datasync(
                nome_arquivo=arquivo.name,
                caminho_arquivo=str(arquivo.relative_to(projetos_path))
            )

            return send_file(
                arquivo,
                as_attachment=True,
                download_name=arquivo.name
            )

        registrar_download_datasync(
            nome_arquivo=f"{item_path.name}.zip",
            caminho_arquivo=str(item_path.relative_to(projetos_path))
        )

        temp_dir = Path(tempfile.gettempdir())
        zip_base = temp_dir / item_path.name

        zip_path = shutil.make_archive(
            base_name=str(zip_base),
            format="zip",
            root_dir=item_path
        )

        return send_file(
            zip_path,
            as_attachment=True,
            download_name=f"{item_path.name}.zip"
        )

    abort(404)


@bp.route("/bancos-mapeados")
def bancos_mapeados_index():
    db = get_db()

    bancos = db.execute(
        """
        SELECT bm.*,
               COUNT(cs.id) AS total_consultas
        FROM banco_mapeado bm
        LEFT JOIN consulta_sql cs
          ON cs.banco_id = bm.id
         AND cs.deleted_at IS NULL
        WHERE bm.deleted_at IS NULL
        GROUP BY bm.id
        ORDER BY bm.updated_at DESC
        """
    ).fetchall()

    return render_template("bancos_mapeados/index.html", bancos=bancos)


@bp.route("/bancos-mapeados/novo", methods=["GET", "POST"])
@login_required
def bancos_mapeados_create():
    if request.method == "POST":
        return salvar_banco_mapeado()

    return render_template("bancos_mapeados/form.html", banco=None, consultas=[])

@bp.route("/bancos-mapeados/<int:banco_id>")
def bancos_mapeados_detail(banco_id):
    db = get_db()

    banco = db.execute(
            """
            SELECT *
            FROM banco_mapeado
            WHERE id = ?
            AND deleted_at IS NULL
            """,
            (banco_id,)
        ).fetchone()

    if banco is None:
            flash("Banco mapeado não encontrado.", "warning")
            return redirect(url_for("main.bancos_mapeados_index"))

    consultas = db.execute(
            """
            SELECT *
            FROM consulta_sql
            WHERE banco_id = ?
            AND deleted_at IS NULL
            ORDER BY ordem ASC, id ASC
            """,
            (banco_id,)
        ).fetchall()

    return render_template(
            "bancos_mapeados/detail.html",
            banco=banco,
            consultas=consultas
        )


@bp.route("/bancos-mapeados/<int:banco_id>/editar", methods=["GET", "POST"])
@login_required
def bancos_mapeados_edit(banco_id):
        db = get_db()

        banco = db.execute(
            """
            SELECT *
            FROM banco_mapeado
            WHERE id = ?
            AND deleted_at IS NULL
            """,
            (banco_id,)
        ).fetchone()

        if banco is None:
            flash("Banco mapeado não encontrado.", "warning")
            return redirect(url_for("main.bancos_mapeados_index"))

        if request.method == "POST":
            return salvar_banco_mapeado(banco_id)

        consultas = db.execute(
            """
            SELECT *
            FROM consulta_sql
            WHERE banco_id = ?
            AND deleted_at IS NULL
            ORDER BY ordem ASC, id ASC
            """,
            (banco_id,)
        ).fetchall()

        return render_template(
            "bancos_mapeados/form.html",
            banco=banco,
            consultas=consultas
        )


@bp.route("/bancos-mapeados/<int:banco_id>/deletar", methods=["POST"])
@login_required
def bancos_mapeados_delete(banco_id):
        db = get_db()

        db.execute(
            """
            UPDATE banco_mapeado
            SET deleted_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now(), now(), banco_id)
        )

        db.execute(
            """
            UPDATE consulta_sql
            SET deleted_at = ?,
                updated_at = ?
            WHERE banco_id = ?
            """,
            (now(), now(), banco_id)
        )

        db.commit()

        flash("Banco mapeado excluído com sucesso.", "success")
        return redirect(url_for("main.bancos_mapeados_index"))


def salvar_banco_mapeado(banco_id=None):
    db = get_db()

    nome_sistema = request.form.get("nome_sistema", "").strip()
    nome_banco = request.form.get("nome_banco", "").strip()
    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "").strip()

    tabelas = request.form.getlist("consulta_tabela[]")
    titulos = request.form.getlist("consulta_titulo[]")
    sqls = request.form.getlist("consulta_sql[]")

    if not nome_sistema or not nome_banco or not usuario or not senha:
        flash("Preencha todos os campos do banco.", "warning")
        return redirect(request.url)

    consultas_validas = []

    for index, titulo in enumerate(titulos):
        titulo = titulo.strip()
        sql = sqls[index].strip() if index < len(sqls) else ""
        nome_tabela = tabelas[index].strip() if index < len(tabelas) else ""

        if titulo and sql:
            consultas_validas.append({
                "nome_tabela": nome_tabela,
                "titulo": titulo,
                "sql": sql,
                "ordem": index + 1
            })

    if not consultas_validas:
        flash("Adicione pelo menos uma consulta SQL.", "warning")
        return redirect(request.url)

    timestamp = now()

    if banco_id:
        db.execute(
            """
            UPDATE banco_mapeado
            SET nome_sistema = ?,
                nome_banco = ?,
                usuario = ?,
                senha = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (nome_sistema, nome_banco, usuario, senha, timestamp, banco_id)
        )

        db.execute(
            """
            UPDATE consulta_sql
            SET deleted_at = ?,
                updated_at = ?
            WHERE banco_id = ?
            """,
            (timestamp, timestamp, banco_id)
        )

        target_id = banco_id
        flash("Banco mapeado atualizado com sucesso.", "success")

    else:
        cur = db.execute(
            """
            INSERT INTO banco_mapeado (
                nome_sistema,
                nome_banco,
                usuario,
                senha,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome_sistema, nome_banco, usuario, senha, timestamp, timestamp)
        )

        target_id = cur.lastrowid
        flash("Banco mapeado cadastrado com sucesso.", "success")

    for consulta in consultas_validas:
        db.execute(
            """
            INSERT INTO consulta_sql (
                banco_id,
                nome_tabela,
                titulo,
                sql,
                ordem,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_id,
                consulta["nome_tabela"],
                consulta["titulo"],
                consulta["sql"],
                consulta["ordem"],
                timestamp,
                timestamp
            )
        )

    db.commit()
    return redirect(url_for("main.bancos_mapeados_detail", banco_id=target_id))

@bp.route("/gerador-link")
def gerador_link():
    return render_template("gerador_link/index.html")


@bp.route("/ferramentas-conversao")
def ferramentas_conversao_index():
    ferramentas_path = Path(current_app.root_path) / "static" / "ferramentas_conversao"
    ferramentas_path.mkdir(parents=True, exist_ok=True)

    ferramentas = []

    for item in sorted(ferramentas_path.iterdir(), key=lambda p: p.name.lower()):
        ferramentas.append({
            "nome": item.name,
            "tipo": "Pasta" if item.is_dir() else "Arquivo",
            "caminho": f"ferramentas_conversao/{item.name}",
            "url": url_for("main.ferramentas_conversao_download", nome=item.name)
        })

    return render_template(
        "ferramentas_conversao/index.html",
        ferramentas=ferramentas
    )


@bp.route("/ferramentas-conversao/download/<path:nome>")
def ferramentas_conversao_download(nome):
    ferramentas_path = Path(current_app.root_path) / "static" / "ferramentas_conversao"
    item_path = ferramentas_path / nome

    try:
        item_path = item_path.resolve()
        ferramentas_path = ferramentas_path.resolve()
    except FileNotFoundError:
        abort(404)

    if not str(item_path).startswith(str(ferramentas_path)):
        abort(403)

    if not item_path.exists():
        abort(404)

    if item_path.is_file():
        return send_file(
            item_path,
            as_attachment=True,
            download_name=item_path.name
        )

    if item_path.is_dir():
        arquivos = [p for p in item_path.iterdir() if p.is_file()]
        compactados = [
            p for p in arquivos
            if p.suffix.lower() in [".rar", ".zip", ".7z"]
        ]

        if len(arquivos) == 1 and len(compactados) == 1:
            arquivo = compactados[0]

            return send_file(
                arquivo,
                as_attachment=True,
                download_name=arquivo.name
            )

        temp_dir = Path(tempfile.gettempdir())
        zip_base = temp_dir / item_path.name

        zip_path = shutil.make_archive(
            base_name=str(zip_base),
            format="zip",
            root_dir=item_path
        )

        return send_file(
            zip_path,
            as_attachment=True,
            download_name=f"{item_path.name}.zip"
        )

    abort(404)