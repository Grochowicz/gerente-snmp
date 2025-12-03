from flask import Blueprint, request, jsonify
from .. import snmp as snmp_mod
from .. import storage
from ..snmp import SNMPManager

"""
Este módulo agora usa CSVs via `app.storage` em vez de SQLAlchemy.
As funções de storage oferecem load_all(entity), append(entity,data), save_all(entity,rows) e next_id(entity,id_field).
"""

api = Blueprint("api", __name__)

@api.route("/salas", methods=["GET"])
def listar_salas():
    salas = storage.load_all("salas")
    return jsonify(salas)


@api.route("/salas", methods=["POST"])
def criar_sala():
    dados = request.json
    new_id = storage.next_id("salas", "id_sala")
    row = {
        "id_sala": new_id,
        "numero": dados["numero"],
        "bloco": dados["bloco"],
        "numero_pcs": dados.get("numero_pcs", "")
    }
    storage.append("salas", row)
    return jsonify({"mensagem": "Sala criada"}), 201

@api.route("/switches", methods=["GET"])
def listar_switches():
    switches = storage.load_all("switches")
    return jsonify(switches)


@api.route("/switches", methods=["POST"])
def criar_switch():
    dados = request.json
    new_id = storage.next_id("switches", "id_switch")
    row = {
        "id_switch": new_id,
        "numero_portas": dados["numero_portas"],
        "ip": dados["ip"],
        "mac": dados["mac"],
        "versao_snmp": dados["versao_snmp"],
        "porta_uplink": dados.get("porta_uplink", ""),
        "chave_community": dados.get("chave_community", ""),
        "protocolo_autenticacao": dados.get("protocolo_autenticacao", ""),
        "protocolo_criptografia": dados.get("protocolo_criptografia", ""),
        "chave_autenticacao": dados.get("chave_autenticacao", ""),
        "chave_privada": dados.get("chave_privada", ""),
        "nivel_seguranca": dados.get("nivel_seguranca", "")
    }
    storage.append("switches", row)
    return jsonify({"mensagem": "Switch criado"}), 201

@api.route("/maquinas", methods=["GET"])
def listar_maquinas():
    maquinas = storage.load_all("maquinas")
    return jsonify(maquinas)


@api.route("/maquinas", methods=["POST"])
def criar_maquina():
    dados = request.json
    new_id = storage.next_id("maquinas", "id_maquina")
    row = {
        "id_maquina": new_id,
        "nome": dados["nome"],
        "ip": dados["ip"],
        "tipo_maquina": dados["tipo_maquina"],
        "id_sala": dados.get("id_sala", ""),
        "mac": dados.get("mac", "")
    }
    storage.append("maquinas", row)
    return jsonify({"mensagem": "Máquina criada"}), 201

@api.route("/ligacoes", methods=["POST"])
def criar_ligacao():
    dados = request.json
    row = {"id_sala": dados["id_sala"], "id_switch": dados["id_switch"]}
    storage.append("ligacao_sala_switch", row)
    return jsonify({"mensagem": "Ligação criada"}), 201


@api.route("/ligacoes", methods=["GET"])
def listar_ligacoes():
    ligacoes = storage.load_all("ligacao_sala_switch")
    return jsonify(ligacoes)

@api.route("/agendamentos", methods=["POST"])
def criar_agendamento():
    dados = request.json
    # gravar também o mac e id_maquina caso fornecidos
    row = {
        "id_sala": dados.get("id_sala", ""),
        "id_switch": dados.get("id_switch", ""),
        "mac": dados.get("mac", ""),
        "id_maquina": dados.get("id_maquina", ""),
        "data_inicio": dados.get("data_inicio"),
        "data_fim": dados.get("data_fim")
    }
    storage.append("agendamento_sala_switch", row)
    return jsonify({"mensagem": "Agendamento criado"}), 201


@api.route("/agendamentos", methods=["GET"])
def listar_agendamentos():
    agends = storage.load_all("agendamento_sala_switch")
    return jsonify(agends)

@api.route("/porta", methods=["POST"])
def alterar_porta():
    dados = request.json

    id_switch = dados["id_switch"]
    id_maquina = dados["id_maquina"]
    porta = dados["porta"]
    # garantir que status seja um inteiro (1 para ligado, 0 para desligado)
    try:
        status = int(dados["status"])
    except Exception:
        return jsonify({"erro": "status inválido"}), 400

    switches = storage.load_all("switches")
    switch = None
    for s in switches:
        try:
            if int(s.get("id_switch")) == int(id_switch):
                switch = s
                break
        except Exception:
            continue

    if not switch:
        return jsonify({"erro": "switch não encontrado"}), 404

    snmp = SNMPManager(
        hostname=switch.get("ip"),
        community_read=switch.get("chave_community"),
        community_write=switch.get("chave_community"),
        version=int(switch.get("versao_snmp") or 2)
    )

    snmp_sucesso = snmp.alterar_estado_porta(porta, status)

    # atualizar CSV de maquinas_conectadas_switch
    regs = storage.load_all("maquinas_conectadas_switch")
    updated = False
    for r in regs:
        try:
            if int(r.get("id_maquina")) == int(id_maquina) and int(r.get("id_switch")) == int(id_switch):
                r["status"] = "True" if status == 1 else "False"
                updated = True
                break
        except Exception:
            continue

    if updated:
        storage.save_all("maquinas_conectadas_switch", regs)

    return jsonify({
        "sucesso": snmp_sucesso,
        "porta": porta,
        "status": status
    })
