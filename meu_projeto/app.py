# Importações
from flask import Flask, render_template, request
from pyngrok import ngrok
import pandas as pd
import requests
from datetime import datetime
import os

# Configuração opcional do token do ngrok (apenas 1x por máquina)
ngrok.set_auth_token('2iu7X2ds0blGAPc1qFhMnL4fyTj_5QJoq1GZVUN1D2Fv4uurC')

# Flask app
app = Flask(__name__)
PORT = 5000

# Função para buscar dados
def fetch_data(data, empresa, token):
    url_viagens = f"http://servicos.cittati.com.br/WSIntegracaoCittati/Operacional/ConsultarViagens?data={data}&empresa={empresa}"
    headers = {
        "Content-type": "application/json",
        "Authorization": f"Basic {token}"
    }
    response = requests.get(url_viagens, headers=headers)
    return response.json() if response.status_code == 200 else None

# Processamento dos dados
def process_data(data):
    df = pd.DataFrame(data["viagens"])
    df = df[df['veiculo'] != "VNR"]
    df_filtered = df[(df['inicioRealizado'].isna()) | (df['fimRealizado'].isna())]
    return df_filtered.sort_values(by='linha')

# Rota principal
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data = request.form.get("data")
        empresa = request.form.get("empresa")
        token = request.form.get("token")

        data = datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
        response_data = fetch_data(data, empresa, token)

        if response_data:
            df = process_data(response_data)
            if not df.empty:
                return render_template("index.html", tables=[df.to_html(classes='data')], titles=df.columns.values)
            else:
                return "Nenhum dado encontrado após o processamento."
        else:
            return "Falha na obtenção de dados."
    return render_template("index.html")

# Criação da pasta templates e HTML
os.makedirs('templates', exist_ok=True)
with open('templates/index.html', 'w') as f:
    f.write("""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Consulta de Viagens</title></head>
<body>
    <h1>Consulta de Viagens</h1>
    <form method="POST">
        <label for="data">Data (dd/mm/yyyy):</label>
        <input type="text" id="data" name="data" required><br>
        <label for="empresa">Empresa:</label>
        <input type="text" id="empresa" name="empresa" required><br>
        <label for="token">Token:</label>
        <input type="text" id="token" name="token" required><br>
        <button type="submit">Consultar</button>
    </form>
    {% if tables %}
        <h2>Resultados</h2>
        {% for table in tables %}
            {{ table|safe }}
        {% endfor %}
    {% endif %}
</body>
</html>
""")

# Inicia túnel ngrok
public_url = ngrok.connect(PORT)
print(f"Public URL: {public_url}")

# Executa o app
app.run(port=PORT)