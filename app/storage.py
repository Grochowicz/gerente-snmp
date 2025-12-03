import csv
import os
from typing import List, Dict

BASE_DIR = os.path.join(os.path.dirname(__file__), "data")

ENTITIES = {
    "salas": {
        "file": "salas.csv",
        "fields": ["id_sala", "numero", "bloco", "numero_pcs"]
    },
    "switches": {
        "file": "switches.csv",
        "fields": ["id_switch", "numero_portas", "ip", "mac", "versao_snmp", "porta_uplink", "chave_community", "protocolo_autenticacao", "protocolo_criptografia", "chave_autenticacao", "chave_privada", "nivel_seguranca"]
    },
    "maquinas": {
        "file": "maquinas.csv",
        "fields": ["id_maquina", "nome", "ip", "tipo_maquina", "id_sala", "mac", "access_allowed"]
    },
    "ligacao_sala_switch": {
        "file": "ligacao_sala_switch.csv",
        "fields": ["id_sala", "id_switch"]
    },
    "agendamento_sala_switch": {
        "file": "agendamento_sala_switch.csv",
        "fields": ["uid", "id_sala", "id_switch", "mac", "id_maquina", "data_inicio", "data_fim"]
    },
    "maquinas_conectadas_switch": {
        "file": "maquinas_conectadas_switch.csv",
        "fields": ["id_maquina", "id_switch", "status", "porta"]
    }
    ,
    "status_portas": {
        "file": "status_portas.csv",
        # armazenar apenas o estado atual por porta: um único MAC (se houver)
        "fields": ["id_switch", "switch_ip", "port", "operational", "administrative", "mac", "bridge_mac", "access_allowed"]
    }
}


def ensure_data_dir():
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)


def _get_path(entity: str) -> str:
    ensure_data_dir()
    if entity not in ENTITIES:
        raise ValueError(f"Entidade desconhecida: {entity}")
    return os.path.join(BASE_DIR, ENTITIES[entity]["file"])


def load_all(entity: str) -> List[Dict[str, str]]:
    path = _get_path(entity)
    fields = ENTITIES[entity]["fields"]
    if not os.path.exists(path):
        # criar arquivo com cabeçalho vazio
        with open(path, "w", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
        return []

    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]


def save_all(entity: str, rows: List[Dict[str, str]]) -> None:
    path = _get_path(entity)
    fields = ENTITIES[entity]["fields"]
    with open(path, "w", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            # garantir todas as chaves
            row = {k: (str(r.get(k)) if r.get(k) is not None else "") for k in fields}
            writer.writerow(row)


def append(entity: str, data: Dict[str, str]) -> None:
    path = _get_path(entity)
    fields = ENTITIES[entity]["fields"]
    exists = os.path.exists(path)
    with open(path, "a", newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        row = {k: (str(data.get(k)) if data.get(k) is not None else "") for k in fields}
        writer.writerow(row)


def next_id(entity: str, id_field: str) -> int:
    rows = load_all(entity)
    max_id = 0
    for r in rows:
        try:
            v = int(r.get(id_field) or 0)
            if v > max_id:
                max_id = v
        except Exception:
            continue
    return max_id + 1
