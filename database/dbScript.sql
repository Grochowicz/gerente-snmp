CREATE TABLE usuarios (
    id_usuario SERIAL NOT NULL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    senha VARCHAR(255) NOT NULL,
    tipo BOOLEAN NOT NULL,
    departamento VARCHAR(100)
);

CREATE TABLE salas (
    id_sala SERIAL NOT NULL PRIMARY KEY,
    numero INT NOT NULL,
    bloco VARCHAR(5) NOT NULL,
    numero_pcs INT
);


CREATE TABLE maquinas (
    id_maquina SERIAL NOT NULL PRIMARY KEY,
    nome VARCHAR(25) NOT NULL,
    ip CHAR(12) NOT NULL,
    tipo_maquina BOOLEAN NOT NULL,
    id_sala INT NOT NULL,
    mac CHAR(12),
    FOREIGN KEY (id_sala) REFERENCES salas(id_sala)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE switches (
    id_switch SERIAL NOT NULL PRIMARY KEY,
    numero_portas INT NOT NULL,
    ip CHAR(12) NOT NULL,
    mac CHAR(12) NOT NULL,
    versao_snmp INT NOT NULL,
    porta_uplink INT NOT NULL,
    chave_community VARCHAR(32),
    protocolo_autenticacao VARCHAR(25),
    protocolo_criptografia VARCHAR(25),
    chave_autenticacao VARCHAR(256),
    chave_privada VARCHAR(256),
    nivel_seguranca INT
);

CREATE TABLE ligacao_sala_switch (
    id_sala INT NOT NULL,
    id_switch INT NOT NULL,
    PRIMARY KEY (id_sala, id_switch),
    FOREIGN KEY (id_sala) REFERENCES salas(id_sala)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (id_switch) REFERENCES switches(id_switch)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE agendamento_sala_switch (
    id_sala INT NOT NULL,
    id_switch INT NOT NULL,
    data_inicio TIMESTAMP NOT NULL,
    data_fim TIMESTAMP NOT NULL,
    PRIMARY KEY (id_sala, id_switch),
    FOREIGN KEY (id_sala) REFERENCES salas(id_sala)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (id_switch) REFERENCES switches(id_switch)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE maquinas_usadas_professores (
    id_funcionario INT NOT NULL,
    id_maquina_professor INT NOT NULL,
    data_acesso TIMESTAMP,
    PRIMARY KEY (id_funcionario, id_maquina_professor),
    FOREIGN KEY (id_funcionario) REFERENCES funcionarios(id_funcionario)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (id_maquina_professor) REFERENCES maquinas(id_maquina)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE maquinas_conectadas_switch (
    id_maquina INT NOT NULL PRIMARY KEY,
    id_switch INT NOT NULL,
    status BOOLEAN NOT NULL,
    porta INT NOT NULL,
    FOREIGN KEY (id_maquina) REFERENCES maquinas(id_maquina)
        ON DELETE SET NULL
        ON UPDATE CASCADE,
    FOREIGN KEY (id_switch) REFERENCES switches(id_switch)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);
