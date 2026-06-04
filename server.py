"""
PECLD – servidor local de dados
Lê todos os arquivos PECLD*.xlsx da pasta de trabalho compartilhada e
expõe os dados como JSON para o painel HTML.
"""
from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import os
import json
import logging
import subprocess

FOLDER   = r"G:\Drives compartilhados\PCP\Time STC\PECLDTESTE"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
METAS_FILE  = os.path.join(BASE_DIR, "metas.json")
SUPERS_FILE = os.path.join(BASE_DIR, "superintendencias.json")

ESCOLHER_DATAS_DIR    = BASE_DIR
ESCOLHER_DATAS_SCRIPT = os.path.join(BASE_DIR, "escolher_datas.py")

app = Flask(__name__, static_folder=BASE_DIR)
log = logging.getLogger("werkzeug")
log.setLevel(logging.WARNING)

# ── colunas que interessam ─────────────────────────────────────────────────
COLS = [
    "num_servico", "Nota", "contrato", "Utd", "Coordenador", "Supervisor",
    "grupo_servico", "Motivo_Servico", "prioridade", "situacao_servico",
    "Retorno_de_Campo", "Grupo_Retorno_de_Campo",
    "dta_exec_srv", "Regional", "Bairro", "VALOR",
    "qtd_horas_trabalhadas",
]

_df: pd.DataFrame | None = None
_files_info: list = []

# ── carregamento ───────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    global _df, _files_info
    dfs, _files_info = [], []

    if not os.path.isdir(FOLDER):
        print(f"[AVISO] Pasta não encontrada: {FOLDER}")
        _df = pd.DataFrame()
        return _df

    for fname in sorted(os.listdir(FOLDER)):
        if not fname.lower().endswith(".xlsx"):
            continue
        path = os.path.join(FOLDER, fname)
        try:
            tmp = pd.read_excel(
                path, engine="openpyxl",
                usecols=lambda c: c in COLS,
            )
            dfs.append(tmp)
            _files_info.append({"name": fname, "rows": len(tmp)})
            print(f"  OK  {fname:50s} {len(tmp):>5} linhas")
        except Exception as exc:
            print(f"  ERR {fname}: {exc}")

    if not dfs:
        _df = pd.DataFrame()
        return _df

    df = pd.concat(dfs, ignore_index=True)
    df = df.drop_duplicates(subset=["num_servico"])

    # ── limpeza de strings ─────────────────────────────────────────────────
    for col in ["Utd", "Coordenador", "grupo_servico", "prioridade",
                "Regional", "Bairro", "situacao_servico", "Motivo_Servico"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # ── superintendencia: auto-derivada do contrato + overrides do JSON ───────
    if "contrato" in df.columns:
        import re
        def _super(v):
            m = re.search(r"STC_(.+?)_\d{4}", str(v))
            return m.group(1).replace(".", "-") if m else ""
        df["Superintendencia"] = df["contrato"].apply(_super)
    else:
        df["Superintendencia"] = ""

    # aplica overrides manuais (superintendencias.json sobrescreve o auto)
    if os.path.exists(SUPERS_FILE):
        with open(SUPERS_FILE, encoding="utf-8") as f:
            overrides = json.load(f)
        df["Superintendencia"] = df.apply(
            lambda r: overrides.get(r["Utd"], r["Superintendencia"]), axis=1
        )

    # ── datas ──────────────────────────────────────────────────────────────
    df["dta_exec_srv"] = pd.to_datetime(df["dta_exec_srv"], errors="coerce")
    df["data_str"]     = df["dta_exec_srv"].dt.strftime("%Y-%m-%d").fillna("")
    df["mes"]          = df["dta_exec_srv"].dt.month.fillna(0).astype(int)
    df["ano"]          = df["dta_exec_srv"].dt.year.fillna(0).astype(int)
    df["dia_semana"]   = df["dta_exec_srv"].dt.dayofweek.fillna(-1).astype(int)

    # ── retorno de campo (booliano) ────────────────────────────────────────
    df["tem_retorno"] = (
        df["Retorno_de_Campo"].notna()
        & (df["Retorno_de_Campo"].astype(str).str.strip() != "")
        & (df["Retorno_de_Campo"].astype(str) != "nan")
    )

    # ── valor numérico ─────────────────────────────────────────────────────
    if "VALOR" in df.columns:
        df["VALOR"] = pd.to_numeric(df["VALOR"], errors="coerce").fillna(0)

    _df = df
    print(f"\n  Total: {len(df):,} Notas em {len(dfs)} arquivo(s)\n")
    return _df

def get_df() -> pd.DataFrame:
    if _df is None:
        load_data()
    return _df  # type: ignore

# ── filtros ────────────────────────────────────────────────────────────────
def apply_filters(df: pd.DataFrame, args) -> pd.DataFrame:
    if args.get("ano") and str(args["ano"]).isdigit():
        df = df[df["ano"] == int(args["ano"])]
    if args.get("mes") and str(args["mes"]).isdigit():
        df = df[df["mes"] == int(args["mes"])]
    if args.get("dia") and str(args["dia"]).isdigit():
        df = df[df["data_str"].str.endswith(f"-{str(args['dia']).zfill(2)}")]
    if args.get("super"):
        df = df[df["Superintendencia"] == args["super"]]
    if args.get("utd"):
        df = df[df["Utd"] == args["utd"]]
    if args.get("grupo"):
        df = df[df["grupo_servico"].str.contains(args["grupo"], na=False)]
    return df

# ── helpers JSON ───────────────────────────────────────────────────────────
def safe_records(df: pd.DataFrame) -> list:
    """Converte DataFrame em lista de dicts sem NaN."""
    return df.where(pd.notnull(df), None).to_dict("records")

# ── rotas ──────────────────────────────────────────────────────────────────
app.config["JSON_AS_ASCII"] = False   # mantém acentos no JSON

@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    if resp.content_type.startswith("application/json"):
        resp.content_type = "application/json; charset=utf-8"
    return resp

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/api/files")
def api_files():
    return jsonify(_files_info)

@app.route("/api/reload", methods=["POST"])
def api_reload():
    global _df
    _df = None
    load_data()
    return jsonify({"status": "ok", "total": len(get_df())})

@app.route("/api/os")
def api_os():
    df = apply_filters(get_df(), request.args)
    out = [
        "num_servico", "Nota", "Superintendencia", "Utd", "Coordenador",
        "grupo_servico", "prioridade", "situacao_servico", "Retorno_de_Campo",
        "Grupo_Retorno_de_Campo", "Motivo_Servico",
        "data_str", "mes", "ano", "dia_semana",
        "Regional", "Bairro", "VALOR", "tem_retorno",
    ]
    cols = [c for c in out if c in df.columns]
    return jsonify({"total": len(df), "records": safe_records(df[cols])})

@app.route("/api/metas", methods=["GET", "POST"])
def api_metas():
    if request.method == "POST":
        data = request.get_json(force=True)
        with open(METAS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "saved"})
    if os.path.exists(METAS_FILE):
        with open(METAS_FILE, encoding="utf-8") as f:
            return jsonify(json.load(f))
    # fallback: metas zeradas por UTD
    df = get_df()
    metas = {}
    for utd in df["Utd"].dropna().unique():
        if utd:
            metas[str(utd)] = {"seg_qui": 0, "sexta": 0}
    return jsonify(metas)

