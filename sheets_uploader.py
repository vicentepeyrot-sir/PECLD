import os
import glob
import logging
import unicodedata
import re
from datetime import datetime
import pandas as pd

import config

logger = logging.getLogger(__name__)

# Pasta de destino no Google Drive compartilhado (uso local)
PASTA_DRIVE = r"G:\Drives compartilhados\PCP\Time STC\PECLDTESTE"

# Pasta de dados para GitHub Actions / GitHub Pages
PASTA_GITHUB_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def normalizar_coluna(nome: str) -> str:
    """
    Limpa o nome de uma coluna:
    - Remove espaços nas bordas
    - Converte acentos e caracteres especiais para ASCII equivalente
      (ex: 'ção' → 'cao', 'nº' → 'n')
    - Substitui espaços internos por '_'
    - Remove qualquer caractere que não seja letra, dígito ou '_'
    - Colapsa múltiplos '_' seguidos em um único
    """
    nome = nome.strip()
    # Decompõe acentos e descarta os diacríticos (categoria 'Mn')
    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.category(c) == "Mn")
    nome = nome.replace(" ", "_")
    nome = re.sub(r"[^\w]", "", nome)   # mantém letras, dígitos e '_'
    nome = re.sub(r"_+", "_", nome)     # colapsa '__' → '_'
    nome = nome.strip("_")
    return nome

def _ler_csv_com_encoding(arquivo: str) -> pd.DataFrame:
    """Tenta ler o CSV nos encodings mais comuns até um deles funcionar sem mojibake."""
    # utf-8-sig cobre UTF-8 com BOM (comum em exports do Windows)
    # cp1252 cobre a maioria dos sistemas Windows brasileiros
    # ISO-8859-1 é o fallback final (nunca levanta UnicodeDecodeError)
    for enc in ("utf-8-sig", "utf-8", "cp1252", "ISO-8859-1"):
        try:
            df = pd.read_csv(arquivo, sep=";", encoding=enc, dtype=str)
            logger.debug(f"Arquivo '{os.path.basename(arquivo)}' lido com encoding {enc}.")
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Nenhum encoding funcionou para '{arquivo}'")


def carregar_dados_csv(prefixo):
    """
    Lê todos os CSVs na pasta TEMP que começam com o prefixo informado e concatena em um DataFrame.
    """
    padrao = os.path.join(config.dir_temp, f"{prefixo}*.csv")
    arquivos = glob.glob(padrao)

    if not arquivos:
        logger.warning(f"Nenhum arquivo CSV encontrado com o prefixo '{prefixo}'.")
        return pd.DataFrame()

    dfs = []
    for arquivo in arquivos:
        try:
            df = _ler_csv_com_encoding(arquivo)
            dfs.append(df)
        except Exception as e:
            logger.error(f"Erro ao ler o arquivo {arquivo}: {e}")
            
    if dfs:
        df_concat = pd.concat(dfs, ignore_index=True)
        # Normaliza nomes de colunas: remove acentos, espaços e caracteres especiais
        df_concat.columns = [normalizar_coluna(c) for c in df_concat.columns]
        # Remove registros totalmente vazios, se houver
        df_concat.dropna(how="all", inplace=True)
        # Preenche os NaN com string vazia para não dar erro no JSON do gspread
        df_concat.fillna("", inplace=True)
        
        # Normaliza e limpa os valores de cada coluna de texto
        for col in df_concat.columns:
            if df_concat[col].dtype == 'object':
                # Remove aspa simples no início (evita bug de string no Excel)
                df_concat[col] = df_concat[col].str.replace(r"^'", "", regex=True)
                # Normaliza unicode NFKC: corrige caracteres compostos mal formados
                # e garante que acentos (ã, ç, é, etc.) sejam exibidos corretamente
                df_concat[col] = df_concat[col].apply(
                    lambda v: unicodedata.normalize("NFKC", v) if isinstance(v, str) else v
                )
                
        return df_concat
    else:
        return pd.DataFrame()

