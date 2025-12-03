#!/usr/bin/env python3
import argparse
import sys
import logging

from app.snmp import SNMPManager, PortState


def parse_args():
    p = argparse.ArgumentParser(description="Executa ação SNMP em portas especificadas")
    p.add_argument("--action", choices=["enable", "disable"], required=True, help="enable ou disable")
    p.add_argument("--ip", required=True, help="IP do switch")
    p.add_argument("--community", required=True, help="Community string")
    p.add_argument("--ports", required=True, help="Lista de portas separadas por vírgula, ex: 1,2,3")
    p.add_argument("--version", type=int, default=2, help="Versão SNMP (1 ou 2)")
    return p.parse_args()


def main():
    args = parse_args()
    ports = []
    for part in args.ports.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            ports.append(int(part))
        except ValueError:
            logging.error("Porta inválida: %s", part)
            sys.exit(2)

    try:
        snmp = SNMPManager(host=args.ip, community_read=args.community, community_write=args.community, version=args.version)
    except Exception as e:
        logging.error("Falha ao criar SNMPManager: %s", e)
        sys.exit(3)

    state = PortState.ENABLED if args.action == "enable" else PortState.DISABLED
    ok = snmp.set_ports(ports, state)
    if ok:
        print("SUCCESS")
        sys.exit(0)
    else:
        print("FAIL")
        sys.exit(4)


if __name__ == '__main__':
    main()
