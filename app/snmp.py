from easysnmp import Session
from enum import Enum
from typing import List


class PortState(Enum):
    ENABLED = 1
    DISABLED = 2


MIB_PORT_STATUS = {
    "OPER": ".1.3.6.1.2.1.2.2.1.8",
    "ADMIN": ".1.3.6.1.2.1.2.2.1.7",
    "FDB_PORT": ".1.3.6.1.2.1.17.4.3.1.2"
}


class SNMPManager:
    def __init__(self, host: str = None, community_read: str = None, community_write: str = None, version: int = 2, timeout: int = 2, retries: int = 1, hostname: str = None, community: str = None):
        # compatibilidade: aceitar `hostname`/`community` alternativos
        if hostname and not host:
            host = hostname
        if community and not community_read:
            community_read = community
            community_write = community

        # definir valores padrão sensatos
        if host is None:
            raise ValueError('host is required for SNMPManager')
        if community_read is None:
            community_read = 'public'
        if community_write is None:
            community_write = community_read

        # criar sessões com timeout/retries (easysnmp aceita esses parâmetros)
        try:
            self.read_sess = Session(hostname=host, community=community_read, version=version, timeout=timeout, retries=retries)
            self.write_sess = Session(hostname=host, community=community_write, version=version, timeout=timeout, retries=retries)
        except Exception:
            # fallback sem timeout/retries se a opção não for suportada
            self.read_sess = Session(hostname=host, community=community_read, version=version)
            self.write_sess = Session(hostname=host, community=community_write, version=version)

    def get_ports_by_mac(self, mac: str = ""):
        if mac != "":
            # buscar porta por mac
            return self.read_sess.get(f"{MIB_PORT_STATUS['FDB_PORT']}.{mac}")
        # retorna todas se vazio
        return self.read_sess.walk(MIB_PORT_STATUS['FDB_PORT'])

    def get_fdb_entries(self) -> List[dict]:
        """Retorna lista de entradas FDB com campos {'mac': 'AA:BB:CC:DD:EE:FF', 'port': int}.
        Usa o MIB dot1dTpFdbPort e converte o sufixo do OID em endereço MAC legível."""
        entries = []
        try:
            vars = self.read_sess.walk(MIB_PORT_STATUS['FDB_PORT'])
            for v in vars:
                try:
                    # v.oid example: .1.3.6.1.2.1.17.4.3.1.2.170.187.204.221.238.255
                    oid = getattr(v, 'oid', '')
                    prefix = MIB_PORT_STATUS['FDB_PORT'] + '.'
                    if oid.startswith(prefix):
                        suffix = oid[len(prefix):]
                    else:
                        # fallback: try oid_index if available
                        suffix = getattr(v, 'oid_index', '')
                    parts = [p for p in str(suffix).split('.') if p]
                    # convert decimals to hex bytes
                    mac_bytes = []
                    for p in parts:
                        try:
                            n = int(p)
                            mac_bytes.append('%02X' % n)
                        except Exception:
                            break
                    if not mac_bytes:
                        continue
                    mac = ':'.join(mac_bytes)
                    port = None
                    try:
                        port = int(getattr(v, 'value', None))
                    except Exception:
                        port = None
                    entries.append({'mac': mac, 'port': port})
                except Exception:
                    continue
        except Exception:
            return entries
        return entries

    def get_macs_by_port(self) -> dict:
        """Retorna dicionário port -> [macs]
        Útil para listar quais MACs estão aprendidas em cada porta."""
        mapping = {}
        entries = self.get_fdb_entries()
        for e in entries:
            p = e.get('port')
            mac = e.get('mac')
            if p is None:
                continue
            mapping.setdefault(p, []).append(mac)
        return mapping

    def get_bridge_mac(self) -> str:
        """Tenta obter o MAC do switch (dot1dBaseBridgeAddress .1.3.6.1.2.1.17.1.1)."""
        BRIDGE_OID = '.1.3.6.1.2.1.17.1.1'
        try:
            v = self.read_sess.get(BRIDGE_OID)
            raw = getattr(v, 'value', None)
            if raw is None:
                return ''
            # raw may be a str of bytes; convert to hex pairs
            try:
                if isinstance(raw, bytes):
                    mac_bytes = ['%02X' % b for b in raw]
                else:
                    mac_bytes = ['%02X' % ord(c) for c in raw]
                return ':'.join(mac_bytes)
            except Exception:
                return str(raw)
        except Exception:
            return ''

    def get_if_phys_addresses(self) -> dict:
        """Retorna mapping ifIndex -> mac (ifPhysAddress .1.3.6.1.2.1.2.2.1.6)"""
        IF_PHYS = '.1.3.6.1.2.1.2.2.1.6'
        mapping = {}
        try:
            vars = self.read_sess.walk(IF_PHYS)
            for v in vars:
                try:
                    oid = getattr(v, 'oid', '')
                    prefix = IF_PHYS + '.'
                    if oid.startswith(prefix):
                        idx = oid[len(prefix):]
                    else:
                        idx = getattr(v, 'oid_index', '')
                    val = getattr(v, 'value', None)
                    if val is None:
                        continue
                    try:
                        if isinstance(val, bytes):
                            mac_bytes = ['%02X' % b for b in val]
                        else:
                            mac_bytes = ['%02X' % ord(c) for c in val]
                        mac = ':'.join(mac_bytes)
                    except Exception:
                        mac = str(val)
                    mapping[int(idx)] = mac
                except Exception:
                    continue
        except Exception:
            return mapping
        return mapping

    # altera o estado de uma porta aqui
    def set_port_state(self, port: int, state: PortState) -> bool:
        try:
            self.write_sess.set(f"{MIB_PORT_STATUS['ADMIN']}.{port}", state.value, 'i')
            return True
        except Exception as e:
            print(f"Erro ao alterar porta {port}: {e}")
            return False


    def fetch_port_status(self, port: int = 0) -> List[dict]:
        # retorna status de uma porta
        if port > 0:
                oper = self.read_sess.get(f"{MIB_PORT_STATUS['OPER']}.{port}").value
                admin = self.read_sess.get(f"{MIB_PORT_STATUS['ADMIN']}.{port}").value
                return [{"port": port, "operational": oper, "administrative": admin}]

        statuses = []
        oper_list = self.read_sess.walk(MIB_PORT_STATUS['OPER'])
        admin_list = self.read_sess.walk(MIB_PORT_STATUS['ADMIN'])

        # retorna status de várias portas
        for idx, (oper, admin) in enumerate(zip(oper_list, admin_list), start=1):
            statuses.append({
                "port": idx,
                "operational": oper.value,
                "administrative": admin.value
            })
        return statuses

    def set_ports(self, ports: List[int], state: PortState) -> bool:
        for p in ports:
            if not self.set_port_state(p, state):
                return False
        return True

    # Métodos com nomes em português compatíveis com rotas existentes
    def alterar_estado_porta(self, porta: int, estado: int) -> bool:
        """Compatibilidade: recebe porta e estado (1 para ligado/enable, 2 para desligado/disable).
        Retorna True se teve sucesso."""
        try:
            # assumir que estado segue os mesmos valores do enum PortState
            # mapear estado inteiro para PortState se possível
            if estado == PortState.ENABLED.value:
                estado_enum = PortState.ENABLED
            else:
                estado_enum = PortState.DISABLED
            return self.set_port_state(porta, estado_enum)
        except Exception as e:
            print(f"Erro alterar_estado_porta: {e}")
            return False

    def alterar_estado_portas(self, portas: List[int], estado: int) -> bool:
        try:
            if estado == PortState.ENABLED.value:
                estado_enum = PortState.ENABLED
            else:
                estado_enum = PortState.DISABLED
            return self.set_ports(portas, estado_enum)
        except Exception as e:
            print(f"Erro alterar_estado_portas: {e}")
            return False
