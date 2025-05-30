from flask import Flask, render_template, request
import requests
import pandas as pd

app = Flask(__name__)

EMPRESA = "regimilson.silva@axe.gevan.com.br"
URL_AUTH = "http://servicos.cittati.com.br/WSIntegracaoCittati/Autenticacao/AutenticarUsuario/"
URL_VIAGENS_BASE = "http://servicos.cittati.com.br/WSIntegracaoCittati/Operacional/ConsultarViagens"
AUTH_HEADER = {
    "Content-type": "application/json",
    "Authorization": "Basic V1NJbnRlZ3JhY2FvUExUOndzcGx0"
}

def autenticar_usuario():
    response = requests.post(URL_AUTH, headers=AUTH_HEADER, json={})
    if response.status_code == 200:
        return response.json().get("token")
    return None

def consultar_viagens(token, data, empresa=EMPRESA, colunas=None):
    data_formatada = pd.to_datetime(data, dayfirst=True).strftime('%d/%m/%Y')
    url = f"{URL_VIAGENS_BASE}?data={data_formatada}&empresa={empresa}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        viagens = response.json().get("viagens", [])
        if not viagens:
            return None
        df = pd.DataFrame(viagens)
        if colunas:
            df = df[colunas]
        for col in ["inicioProgramado", "inicioRealizado", "fimProgramado", "fimRealizado"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%H:%M:%S')
        return df
    return None

def aplicar_filtros(df, filtros):
    for coluna, valor in filtros.items():
        if valor:
            df = df[df[coluna].astype(str).str.contains(valor, case=False, na=False)]
    return df

def viagens_em_aberto(df):
    df_sem_vnr = df[df['veiculo'].str.upper() != "VNR"]
    filtro_aberto = df_sem_vnr['inicioRealizado'].isna() | df_sem_vnr['fimRealizado'].isna()
    aberto = df_sem_vnr[filtro_aberto].sort_values(by='inicioProgramado')
    return aberto

def viagens_ociosas(df):
    saida = df[df['atividade'] == 'Saída de Garagem']
    recolhe = df[df['atividade'] == 'Recolhe']
    veic_saida_sem_recolhe = saida[~saida['veiculo'].isin(recolhe['veiculo'])]
    veic_recolhe_sem_saida = recolhe[~recolhe['veiculo'].isin(saida['veiculo'])]
    sem_pares = pd.concat([veic_saida_sem_recolhe, veic_recolhe_sem_saida])
    return sem_pares[['veiculo']].drop_duplicates()

def viagens_inconsistentes(df):
    df_sem_vnr = df[~df['veiculo'].str.contains('VNR', case=False, na=False)].copy()
    df_sem_vnr['inicioRealizado'] = pd.to_datetime(df_sem_vnr['inicioRealizado'], errors='coerce')
    duplicados = df_sem_vnr[df_sem_vnr.duplicated(subset=['veiculo', 'inicioRealizado'], keep=False)]
    return duplicados[['veiculo', 'inicioProgramado', 'inicioRealizado', 'fimProgramado', 'fimRealizado']]

def viagens_com_atraso(df):
    df = df.copy()
    df['inicioProgramado_dt'] = pd.to_datetime(df['inicioProgramado'], errors='coerce')
    df['inicioRealizado_dt'] = pd.to_datetime(df['inicioRealizado'], errors='coerce')
    df['Atraso'] = (df['inicioRealizado_dt'] - df['inicioProgramado_dt']).dt.total_seconds() > 6 * 60
    filtro = (df['atividade'] == 'Viagem Normal') & (df['sentido'] == 'I') & (df['Atraso'] == True)
    atrasadas = df.loc[filtro, ['atividade', 'linha', 'veiculo', 'sentido', 'tabela', 'inicioProgramado', 'inicioRealizado', 'Atraso']]
    return atrasadas.sort_values(by='inicioProgramado')

@app.route("/", methods=["GET", "POST"])
def index():
    data_consulta = request.form.get("data") or pd.Timestamp.today().strftime('%d/%m/%Y')

    filtros = {
        "atividade": request.form.get("atividade", "").strip(),
        "linha": request.form.get("linha", "").strip(),
        "veiculo": request.form.get("veiculo", "").strip(),
        "sentido": request.form.get("sentido", "").strip(),
        "tabela": request.form.get("tabela", "").strip(),
    }

    token = autenticar_usuario()
    if not token:
        return "Erro na autenticação", 500

    colunas = [
        "atividade", "linha", "veiculo", "sentido", "tabela",
        "inicioProgramado", "inicioRealizado", "fimProgramado", "fimRealizado"
    ]
    df = consultar_viagens(token, data_consulta, colunas=colunas)
    if df is None:
        return render_template("index.html", data=data_consulta, resultados=None, filtros=filtros, error="Nenhuma viagem encontrada.")

    df_filtrado = aplicar_filtros(df, filtros)

    resultados_html = df_filtrado.to_html(classes="table table-striped", index=False)

    # Tabelas extras
    em_aberto = viagens_em_aberto(df_filtrado).to_html(classes="table table-sm", index=False)
    ociosas = viagens_ociosas(df_filtrado).to_html(classes="table table-sm", index=False)
    inconsistentes = viagens_inconsistentes(df_filtrado).to_html(classes="table table-sm", index=False)
    com_atraso = viagens_com_atraso(df_filtrado).to_html(classes="table table-sm", index=False)

    return render_template(
        "index.html",
        data=data_consulta,
        resultados=resultados_html,
        filtros=filtros,
        aberto_html=em_aberto,
        ociosas_html=ociosas,
        inconsistentes_html=inconsistentes,
        atraso_html=com_atraso
    )



if __name__ == "__main__":
    from os import environ
    port = int(environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
