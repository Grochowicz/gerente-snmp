"""Launcher que inicia a interface Streamlit do projeto.

Ao executar `python main.py` este script irá chamar o Streamlit para rodar
`streamlit_app.py` (a interface web principal do sistema).
"""
import os
import subprocess
import sys


def run_streamlit():
    base = os.path.dirname(__file__)
    script = os.path.join(base, "streamlit_app.py")
    if not os.path.exists(script):
        print(f"Arquivo do Streamlit não encontrado: {script}")
        sys.exit(1)

    cmd = [
        "streamlit",
        "run",
        script,
        "--server.port",
        "8501",
        "--server.headless",
        "true",
    ]
    # Executa o Streamlit (irá bloquear até o usuário encerrar)
    return subprocess.run(cmd)


if __name__ == '__main__':
    run_streamlit()
