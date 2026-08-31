import re
import json
import urllib.request
import urllib.error
from flask import jsonify, request
from . import api_bp

@api_bp.route("/cep/<path:cep>", methods=["GET"])
def consultar_cep(cep):
    """
    Consulta o CEP na API do ViaCEP de forma centralizada e padronizada.
    Utiliza urllib da biblioteca padrão para máxima portabilidade e zero dependências externas.
    """
    # Remove qualquer caracter que não seja dígito
    cep_limpo = re.sub(r"\D", "", cep or "")

    if len(cep_limpo) != 8:
        return jsonify({
            "success": False,
            "erro": "CEP deve conter exatamente 8 dígitos numéricos.",
            "codigo": "cep_invalido"
        }), 400

    url = f"https://viacep.com.br/ws/{cep_limpo}/json/"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SiGI/1.0 (Sistema Integrado de Gestao de Igreja)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                return jsonify({
                    "success": False,
                    "erro": "Serviço de consulta de CEP temporariamente indisponível.",
                    "codigo": "servico_indisponivel"
                }), 502

            raw_data = response.read().decode("utf-8")
            data = json.loads(raw_data)

            if data.get("erro"):
                return jsonify({
                    "success": False,
                    "erro": "CEP não encontrado.",
                    "codigo": "cep_nao_encontrado"
                }), 404

            return jsonify({
                "success": True,
                "cep": data.get("cep", ""),
                "logradouro": data.get("logradouro", ""),
                "complemento": data.get("complemento", ""),
                "bairro": data.get("bairro", ""),
                "cidade": data.get("localidade", ""),
                "estado": data.get("uf", ""),
                "uf": data.get("uf", ""),
                "ibge": data.get("ibge", ""),
                "ddd": data.get("ddd", "")
            }), 200

    except urllib.error.HTTPError as e:
        return jsonify({
            "success": False,
            "erro": "Falha na comunicação com o serviço de CEP.",
            "codigo": f"http_error_{e.code}"
        }), 502
    except urllib.error.URLError:
        return jsonify({
            "success": False,
            "erro": "Não foi possível conectar ao serviço de CEP. Verifique a conexão.",
            "codigo": "erro_conexao"
        }), 504
    except Exception as e:
        return jsonify({
            "success": False,
            "erro": f"Falha ao consultar o CEP: {str(e)}",
            "codigo": "erro_interno"
        }), 500

