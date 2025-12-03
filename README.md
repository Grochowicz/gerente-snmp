OGMR — Execução via Streamlit

Visão rápida

Este repositório contém o back-end do projeto OGMR. A interface é uma aplicação Streamlit que usa CSVs em `app/data` como armazenamento (simulando um banco de dados).

Pré-requisitos

- Python 3.8+ recomendado
- Não é necessário banco relacional: todos os dados são arquivos CSV em `app/data`.
- (Opcional) easysnmp + dependências nativas para funcionalidades SNMP

Instalação

No diretório `back-end`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Observação: a instalação de `easysnmp` pode requerer bibliotecas do sistema (net-snmp). Se você não precisar executar comandos SNMP reais, pode ignorar a instalação; o app exibirá um fallback informando que SNMP não está disponível.

Configuração do banco

1) Usar o banco configurado em `config.py` (PostgreSQL por exemplo)

A configuração de banco foi removida — o projeto usa CSVs em `app/data`. Para personalizar o caminho dos CSVs, edite `config.py` (variável `CSV_DATA_DIR`).

Executando a interface Streamlit

No diretório `back-end`, execute:

```bash
streamlit run main.py
```

A interface abrirá no navegador. Faça login com um usuário existente na tabela `usuarios` (o projeto original usava senha em texto plano). Após o login, selecione a sala e visualize as máquinas. Se `easysnmp` estiver disponível e os switches configurados com `chave_community`, os botões de bloquear/desbloquear irão tentar enviar SETs SNMP.

Agendamento

O app grava agendamentos no CSV `app/data/agendamento_sala_switch.csv` e também cria entradas no crontab do usuário (quando solicitado pela interface). Um script externo (`run_snmp_action.py`) é usado para executar ações SNMP quando o crontab dispara os comandos.

Notas finais

- Esta é uma adaptação inicial para Streamlit. Para produção, considere: autenticação segura (hash de senhas), tratamento de permissões, testes e integração com o processo agendador (cron) e o gerente SNMP.