def _sem_acento(texto: str) -> str:
    """Remove acentos para comparações tolerantes (ex: 'Não' == 'Nao')."""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def extrair_valor_laudo(texto):
    """
    Replica a fórmula Excel:
    =SEERRO(VALOR(EXT.TEXTO(...; LOCALIZAR("$";...)+1; MÍNIMO(pos @, |, espaço, vírgula) - pos $ - 1));"")
    Extrai o número imediatamente após o primeiro '$' na string,
    encerrando no primeiro '@', '|', ' ' ou ',' encontrado depois dele.
    """
    if not isinstance(texto, str) or "$" not in texto:
        return ""
    pos = texto.index("$") + 1
    substr = texto[pos:]
    delimitadores = []
    for d in ["@", "|", " ", ","]:
        idx = substr.find(d)
        if idx != -1:
            delimitadores.append(idx)
    fim = min(delimitadores) if delimitadores else len(substr)
    valor_str = substr[:fim].strip()
    try:
        return float(valor_str.replace(",", "."))
    except (ValueError, AttributeError):
        return ""

def salvar_excel_drive(abas: dict, sufixo: str = None):
    """
    Salva um arquivo Excel com múltiplas abas na pasta do Drive.
    abas:   dict de {nome_aba: DataFrame}
    sufixo: texto adicionado ao nome do arquivo (ex: '01-05-2026_a_27-05-2026')
    """
    os.makedirs(PASTA_DRIVE, exist_ok=True)
    _sufixo = sufixo if sufixo else datetime.now().strftime("%Y-%m-%d")
    nome_arquivo = f"PECLD_{_sufixo}.xlsx"
    caminho = os.path.join(PASTA_DRIVE, nome_arquivo)

    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        for nome_aba, df in abas.items():
            df.to_excel(writer, sheet_name=nome_aba, index=False)
            logger.info(f"Aba '{nome_aba}' salva com {len(df)} registros.")

    logger.info(f"Arquivo salvo em: {caminho}")

def _processar_csv(data_inicio=None, data_fim=None) -> pd.DataFrame:
    """
    Carrega e processa os CSVs da pasta TEMP/, retornando o DataFrame filtrado.
    Lógica compartilhada entre enviar_para_sheets e enviar_para_github.
    """
    df_executadas = carregar_dados_csv("cs_executados")

    GRUPOS_FILTRO = [
        "CORTE A -", "CORTE B -", "CORTE C -", "CORTE TOP25 -",
        "RECORTE A -", "RECORTE B -", "RECORTE C -",
    ]

    mapeamento_colunas = {
        "equipe": "equipe_desp",
        "centro_servico": "Utd",
        "tipo_servico": "grupo_servico",
        "zona_servico": "Regional"
    }

    if not df_executadas.empty:
        dict_rename = {}
        for col_atual in df_executadas.columns:
            nome_limpo = col_atual.strip().lower()
            for chave, novo_nome in mapeamento_colunas.items():
                if nome_limpo == chave:
                    dict_rename[col_atual] = novo_nome
        df_executadas = df_executadas.rename(columns=dict_rename)

        # Filtra apenas os grupo_servico desejados
        if "grupo_servico" in df_executadas.columns:
            df_exec_filtrado = df_executadas[
                df_executadas["grupo_servico"].str.strip().isin(GRUPOS_FILTRO)
            ].copy()
        else:
            logger.warning("Coluna 'grupo_servico' não encontrada. Nenhum filtro aplicado.")
            df_exec_filtrado = df_executadas.copy()
    else:
        df_exec_filtrado = df_executadas

    # 2. Filtrar por período, se informado
    if (data_inicio is not None or data_fim is not None) and not df_exec_filtrado.empty:
        COLUNAS_DATA = ["data_exec", "dt_exec", "data_execucao", "data_conclusao",
                        "data_atendimento", "data_servico"]
        col_data = next((c for c in df_exec_filtrado.columns if c.lower() in COLUNAS_DATA), None)

        if col_data:
            def parse_data(valor):
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        return datetime.strptime(str(valor).strip(), fmt).date()
                    except ValueError:
                        continue
                return None

            datas_serie = df_exec_filtrado[col_data].apply(parse_data)
            mask = pd.Series([True] * len(df_exec_filtrado), index=df_exec_filtrado.index)
            if data_inicio:
                mask &= datas_serie >= data_inicio
            if data_fim:
                mask &= datas_serie <= data_fim
            df_exec_filtrado = df_exec_filtrado[mask].copy()
            logger.info(f"Registros após filtro de período: {len(df_exec_filtrado)}")
        else:
            logger.warning(f"Nenhuma coluna de data reconhecida. Colunas disponíveis: {list(df_exec_filtrado.columns)}")

    # 3. Filtrar coluna AD pela situação da coluna AC
    if not df_exec_filtrado.empty:
        n_cols = len(df_exec_filtrado.columns)
        if n_cols > 29:
            col_ac = df_exec_filtrado.columns[28]  # posição AC no Excel (índice 28)
            col_ad = df_exec_filtrado.columns[29]  # posição AD no Excel (índice 29)
            PREFIXOS_AD = ("96001", "96002", "96003")

            col_ac_norm = df_exec_filtrado[col_ac].str.strip().apply(
                lambda v: _sem_acento(v).lower() if isinstance(v, str) else v
            )
            vnr = col_ac_norm == "visitado nao realizado"
            ad_ok = df_exec_filtrado[col_ad].str.strip().str.startswith(PREFIXOS_AD)

            # "Visitado Nao Realizado" só fica se AD começar com os prefixos permitidos;
            # qualquer outro status (incluindo "Visitado Realizado") é mantido sem restrição.
            df_exec_filtrado = df_exec_filtrado[~vnr | (vnr & ad_ok)].copy()
            logger.info(f"Registros após filtro Visitado/AD: {len(df_exec_filtrado)}")
        else:
            logger.warning(
                f"DataFrame tem apenas {n_cols} colunas; filtro AC/AD não aplicado "
                f"(esperado mínimo 30 colunas para AC=28, AD=29)."
            )

    # 4. Criar coluna VALOR extraída da coluna laudo
    if not df_exec_filtrado.empty and "laudo" in df_exec_filtrado.columns:
        df_exec_filtrado = df_exec_filtrado.copy()
        df_exec_filtrado["VALOR"] = df_exec_filtrado["laudo"].apply(extrair_valor_laudo)
    else:
        logger.warning("Coluna 'laudo' não encontrada. Coluna VALOR não será criada.")

    return df_exec_filtrado


