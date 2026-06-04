# -*- coding: utf-8 -*-
"""
generate_static.py
==================
Lê os XLSX de data/ e gera os arquivos JSON estáticos usados pelo GitHub Pages.

Saída (sobrescreve):
  data/os.json               → registros de notas (equivalente a /api/os)
  data/calendar.json         → contagem por data  (equivalente a /api/calendar)
  data/files.json            → lista de arquivos  (equivalente a /api/files)
  data/metas.json            → metas por UTD      (equivalente a /api/metas)
  data/superintendencias.json → mapeamento UTD→Super (equivalente a /api/superintendencias)

Uso:
    python generate_static.py
"""
import os
import json
import re
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
METAS_F  = os.path.join(BASE_DIR, "metas.json")
SUPERS_F = os.path.join(BASE_DIR, "superintendencias.json")

COLS = [
    "num_servico", "Nota", "contrato", "Utd", "Coordenador", "Supervisor",
    "grupo_servico", "Motivo_Servico", "prioridade", "situacao_servico",
    "Retorno_de_Campo", "Grupo_Retorno_de_Campo",
    "dta_exec_srv", "Regional", "Bairro", "VALOR",
    "qtd_horas_trabalhadas",
]

OUT_COLS = [
    "num_servico", "Nota", "Superintendencia", "Utd", "Coordenador",
    "grupo_servico", "prioridade", "situacao_servico", "Retorno_de_Campo",
    "Grupo_Retorno_de_Campo", "Motivo_Servico",
    "data_str", "mes", "ano", "dia_semana",
    "Regional", "Bairro", "VALOR", "tem_retorno",
]


def _super_from_contrato(v):
    m = re.search(r"STC_(.+?)_\d{4}", str(v))
    return m.group(1).replace(".", "-") if m else ""


def load_data():
    dfs, info = [], []

    if not os.path.isdir(DATA_DIR):
        print(f"[AVISO] Pasta data/ não encontrada: {DATA_DIR}")
        return pd.DataFrame(), info

    for fname in sorted(os.listdir(DATA_DIR)):
        if not fname.lower().endswith(".xlsx"):
            continue
        path = os.path.join(DATA_DIR, fname)
        try:
            tmp = pd.read_excel(
                path, engine="openpyxl",
                usecols=lambda c: c in COLS,
            )
            dfs.append(tmp)
            info.append({"name": fname, "rows": len(tmp)})
            print(f"  OK  {fname}: {len(tmp)} linhas")
        except Exception as exc:
            print(f"  ERR {fname}: {exc}")

    if not dfs:
        return pd.DataFrame(), info

    df = pd.concat(dfs, ignore_index=True)
    df = df.drop_duplicates(subset=["num_servico"])

    for col in ["Utd", "Coordenador", "grupo_servico", "prioridade",
                "Regional", "Bairro", "situacao_servico", "Motivo_Servico"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    if "contrato" in df.columns:
        df["Superintendencia"] = df["contrato"].apply(_super_from_contrato)
    else:
        df["Superintendencia"] = ""

    overrides = {}
    if os.path.exists(SUPERS_F):
        with open(SUPERS_F, encoding="utf-8") as f:
            overrides = json.load(f)
    df["Superintendencia"] = df.apply(
        lambda r: overrides.get(r["Utd"], r["Superintendencia"]), axis=1
    )

    df["dta_exec_srv"] = pd.to_datetime(df["dta_exec_srv"], errors="coerce")
    df["data_str"]     = df["dta_exec_srv"].dt.strftime("%Y-%m-%d").fillna("")
    df["mes"]          = df["dta_exec_srv"].dt.month.fillna(0).astype(int)
    df["ano"]          = df["dta_exec_srv"].dt.year.fillna(0).astype(int)
    df["dia_semana"]   = df["dta_exec_srv"].dt.dayofweek.fillna(-1).astype(int)

    df["tem_retorno"] = (
        df["Retorno_de_Campo"].notna()
        & (df["Retorno_de_Campo"].astype(str).str.strip() != "")
        & (df["Retorno_de_Campo"].astype(str) != "nan")
    )

    if "VALOR" in df.columns:
        df["VALOR"] = pd.to_numeric(df["VALOR"], errors="coerce").fillna(0)

    print(f"  Total: {len(df):,} notas de {len(dfs)} arquivo(s)")
    return df, info


def safe_records(df):
    return df.where(pd.notnull(df), None).to_dict("records")


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    size = os.path.getsize(path)
    print(f"  → {os.path.basename(path)}: {size:,} bytes")


def main():
    print("=" * 55)
    print("  Gerando JSON estático para GitHub Pages")
    print("=" * 55)

    os.makedirs(DATA_DIR, exist_ok=True)
    df, info = load_data()

    cols = [c for c in OUT_COLS if c in df.columns]
    records = safe_records(df[cols]) if not df.empty else []

    print(f"\nEscrevendo JSON em {DATA_DIR}:")
    write_json(os.path.join(DATA_DIR, "files.json"), info)
    write_json(
        os.path.join(DATA_DIR, "os.json"),
        {"total": len(records), "records": records},
    )

    if not df.empty:
        by_date = df.groupby("data_str").size().reset_index(name="total")
        cal = by_date.to_dict("records")
    else:
        cal = []
    write_json(os.path.join(DATA_DIR, "calendar.json"), cal)

    metas = {}
    if os.path.exists(METAS_F):
        with open(METAS_F, encoding="utf-8") as f:
            metas = json.load(f)
    write_json(os.path.join(DATA_DIR, "metas.json"), metas)

    overrides = {}
    if os.path.exists(SUPERS_F):
        with open(SUPERS_F, encoding="utf-8") as f:
            overrides = json.load(f)
    mapping = {}
    if not df.empty:
        for _, row in df[["Utd", "Superintendencia"]].drop_duplicates("Utd").iterrows():
            utd = row["Utd"]
            if utd:
                mapping[utd] = overrides.get(utd, row["Superintendencia"])
    write_json(os.path.join(DATA_DIR, "superintendencias.json"), mapping)

    print(f"\nConcluído. {len(records):,} notas exportadas.")


if __name__ == "__main__":
    main()
