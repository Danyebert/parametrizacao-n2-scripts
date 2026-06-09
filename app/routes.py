import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from flask import send_file, abort

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
    where = ["deleted_at IS NULL"]
    if q:
        like = f"%{q}%"
        where.append("(titulo LIKE ? OR descricao LIKE ? OR codigo_sql LIKE ? OR observacoes LIKE ?)")
        params.extend([like, like, like, like])
    if tipo_banco:
        where.append("tipo_banco = ?")
        params.append(tipo_banco)
    rows = db.execute(
        f"SELECT * FROM scripts_sql WHERE {' AND '.join(where)} ORDER BY updated_at DESC",
        params,
    ).fetchall()
    return render_template("scripts/index.html", scripts=rows, tipos_banco=get_tipos_banco(), q=q, tipo_banco=tipo_banco)


@bp.route("/scripts/novo", methods=["GET", "POST"])
@login_required
def scripts_create():
    if request.method == "POST":
        return save_script()
    return render_template("scripts/form.html", script=None, tipos_banco=get_tipos_banco())


@bp.route("/scripts/<int:script_id>")
def scripts_detail(script_id):
    script = get_db().execute(
        "SELECT * FROM scripts_sql WHERE id = ? AND deleted_at IS NULL", (script_id,)
    ).fetchone()
    if script is None:
        flash("Script SQL não encontrado.", "warning")
        return redirect(url_for("main.scripts_index"))
    return render_template("scripts/detail.html", script=script)


@bp.route("/scripts/<int:script_id>/editar", methods=["GET", "POST"])
@login_required
def scripts_edit(script_id):
    script = get_db().execute(
        "SELECT * FROM scripts_sql WHERE id = ? AND deleted_at IS NULL", (script_id,)
    ).fetchone()
    if script is None:
        flash("Script SQL não encontrado.", "warning")
        return redirect(url_for("main.scripts_index"))
    if request.method == "POST":
        return save_script(script_id)
    return render_template("scripts/form.html", script=script, tipos_banco=get_tipos_banco())


@bp.route("/scripts/<int:script_id>/excluir", methods=["POST"])
@login_required
def scripts_delete(script_id):
    soft_delete("scripts_sql", script_id)
    flash("Script SQL excluído logicamente.", "success")
    return redirect(url_for("main.scripts_index"))


def save_script(script_id=None):
    db = get_db()
    titulo = request.form.get("titulo", "").strip()
    tipo_banco = request.form.get("tipo_banco_novo", "").strip() or request.form.get("tipo_banco", "").strip()
    descricao = request.form.get("descricao", "").strip()
    codigo_sql = request.form.get("codigo_sql", "").strip()
    observacoes = request.form.get("observacoes", "").strip()
    if not all([titulo, tipo_banco, descricao, codigo_sql]):
        flash("Preencha título, tipo de banco, descrição e código SQL.", "warning")
        return redirect(request.url)
    save_tipo_banco_if_new(tipo_banco)
    timestamp = now()
    if script_id:
        db.execute(
            """
            UPDATE scripts_sql SET titulo=?, tipo_banco=?, descricao=?, codigo_sql=?, observacoes=?, updated_at=?
            WHERE id=? AND deleted_at IS NULL
            """,
            (titulo, tipo_banco, descricao, codigo_sql, observacoes, timestamp, script_id),
        )
        flash("Script SQL atualizado com sucesso.", "success")
    else:
        db.execute(
            """
            INSERT INTO scripts_sql (titulo, tipo_banco, descricao, codigo_sql, observacoes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (titulo, tipo_banco, descricao, codigo_sql, observacoes, timestamp, timestamp),
        )
        flash("Script SQL cadastrado com sucesso.", "success")
    db.commit()
    return redirect(url_for("main.scripts_index"))


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


@bp.route("/datasync")
def datasync_index():
    projetos_path = Path(current_app.root_path) / "static" / "datasync" / "projetos"

    projetos_path.mkdir(parents=True, exist_ok=True)

    projetos = []

    for item in sorted(projetos_path.iterdir(), key=lambda p: p.name.lower()):
        projetos.append({
            "nome": item.name,
            "tipo": "Pasta" if item.is_dir() else "Arquivo",
            "caminho": f"datasync/projetos/{item.name}",
            "url": url_for("main.datasync_download", nome=item.name)
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

    # Se for arquivo, baixa o próprio arquivo direto.
    if item_path.is_file():
        return send_file(item_path, as_attachment=True, download_name=item_path.name)

    # Se for pasta, verifica se dentro tem apenas um arquivo compactado.
    if item_path.is_dir():
        arquivos = [p for p in item_path.iterdir() if p.is_file()]

        compactados = [
            p for p in arquivos
            if p.suffix.lower() in [".rar", ".zip", ".7z"]
        ]

        # Se a pasta tiver apenas um compactado, baixa ele direto.
        if len(arquivos) == 1 and len(compactados) == 1:
            arquivo = compactados[0]
            return send_file(
                arquivo,
                as_attachment=True,
                download_name=arquivo.name
            )

        # Se tiver vários arquivos, gera ZIP da pasta.
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