def enviar_para_sheets(data_inicio=None, data_fim=None):
    """
    Processa os CSVs e os salva como arquivo Excel na pasta do Drive compartilhado.
    data_inicio / data_fim: objetos datetime.date (período inclusivo) ou None (sem filtro).
    """
    if data_inicio and data_fim:
        logger.info(f"Período selecionado: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")
    else:
        logger.info("Iniciando processo de salvamento na pasta do Drive...")

    df = _processar_csv(data_inicio, data_fim)

    if data_inicio and data_fim:
        sufixo = f"{data_inicio.strftime('%d-%m-%Y')}_a_{data_fim.strftime('%d-%m-%Y')}"
    elif data_inicio:
        sufixo = f"a_partir_{data_inicio.strftime('%d-%m-%Y')}"
    elif data_fim:
        sufixo = f"ate_{data_fim.strftime('%d-%m-%Y')}"
    else:
        sufixo = datetime.now().strftime("%Y-%m-%d")

    salvar_excel_drive({"Executadas": df}, sufixo=sufixo)
    logger.info("Salvamento na pasta do Drive concluído com sucesso!")


def enviar_para_github(data_inicio=None, data_fim=None):
    """
    Processa os CSVs e mescla os dados no arquivo data/dados_pecld.xlsx.
    Usado pelo GitHub Actions para acumular dados e servir o GitHub Pages.
    data_inicio / data_fim: objetos datetime.date ou None (sem filtro de data).
    """
    logger.info("Processando dados para GitHub Pages...")

    df_novo = _processar_csv(data_inicio, data_fim)

    if df_novo.empty:
        logger.warning("Nenhum dado novo encontrado nos CSVs. Abortando.")
        return

    os.makedirs(PASTA_GITHUB_DATA, exist_ok=True)
    arquivo = os.path.join(PASTA_GITHUB_DATA, "dados_pecld.xlsx")

    if os.path.exists(arquivo):
        try:
            df_existente = pd.read_excel(arquivo, sheet_name="Executadas", engine="openpyxl")
            df_merged = pd.concat([df_existente, df_novo], ignore_index=True)
            if "num_servico" in df_merged.columns:
                df_merged = df_merged.drop_duplicates(subset=["num_servico"])
            logger.info(
                f"Mesclado: {len(df_existente)} existentes + {len(df_novo)} novos "
                f"= {len(df_merged)} únicos"
            )
        except Exception as exc:
            logger.warning(f"Erro ao carregar dados existentes: {exc}. Usando apenas dados novos.")
            df_merged = df_novo
    else:
        df_merged = df_novo
        logger.info(f"Primeiro carregamento: {len(df_merged)} registros")

    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        df_merged.to_excel(writer, sheet_name="Executadas", index=False)

    logger.info(f"Salvo: {arquivo} ({len(df_merged)} registros totais)")


if __name__ == "__main__":
    from logger_config import setup_logger
    setup_logger()
    enviar_para_sheets()
