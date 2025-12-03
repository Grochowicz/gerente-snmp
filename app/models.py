"""
Schemas leves (dataclasses) usados pela interface Streamlit.
Substituem os modelos SQLAlchemy — todo armazenamento é feito via CSV em `app/data`.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Usuario:
    id_usuario: int
    nome: str
    email: str
    senha: str
    tipo: bool
    departamento: Optional[str] = None


@dataclass
class Sala:
    id_sala: int
    numero: int
    bloco: str
    numero_pcs: Optional[int] = None


@dataclass
class Switch:
    id_switch: int
    numero_portas: int
    ip: str
    mac: str
    versao_snmp: int
    porta_uplink: Optional[int] = None
    chave_community: Optional[str] = None
    protocolo_autenticacao: Optional[str] = None
    protocolo_criptografia: Optional[str] = None
    chave_autenticacao: Optional[str] = None
    chave_privada: Optional[str] = None
    nivel_seguranca: Optional[int] = None


@dataclass
class LigacaoSalaSwitch:
    id_sala: int
    id_switch: int


@dataclass
class AgendamentoSalaSwitch:
    id_sala: int
    id_switch: int
    mac: Optional[str]
    id_maquina: Optional[int]
    data_inicio: str
    data_fim: str


@dataclass
class Maquina:
    id_maquina: int
    nome: str
    ip: str
    tipo_maquina: bool
    id_sala: Optional[int]
    mac: Optional[str]
    access_allowed: Optional[bool] = False


@dataclass
class MaquinasUsadasProfessores:
    id_funcionario: int
    id_maquina_professor: int
    data_acesso: Optional[str] = None


@dataclass
class MaquinasConectadasSwitch:
    id_maquina: int
    id_switch: int
    status: bool
    porta: int
