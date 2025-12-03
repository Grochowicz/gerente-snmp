import os
import sys
import uuid
import streamlit as st
from datetime import datetime
from crontab import CronTab

from app.snmp import SNMPManager, PortState
from app import storage


def login_section():
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Usuário")
    password = st.sidebar.text_input("Senha", type="password")
    if st.sidebar.button("Entrar"):
        if username == "admin" and password == "admin":
            st.session_state['auth'] = True
        else:
            st.sidebar.error("Credenciais inválidas")


def main():
    st.set_page_config(page_title="SNMP Manager - Controle de Acesso", layout="wide")
    st.title("SNMP Manager — Controle de Acesso à Internet")

    if 'auth' not in st.session_state:
        st.session_state['auth'] = False

    login_section()

    if not st.session_state.get('auth'):
        st.info("Faça login (usuário: admin / senha: admin) para usar a aplicação.")
        return

    st.sidebar.success("Autenticado")
    # escolher máquina do professor e quais máquinas têm acesso
    st.sidebar.markdown("---")
    st.sidebar.header("Configuração de Acesso")
    try:
        maquinas_cfg = storage.load_all("maquinas")
        # carregar conexões e switches
        conex = storage.load_all('maquinas_conectadas_switch')
        switches = storage.load_all('switches')

        # sincroniza automaticamente conexões com switches e atualiza o CSV
        def auto_sync_switches():
            switches_local = storage.load_all('switches')
            maquinas_local = storage.load_all('maquinas')
            conex_local = storage.load_all('maquinas_conectadas_switch')
            updated = 0
            added = 0
            errors_local = []

            def mac_to_oid_suffix_local(mac: str) -> str:
                if not mac:
                    return ""
                parts = [p for p in mac.replace('-', ':').split(':') if p]
                try:
                    nums = [str(int(p, 16)) for p in parts]
                    return ".".join(nums)
                except Exception:
                    return mac

            for sw in switches_local:
                try:
                    ip = sw.get('ip')
                    community = sw.get('chave_community') or sw.get('chave_community')
                    version = int(sw.get('versao_snmp') or 2)
                    # usar hostname por compatibilidade
                    snmp = SNMPManager(host=ip, community_read=community, community_write=community, version=version)
                except Exception as e:
                    errors_local.append(f"Falha conectar switch {sw.get('id_switch')} ({sw.get('ip')}): {e}")
                    continue

                for m in maquinas_local:
                    mac = m.get('mac')
                    if not mac:
                        continue
                    oid_suffix = mac_to_oid_suffix_local(mac)
                    try:
                        res = snmp.get_ports_by_mac(oid_suffix)
                        port = None
                        if hasattr(res, 'value'):
                            port = res.value
                        elif isinstance(res, list) and len(res) > 0:
                            first = res[0]
                            port = getattr(first, 'value', None)

                        if not port:
                            continue

                        try:
                            porta_int = int(port)
                        except Exception:
                            porta_int = None

                        admin_val = None
                        try:
                            stats = snmp.fetch_port_status(porta_int or 0)
                            if stats and isinstance(stats, list) and len(stats) > 0:
                                admin_val = stats[0].get('administrative')
                        except Exception:
                            admin_val = None

                        status_bool = False
                        if admin_val is not None:
                            try:
                                if str(admin_val) == '1' or str(admin_val).lower().startswith('up'):
                                    status_bool = True
                            except Exception:
                                status_bool = False

                        id_maquina = m.get('id_maquina')
                        id_switch = sw.get('id_switch')

                        found = False
                        for r in conex_local:
                            try:
                                if str(r.get('id_maquina')) == str(id_maquina) and str(r.get('id_switch')) == str(id_switch):
                                    r['porta'] = str(porta_int) if porta_int is not None else r.get('porta')
                                    r['status'] = 'True' if status_bool else 'False'
                                    found = True
                                    updated += 1
                                    break
                            except Exception:
                                continue

                        if not found:
                            new_row = {
                                'id_maquina': id_maquina,
                                'id_switch': id_switch,
                                'status': 'True' if status_bool else 'False',
                                'porta': str(porta_int) if porta_int is not None else ''
                            }
                            conex_local.append(new_row)
                            added += 1
                    except Exception as e:
                        errors_local.append(f"Erro ao consultar MAC {mac} no switch {sw.get('id_switch')}: {e}")

            try:
                storage.save_all('maquinas_conectadas_switch', conex_local)
            except Exception as e:
                errors_local.append(f"Falha ao salvar conexões: {e}")

            return updated, added, errors_local

        # Gera snapshots em status_portas.csv consultando todos switches
        def generate_status_portas_from_switches():
            switches_local = storage.load_all('switches')
            total = 0
            errors_local = []
            # carregar máquinas conhecidas (mapa mac -> maquina)
            maquinas_known = storage.load_all('maquinas')
            mac_to_machine = {(m.get('mac') or '').strip().upper(): m for m in maquinas_known if m.get('mac')}
            # carregar conexoes pré-existentes para manter portas mesmo sem MAC aprendida
            conex_pre = storage.load_all('maquinas_conectadas_switch')
            conex_map = {}
            for c in conex_pre:
                try:
                    key = f"{c.get('id_switch')}|{c.get('porta')}"
                    conex_map[key] = c
                except Exception:
                    continue

            # coletar globalmente todas as linhas que serão salvas 
            global_rows = []

            for sw in switches_local:
                ip = sw.get('ip')
                id_switch = sw.get('id_switch')
                community = sw.get('chave_community') or sw.get('chave_community')
                version = int(sw.get('versao_snmp') or 2)
                try:
                    snmp = SNMPManager(host=ip, community_read=community, community_write=community, version=version)
                except Exception as e:
                    errors_local.append(f"Falha conectar switch {id_switch} ({ip}): {e}")
                    continue

                try:
                    statuses = snmp.fetch_port_status(0)
                except Exception as e:
                    errors_local.append(f"Falha ao obter status portas {id_switch} ({ip}): {e}")
                    statuses = []

                try:
                    macs_by_port = snmp.get_macs_by_port() or {}
                except Exception:
                    macs_by_port = {}

                try:
                    bridge_mac = snmp.get_bridge_mac() or ""
                except Exception:
                    bridge_mac = ""

                for s in statuses:
                    port = s.get('port')
                    oper = s.get('operational')
                    admin = s.get('administrative')
                    learned = []
                    try:
                        learned = macs_by_port.get(port) or macs_by_port.get(str(port)) or []
                    except Exception:
                        learned = []

                    # normalizar learned MACs
                    learned_norm = [str(x).strip().upper() for x in learned if x]

                    # procurar por macs conhecidas entre as aprendidas
                    matched_mac = ''
                    for lm in learned_norm:
                        if lm in mac_to_machine:
                            matched_mac = lm
                            break

                    # se não há mac conhecida aprendida, verificar se existe conexão prévia para esta porta
                    key = f"{id_switch}|{port}"
                    prior_conn = conex_map.get(key)
                    prior_mac = ''
                    if prior_conn:
                        # tentar encontrar mac da máquina referenciada na conexão
                        try:
                            mid = prior_conn.get('id_maquina')
                            # procurar máquina com id
                            for mm in maquinas_known:
                                try:
                                    if str(mm.get('id_maquina')) == str(mid):
                                        prior_mac = (mm.get('mac') or '').strip().upper()
                                        break
                                except Exception:
                                    continue
                        except Exception:
                            prior_mac = ''

                    # decidir incluir esta porta: incluir apenas se houver matched_mac ou prior_mac
                    chosen_mac = matched_mac or prior_mac or ''
                    if chosen_mac == '' and not matched_mac:
                        # pular portas que não correspondem a máquinas conhecidas
                        continue

                    row = {
                        "id_switch": id_switch,
                        "switch_ip": ip,
                        "port": port,
                        "operational": oper,
                        "administrative": admin,
                        "mac": chosen_mac,
                        "bridge_mac": bridge_mac,
                    }
                    global_rows.append(row)
                    total += 1

            # salvar o estado atual (substituir arquivo) uma vez com todas as linhas relevantes
            try:
                storage.save_all('status_portas', global_rows)
            except Exception as e:
                errors_local.append(f"Falha gravar snapshots (save_all) para status_portas: {e}")

            return total, errors_local
        # Sincroniza maquinas_conectadas_switch e maquinas a partir do arquivo `status_portas`
        def sync_csvs_from_status_portas():
            # carregar snapshots (estado atual por porta) e indexar por switch+port
            snaps = storage.load_all('status_portas')
            latest = {}
            for r in snaps:
                try:
                    key = f"{r.get('id_switch')}|{r.get('port')}"
                    latest[key] = r
                except Exception:
                    continue

            # montar mapa mac -> record (usar campo 'mac' único)
            mac_map = {}
            for rec in latest.values():
                mac_val = (rec.get('mac') or '').strip().upper()
                if mac_val:
                    mac_map[mac_val] = rec

            # carregar máquinas e conexões
            maquinas = storage.load_all('maquinas')
            conex = storage.load_all('maquinas_conectadas_switch')
            # índice por id_maquina+id_switch para atualização
            conex_index = []
            for c in conex:
                conex_index.append(c)

            modified_conex = False
            modified_maquinas = False

            # helper para encontrar machine by mac
            mac_to_machine = { (m.get('mac') or '').strip().upper(): m for m in maquinas if m.get('mac') }

            # para cada mac descoberta, assegurar máquina e conexão
            for mac, rec in mac_map.items():
                try:
                    id_switch = rec.get('id_switch')
                    port = rec.get('port')
                    admin = rec.get('administrative')
                    status_bool = False
                    try:
                        if str(admin) == '1' or str(admin).lower().startswith('up'):
                            status_bool = True
                    except Exception:
                        status_bool = False

                    # garantir máquina existe
                    machine = mac_to_machine.get(mac)
                    if not machine:
                        # criar nova máquina com novo id
                        new_id = storage.next_id('maquinas', 'id_maquina')
                        machine = {'id_maquina': str(new_id), 'nome': '', 'ip': '', 'tipo_maquina': '', 'id_sala': '', 'mac': mac, 'access_allowed': 'True'}
                        maquinas.append(machine)
                        mac_to_machine[mac] = machine
                        modified_maquinas = True

                    # atualizar conexão
                    found = False
                    for c in conex_index:
                        if str(c.get('id_maquina')) == str(machine.get('id_maquina')) and str(c.get('id_switch')) == str(id_switch):
                            c['porta'] = str(port)
                            c['status'] = 'True' if status_bool else 'False'
                            found = True
                            modified_conex = True
                            break
                    if not found:
                        new_conn = {'id_maquina': machine.get('id_maquina'), 'id_switch': id_switch, 'status': 'True' if status_bool else 'False', 'porta': str(port)}
                        conex_index.append(new_conn)
                        modified_conex = True
                except Exception:
                    continue

            # salvar alterações
            if modified_maquinas:
                try:
                    storage.save_all('maquinas', maquinas)
                except Exception as e:
                    st.sidebar.error(f"Falha ao salvar maquinas: {e}")
            if modified_conex:
                try:
                    storage.save_all('maquinas_conectadas_switch', conex_index)
                except Exception as e:
                    st.sidebar.error(f"Falha ao salvar conexões: {e}")

            return {'maquinas_added': modified_maquinas, 'conex_updated': modified_conex}

        # executar sincronização automática sem botão
        try:
            upd_cnt, add_cnt, errs = auto_sync_switches()
            if errs:
                # mostrar apenas aviso resumido
                st.sidebar.warning(f"Sincronização automática terminou com {len(errs)} erros (ver console para detalhes).")
            # garantir que exista algum snapshot inicial em status_portas
            try:
                snaps = storage.load_all('status_portas')
                if not snaps:
                    total_snap, snap_errs = generate_status_portas_from_switches()
                    if snap_errs:
                        st.sidebar.warning(f"Erros ao gerar status_portas: {len(snap_errs)} (ver console)")
                    else:
                        st.sidebar.info(f"Gerados {total_snap} snapshots iniciais em status_portas.csv")
                # sempre tentar sincronizar CSVs a partir dos snapshots
                sync_res = sync_csvs_from_status_portas()
                if sync_res.get('maquinas_added') or sync_res.get('conex_updated'):
                    st.sidebar.info("CSV(s) sincronizados a partir de status_portas.csv")
            except Exception:
                pass
        except Exception:
            pass

        # Mostrar lista de máquinas e permitir autorizar via checkbox (auto-save)
        st.sidebar.markdown("**Autorizar máquinas (toggle)**")
        modified = False
        for m in maquinas_cfg:
            try:
                mid = str(m.get('id_maquina'))
                nome = m.get('nome') or ''
                mac = m.get('mac') or ''
                acc = m.get('access_allowed', '')
                allowed = True if acc == '' else (str(acc).lower() == 'true')
                key = f"auth_{mid}"
                val = st.sidebar.checkbox(f"{mid} - {nome} ({mac})", value=allowed, key=key)
                if val != allowed:
                    m['access_allowed'] = 'True' if val else 'False'
                    modified = True
            except Exception:
                continue

        if modified:
            try:
                storage.save_all('maquinas', maquinas_cfg)
                st.sidebar.success('Permissões atualizadas.')
            except Exception as e:
                st.sidebar.error(f'Falha ao salvar permissões: {e}')
        # se houve erros na auto-sync, mostrar detalhes num expander
        if 'errs' in locals() and errs:
            with st.sidebar.expander(f"Erros de sincronização ({len(errs)})", expanded=False):
                for err in errs[:10]:
                    st.write(err)
    except Exception as e:
        st.sidebar.error(f'Erro ao carregar/atualizar máquinas: {e}')



    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("Ação SNMP imediata")
        with st.form("snmp_form"):
            ip = st.text_input("IP do switch", value="10.90.90.90")
            community = st.text_input("Community", value="private")
            version = st.selectbox("Versão SNMP", [1, 2], index=0)
            porta = st.number_input("Porta (número)", min_value=1, value=1)
            acao = st.selectbox("Ação", ["Desabilitar (down)", "Habilitar (up)"])
            submitted = st.form_submit_button("Executar")

            if submitted:
                state = PortState.DISABLED if acao.startswith("Des") else PortState.ENABLED
                # criar sessão SNMP
                try:
                    snmp = SNMPManager(host=ip, community_read=community, community_write=community, version=version)
                except Exception as e:
                    st.error(f"Erro ao criar sessão SNMP: {e}")
                    return

                ok = snmp.set_port_state(porta, state)
                if ok:
                    st.success(f"Ação enviada para porta {porta}: {acao}")
                else:
                    st.error("Falha ao enviar SNMP SET. Verifique conexão/credentials.")

    st.markdown("---")
    st.header("Agendar bloqueio/desbloqueio via crontab")

    with st.form("agendamento_form"):
        ip_s = st.text_input("IP do switch (para agendamento)", value="10.90.90.90")
        community_s = st.text_input("Community", value="private")
        version_s = st.selectbox("Versão SNMP", [1, 2], index=0, key="ver_sched")
        # carregar máquinas do CSV e montar dropdown de MACs (filtra por access_allowed)
        maquinas = storage.load_all("maquinas")
        mac_options = []
        valid_machines_for_sched = []
        for m in maquinas:
            # somente considerar máquinas com id e mac válidos
            mid = m.get('id_maquina')
            mac = m.get('mac')
            if not mid or mid == "":
                continue
            if not mac or mac == "":
                continue
            is_prof = str(m.get('tipo_maquina', '')).lower() == 'true'
            acc = m.get('access_allowed', '')
            allowed = True if acc == '' else (str(acc).lower() == 'true')
            if not is_prof and allowed:
                mac_options.append(mac)
                valid_machines_for_sched.append(m)

        mac_sel = st.selectbox("MAC da máquina (selecionar para agendamento individual)", [""] + mac_options)

        ports_text = st.text_input("Portas (vírgula-separadas)", value="1,2,3")
        start_date = st.date_input("Data de início (bloqueio)", value=datetime.now().date())
        start_time = st.time_input("Hora de início (bloqueio)", value=datetime.now().time())

        end_date = st.date_input("Data de fim (desbloqueio)", value=datetime.now().date())
        end_time = st.time_input("Hora de fim (desbloqueio)", value=datetime.now().time())

        start_dt = datetime.combine(start_date, start_time)
        end_dt = datetime.combine(end_date, end_time)
        submit_sched = st.form_submit_button("Agendar")

        if submit_sched:
            try:
                # truncar segundos e micros para precisão de minuto do cron
                from datetime import timedelta
                start_dt_adj = start_dt.replace(second=0, microsecond=0)
                end_dt_adj = end_dt.replace(second=0, microsecond=0)

                # garantir que end_dt > start_dt; se iguais, acrescentar 1 minuto ao end
                if end_dt_adj <= start_dt_adj:
                    end_dt_adj = start_dt_adj + timedelta(minutes=1)
                    st.warning("Data/hora de fim foi ajustada para 1 minuto após o início (cron tem precisão de minuto).")

                uid = uuid.uuid4().hex
                # caminho absoluto do script `run_snmp_action.py` (mesmo diretório)
                base = os.path.dirname(__file__)
                script = os.path.abspath(os.path.join(base, "run_snmp_action.py"))
                python_exec = sys.executable or "python3"

                ports_csv = ",".join([p.strip() for p in ports_text.split(',') if p.strip()])

                cmd_disable = f'{python_exec} "{script}" --action disable --ip {ip_s} --community {community_s} --ports "{ports_csv}" --version {version_s}'
                cmd_enable = f'{python_exec} "{script}" --action enable --ip {ip_s} --community {community_s} --ports "{ports_csv}" --version {version_s}'

                cron = CronTab(user=True)

                # criar job de disable
                item_start = cron.new(command=cmd_disable, comment=f"ogmr_{uid}_start")
                item_start.setall(f"{start_dt_adj.minute} {start_dt_adj.hour} {start_dt_adj.day} {start_dt_adj.month} *")

                # criar job de enable
                item_end = cron.new(command=cmd_enable, comment=f"ogmr_{uid}_end")
                item_end.setall(f"{end_dt_adj.minute} {end_dt_adj.hour} {end_dt_adj.day} {end_dt_adj.month} *")

                cron.write()

                # gravar agendamento no CSV também (para simular banco)
                mac_val = mac_sel or ""
                id_maquina = ""
                if mac_val:
                    for m in valid_machines_for_sched:
                        if m.get("mac") == mac_val:
                            id_maquina = m.get("id_maquina", "")
                            break

                # gravar no CSV com uid para permitir remoção posterior (usar datas truncadas)
                storage.append("agendamento_sala_switch", {
                    "uid": uid,
                    "id_sala": "",
                    "id_switch": "",
                    "mac": mac_val,
                    "id_maquina": id_maquina,
                    "data_inicio": start_dt_adj.isoformat(),
                    "data_fim": end_dt_adj.isoformat()
                })

                # confirmar gravação no crontab
                created = [i for i in cron if i.comment and (i.comment == f"ogmr_{uid}_start" or i.comment == f"ogmr_{uid}_end")]
                if len(created) >= 2:
                    st.success(f"Agendamento criado (id={uid}). Bloqueio em {start_dt_adj} e desbloqueio em {end_dt_adj}.")
                    for i in created:
                        st.write(f"{i.comment}: {i.slices} -> {i.command}")
                else:
                    st.warning(f"Agendamento criado no CSV (id={uid}) mas falha ao confirmar escrita no crontab. Verifique permissões do crontab do usuário.")

                st.write("Comando disable:", cmd_disable)
                st.write("Comando enable:", cmd_enable)
                st.info("As tarefas foram adicionadas ao crontab do usuário atual (quando possível) e registradas no CSV local.")
            except Exception as e:
                st.error(f"Erro ao criar agendamento: {e}")

    # seção: status das portas por máquina (uma aba por MAC)
    st.markdown("---")
    st.header("Status das portas por máquina")
    try:
        # listar máquinas permitidas (mesma lógica usada anteriormente)
        maquinas = storage.load_all("maquinas")
        mac_options = []
        mac_map = {}
        missing_id = 0
        missing_mac = 0
        for m in maquinas:
            mid = m.get('id_maquina')
            mac = m.get('mac')
            if not mid or mid == "":
                missing_id += 1
                continue
            if not mac or mac == "":
                missing_mac += 1
                continue
            is_prof = str(m.get('tipo_maquina', '')).lower() == 'true'
            acc = m.get('access_allowed', '')
            allowed = True if acc == '' else (str(acc).lower() == 'true')
            if not is_prof and allowed:
                mac_options.append(mac)
                mac_map[mac] = m

        if not mac_options:
            st.info("Nenhuma máquina listada para visualização de portas (verifique 'Máquinas permitidas' na lateral).")
            # fornecer diagnóstico: mostrar contagens e conexões
            st.write(f"Total de registros em 'maquinas.csv': {len(maquinas)}")
            st.write(f"Registros sem 'id_maquina': {missing_id}")
            st.write(f"Registros sem 'mac': {missing_mac}")
            conex = storage.load_all('maquinas_conectadas_switch')
            st.write(f"Registros em 'maquinas_conectadas_switch.csv': {len(conex)}")
            if conex:
                st.write(conex[:10])
            st.warning("Verifique e corrija os CSVs: as máquinas precisam de 'id_maquina' e 'mac' para aparecerem.")
        else:
            tabs = st.tabs(mac_options)
            # carregar switches e conexões uma vez (chaves como strings)
            switches = {str(s.get('id_switch')): s for s in storage.load_all('switches')}
            conex = storage.load_all('maquinas_conectadas_switch')

            for tab, mac in zip(tabs, mac_options):
                with tab:
                    m = mac_map.get(mac)
                    st.subheader(f"{m.get('nome')} — {mac}")

                    # buscar registro de conexão
                    reg = None
                    for r in conex:
                        try:
                            if str(r.get('id_maquina')) == str(m.get('id_maquina')):
                                reg = r
                                break
                        except Exception:
                            continue

                    if not reg:
                        st.warning("Nenhum registro de conexão encontrado para essa máquina (verifique 'maquinas_conectadas_switch.csv').")
                        continue

                    id_switch = reg.get('id_switch')
                    porta_reg = reg.get('porta')
                    status_csv = reg.get('status')


                    sw = switches.get(str(id_switch)) if id_switch else None
                    if not sw:
                        # tentar localizar por comparações flexíveis
                        sw = None
                        for s in switches.values():
                            try:
                                if str(s.get('id_switch')) == str(id_switch):
                                    sw = s
                                    break
                            except Exception:
                                continue

                    if not sw:
                        st.error("Switch associado não encontrado.")
                        continue

                    st.write(f"Switch: {sw.get('ip')} (id {sw.get('id_switch')}) — porta registrada: {porta_reg} — status CSV: {status_csv}")

                    # preferir usar dados gravados em status_portas.csv
                    try:
                        snaps = storage.load_all('status_portas')
                        # buscar snapshots do switch atual (por id_switch ou ip)
                        sw_id = str(sw.get('id_switch'))
                        sw_ip = str(sw.get('ip'))
                        latest_by_port = {}
                        for r in snaps:
                            try:
                                if str(r.get('id_switch')) != sw_id and str(r.get('switch_ip')) != sw_ip:
                                    continue
                                port = r.get('port')
                                key = str(port)
                                # arquivo agora contém apenas estado atual por porta (um registro por switch+port)
                                latest_by_port[key] = r
                            except Exception:
                                continue

                        if latest_by_port:
                            rows = []
                            for key, rec in sorted(latest_by_port.items(), key=lambda x: int(str(x[0])) if str(x[0]).isdigit() else 0):
                                try:
                                    port = rec.get('port')
                                    oper = rec.get('operational')
                                    admin = rec.get('administrative')
                                    learned = rec.get('mac') or ''
                                    destaque = ''
                                    try:
                                        if porta_reg and int(porta_reg) == int(port):
                                            destaque = '<<'
                                    except Exception:
                                        destaque = ''
                                    rows.append({"porta": port, "operacional": oper, "administrativa": admin, "destaque": destaque, "macs_aprendidas": learned})
                                except Exception:
                                    continue
                            st.table(rows)
                        else:
                            # fallback: tentar consulta SNMP ao vivo
                            try:
                                snmp = SNMPManager(host=sw.get('ip'), community_read=sw.get('chave_community') or sw.get('chave_community'), community_write=sw.get('chave_community') or sw.get('chave_community'), version=int(sw.get('versao_snmp') or 2))
                                statuses = snmp.fetch_port_status(0)
                                macs_by_port = {}
                                try:
                                    macs_by_port = snmp.get_macs_by_port() or {}
                                except Exception:
                                    macs_by_port = {}
                                bridge_mac = ""
                                try:
                                    bridge_mac = snmp.get_bridge_mac() or ""
                                except Exception:
                                    bridge_mac = ""

                                rows = []
                                # preparar novas linhas para este switch
                                new_rows_for_switch = []
                                for s in statuses:
                                    port = s.get('port')
                                    oper = s.get('operational')
                                    admin = s.get('administrative')
                                    destaque = ''
                                    try:
                                        if porta_reg and int(porta_reg) == int(port):
                                            destaque = '<<'
                                    except Exception:
                                        destaque = ''
                                    learned_list = []
                                    try:
                                        learned_list = macs_by_port.get(port) or macs_by_port.get(str(port)) or []
                                    except Exception:
                                        learned_list = []
                                    learned_str = ",".join(learned_list) if learned_list else ""
                                    # escolher apenas um MAC por porta (primeiro)
                                    mac_single = ''
                                    if learned_list:
                                        try:
                                            mac_single = str(learned_list[0]).strip().upper()
                                        except Exception:
                                            mac_single = str(learned_list[0])

                                    # preparar linha para salvar (atualizar estado)
                                    new_rows_for_switch.append({
                                        "id_switch": sw.get('id_switch'),
                                        "switch_ip": sw.get('ip'),
                                        "port": port,
                                        "operational": oper,
                                        "administrative": admin,
                                        "mac": mac_single,
                                        "bridge_mac": bridge_mac,
                                    })

                                    rows.append({"porta": port, "operacional": oper, "administrativa": admin, "destaque": destaque, "macs_aprendidas": mac_single})
                                # atualizar arquivo status_portas substituindo as linhas deste switch
                                try:
                                    all_snaps = storage.load_all('status_portas')
                                    # filtrar outros switches
                                    preserved = [r for r in all_snaps if str(r.get('id_switch')) != str(sw.get('id_switch')) and str(r.get('switch_ip')) != str(sw.get('ip'))]
                                    merged = preserved + new_rows_for_switch
                                    storage.save_all('status_portas', merged)
                                except Exception:
                                    pass
                                st.table(rows)
                            except Exception as e:
                                st.warning(f"Falha ao consultar SNMP: {e}. Usando status do CSV quando disponível.")
                                st.write({"porta_registrada": porta_reg, "status_csv": status_csv})
                    except Exception as e:
                        st.warning(f"Erro ao ler status_portas.csv: {e}. Tentando SNMP ao vivo.")

    except Exception as e:
        st.error(f"Erro ao montar abas de status: {e}")

    # permitir listar/remover agendamentos criados pelo sistema
    st.markdown("---")
    st.header("Gerenciar agendamentos (crontab)")
    try:
        cron = CronTab(user=True)
        items = [i for i in cron if i.comment and i.comment.startswith("ogmr_")]
        if items:
            for i in items:
                st.write(f"- {i.comment}: {i.slices} -> {i.command}")
            if st.button("Remover todos os agendamentos OGMR"):
                for i in items:
                    cron.remove(i)
                cron.write()
                st.success("Agendamentos OGMR removidos.")
        else:
            st.info("Nenhum agendamento OGMR encontrado no crontab do usuário atual.")
    except Exception as e:
        st.error(f"Não foi possível acessar o crontab: {e}")

    with col2:
        st.header("Utilitários / Ajuda rápida")
        st.markdown("- Esta interface realiza ações SNMP imediatas nas portas informadas.")
        st.markdown("- Agendamentos devem ser feitos com crontab ou APScheduler.\n  (podemos adicionar integração para gravar agendamentos no banco e criar entradas no crontab)")
        st.markdown("- Campos de integração com banco de dados (salas, switches, máquinas) podem ser adicionados posteriormente.")


if __name__ == '__main__':
    main()