@app.route("/api/superintendencias", methods=["GET", "POST"])
def api_superintendencias():
    if request.method == "POST":
        data = request.get_json(force=True)
        with open(SUPERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "saved"})
    # Retorna mapeamento atual: UTD → Superintendência (com override se houver)
    df = get_df()
    overrides = {}
    if os.path.exists(SUPERS_FILE):
        with open(SUPERS_FILE, encoding="utf-8") as f:
            overrides = json.load(f)
    mapping = {}
    for _, row in df[["Utd", "Superintendencia"]].drop_duplicates("Utd").iterrows():
        utd = row["Utd"]
        if utd:
            mapping[utd] = overrides.get(utd, row["Superintendencia"])
    return jsonify(mapping)

@app.route("/api/atualizar-dados", methods=["POST"])
def api_atualizar_dados():
    if not os.path.exists(ESCOLHER_DATAS_SCRIPT):
        return jsonify({"status": "error", "message": "Script não encontrado em: " + ESCOLHER_DATAS_SCRIPT}), 404
    try:
        subprocess.Popen(
            f'start "" python "{ESCOLHER_DATAS_SCRIPT}"',
            cwd=ESCOLHER_DATAS_DIR,
            shell=True,
        )
        return jsonify({"status": "started"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

@app.route("/api/calendar")
def api_calendar():
    df = get_df()
    by_date = df.groupby("data_str").size().reset_index(name="total")
    return jsonify(by_date.to_dict("records"))

if __name__ == "__main__":
    print("=" * 60)
    print("  PECLD - Painel de Analise  |  servidor local")
    print("=" * 60)
    print(f"\nPasta de dados:\n  {FOLDER}\n")
    load_data()
    print("Acesse:  http://localhost:5000")
    print("Ctrl+C para encerrar\n")
    app.run(port=5000, host="0.0.0.0", debug=False)
