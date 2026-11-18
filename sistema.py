# -*- coding: utf-8 -*-
"""
Neighborhood Action Dashboard - Global Solution 2026.2 (FIAP)

Prototipo em terminal para cadastrar, consultar e acompanhar ocorrencias
comunitarias (iluminacao, acessibilidade, limpeza e conservacao).
Todos os dados sao FICTICIOS. Nao ha integracao com orgaos publicos.

Executar:  python src/sistema.py

Estruturas usadas (e por que):
  - LISTA     : guarda todas as ocorrencias e permite percorre-las.
  - FILA      : demandas ainda nao examinadas, na ordem de registro (FIFO).
  - PILHA     : ultimos eventos de status (LIFO: o mais recente sai primeiro).
  - DICIONARIO: acesso direto a uma ocorrencia pelo identificador.
  - HIERARQUIA: bairro -> categoria -> ocorrencias (dicionarios aninhados).
  - MATRIZ    : lista de listas com quantidade por categoria x situacao.
"""

import os

# ----------------------------------------------------------------------
# Valores padronizados (identificadores em minusculo e sem acento)
# ----------------------------------------------------------------------
CATEGORIAS = {
    "iluminacao": "Iluminação",
    "acessibilidade": "Acessibilidade",
    "limpeza": "Limpeza",
    "conservacao": "Conservação",
}

STATUS = {
    "aberta": "Aberta",
    "em analise": "Em análise",
    "concluida": "Concluída",
}

SIGNIFICADO_STATUS = {
    "aberta": "registrada e ainda na fila, ninguem examinou",
    "em analise": "ja foi examinada e esta sendo avaliada",
    "concluida": "problema tratado e caso encerrado",
}

# Fluxo permitido de situacao: so avanca, nunca volta
TRANSICOES = {
    "aberta": ["em analise"],
    "em analise": ["concluida"],
    "concluida": [],
}

OBRIGATORIOS = ["id", "bairro", "categoria", "descricao", "local",
                "dia_abertura", "status"]


# ----------------------------------------------------------------------
# Utilitarios
# ----------------------------------------------------------------------
def normalizar(texto):
    """Minusculo, sem espacos nas pontas e sem acentos (ex.: 'Em Análise' -> 'em analise')."""
    texto = texto.strip().lower()
    trocas = {"á": "a", "à": "a", "ã": "a", "â": "a", "é": "e", "ê": "e",
              "í": "i", "ó": "o", "õ": "o", "ô": "o", "ú": "u", "ç": "c"}
    resultado = ""
    for letra in texto:
        if letra in trocas:
            resultado = resultado + trocas[letra]
        else:
            resultado = resultado + letra
    return resultado


def converter_dia(texto):
    """Converte texto em inteiro; devolve None se estiver vazio."""
    if texto == "":
        return None
    return int(texto)


def contem_dado_pessoal(texto):
    """Regra de privacidade: bloqueia e-mail (@) ou sequencias longas de numeros (telefone/CPF)."""
    digitos = 0
    for letra in texto:
        if letra.isdigit():
            digitos = digitos + 1
    return ("@" in texto) or (digitos >= 8)


def criar_sistema():
    return {
        "lista": [],        # lista de ocorrencias (cada uma e um dicionario)
        "indice": {},       # dicionario id -> ocorrencia
        "fila": [],         # fila de ids ainda nao examinados
        "pilha": [],        # pilha de eventos (id, de, para, dia)
        "hierarquia": {},   # bairro -> categoria -> [ids]
        "invalidos": [],    # registros rejeitados na carga
        "dia_atual": 1,     # relogio simulado
    }


# ----------------------------------------------------------------------
# Leitura e validacao
# ----------------------------------------------------------------------
def ler_arquivo(caminho):
    """Le o CSV (separador ';') e devolve uma lista de dicionarios."""
    registros = []
    arquivo = open(caminho, "r", encoding="utf-8-sig")
    linhas = arquivo.readlines()
    arquivo.close()
    cabecalho = linhas[0].strip().split(";")
    for numero in range(1, len(linhas)):
        linha = linhas[numero].strip()
        if linha == "":
            continue
        partes = linha.split(";")
        while len(partes) < len(cabecalho):
            partes.append("")
        reg = {}
        for i in range(len(cabecalho)):
            reg[cabecalho[i]] = partes[i].strip()
        reg["_linha"] = numero + 1
        registros.append(reg)
    return registros


def validar_registro(reg, indice):
    """Devolve a lista de problemas encontrados (lista vazia = registro valido)."""
    problemas = []

    # Regra 1: campos obrigatorios nao podem faltar
    for campo in OBRIGATORIOS:
        if reg.get(campo, "").strip() == "":
            problemas.append("campo obrigatório ausente: " + campo)
    if len(problemas) > 0:
        return problemas

    categoria = normalizar(reg["categoria"])
    status = normalizar(reg["status"])
    dia_analise = reg.get("dia_analise", "")
    dia_conclusao = reg.get("dia_conclusao", "")

    # Regra 2: categoria e situacao precisam ser valores conhecidos
    if categoria not in CATEGORIAS:
        problemas.append("categoria desconhecida: " + reg["categoria"])
    if status not in STATUS:
        problemas.append("situação desconhecida: " + reg["status"])

    # Regra 3: identificador unico
    if reg["id"] in indice:
        problemas.append("identificador duplicado: " + reg["id"])

    # Regra 4: datas simuladas devem ser numeros
    datas_ok = True
    if not reg["dia_abertura"].isdigit():
        problemas.append("dia de abertura inválido")
        datas_ok = False
    if dia_analise != "" and not dia_analise.isdigit():
        problemas.append("dia de análise inválido")
        datas_ok = False
    if dia_conclusao != "" and not dia_conclusao.isdigit():
        problemas.append("dia de conclusão inválido")
        datas_ok = False

    # Regra 5: coerencia entre situacao e datas (usa AND, OR e NOT)
    if status == "concluida" and (dia_analise == "" or dia_conclusao == ""):
        problemas.append("ocorrência concluída sem dia de análise/conclusão")
    if status == "aberta" and (dia_analise != "" or dia_conclusao != ""):
        problemas.append("ocorrência aberta não pode ter dia de análise/conclusão")
    if datas_ok and dia_analise != "":
        if int(dia_analise) < int(reg["dia_abertura"]):
            problemas.append("análise anterior à abertura")
    return problemas


# ----------------------------------------------------------------------
# Estruturas de dados
# ----------------------------------------------------------------------
def adicionar_hierarquia(sistema, oc):
    h = sistema["hierarquia"]
    if oc["bairro"] not in h:
        h[oc["bairro"]] = {}
    if oc["categoria"] not in h[oc["bairro"]]:
        h[oc["bairro"]][oc["categoria"]] = []
    h[oc["bairro"]][oc["categoria"]].append(oc["id"])


def registrar_ocorrencia(sistema, reg):
    """Guarda uma ocorrencia ja validada em todas as estruturas."""
    oc = {
        "id": reg["id"],
        "bairro": reg["bairro"],
        "categoria": normalizar(reg["categoria"]),
        "descricao": reg["descricao"],
        "local": reg["local"],
        "dia_abertura": int(reg["dia_abertura"]),
        "status": normalizar(reg["status"]),
        "dia_analise": converter_dia(reg.get("dia_analise", "")),
        "dia_conclusao": converter_dia(reg.get("dia_conclusao", "")),
    }
    sistema["lista"].append(oc)                 # lista
    sistema["indice"][oc["id"]] = oc            # dicionario
    adicionar_hierarquia(sistema, oc)           # hierarquia
    if oc["status"] == "aberta":
        sistema["fila"].append(oc["id"])        # enfileirar
    for dia in [oc["dia_abertura"], oc["dia_analise"], oc["dia_conclusao"]]:
        if dia is not None and dia > sistema["dia_atual"]:
            sistema["dia_atual"] = dia
    return oc


def empilhar_evento(sistema, id_oc, de, para, dia):
    sistema["pilha"].append((id_oc, de, para, dia))


def ultimos_eventos(sistema, quantidade):
    """Le a pilha do topo para a base (evento mais recente primeiro)."""
    eventos = []
    posicao = len(sistema["pilha"]) - 1
    while posicao >= 0 and len(eventos) < quantidade:
        eventos.append(sistema["pilha"][posicao])
        posicao = posicao - 1
    return eventos


def carregar_dados(sistema, caminho):
    """Carrega o CSV, separa validos de invalidos e reconstroi o historico."""
    registros = ler_arquivo(caminho)
    for reg in registros:
        problemas = validar_registro(reg, sistema["indice"])
        if len(problemas) == 0:
            registrar_ocorrencia(sistema, reg)
        else:
            sistema["invalidos"].append({"registro": reg, "problemas": problemas})

    # Historico simulado: cada mudanca de situacao vira um evento
    eventos = []
    for oc in sistema["lista"]:
        if oc["dia_analise"] is not None:
            eventos.append((oc["dia_analise"], oc["id"], "aberta", "em analise"))
        if oc["dia_conclusao"] is not None:
            eventos.append((oc["dia_conclusao"], oc["id"], "em analise", "concluida"))
    eventos.sort()
    for ev in eventos:
        empilhar_evento(sistema, ev[1], ev[2], ev[3], ev[0])
    return len(sistema["lista"])


def proximo_id(sistema):
    maior = 0
    for oc in sistema["lista"]:
        if oc["id"].isdigit() and int(oc["id"]) > maior:
            maior = int(oc["id"])
    for inv in sistema["invalidos"]:
        codigo = inv["registro"].get("id", "")
        if codigo.isdigit() and int(codigo) > maior:
            maior = int(codigo)
    return str(maior + 1).zfill(3)


# ----------------------------------------------------------------------
# Operacoes: cadastro, consulta, filtro, atualizacao
# ----------------------------------------------------------------------
def cadastrar_ocorrencia(sistema, bairro, categoria, descricao, local):
    """Valida e cadastra uma nova demanda. Devolve (sucesso, mensagem)."""
    texto_livre = descricao + " " + local + " " + bairro
    if contem_dado_pessoal(texto_livre):
        return False, "Cadastro recusado: o texto parece conter dado pessoal (e-mail ou número longo)."
    reg = {
        "id": proximo_id(sistema),
        "bairro": bairro.strip(),
        "categoria": categoria,
        "descricao": descricao.strip(),
        "local": local.strip(),
        "dia_abertura": str(sistema["dia_atual"]),
        "status": "aberta",
        "dia_analise": "",
        "dia_conclusao": "",
    }
    problemas = validar_registro(reg, sistema["indice"])
    if len(problemas) > 0:
        return False, "Cadastro recusado: " + "; ".join(problemas)
    oc = registrar_ocorrencia(sistema, reg)
    return True, "Ocorrência " + oc["id"] + " cadastrada com sucesso (situação: Aberta)."


def consultar_por_id(sistema, codigo):
    codigo = codigo.strip()
    if codigo.isdigit():
        codigo = codigo.zfill(3)
    if codigo in sistema["indice"]:
        return sistema["indice"][codigo]
    return None


def filtrar(sistema, categoria, status):
    """Filtra por categoria e/ou situacao ('' = qualquer)."""
    resultado = []
    for oc in sistema["lista"]:
        if (categoria == "" or oc["categoria"] == categoria) and \
           (status == "" or oc["status"] == status):
            resultado.append(oc)
    return resultado


def atualizar_status(sistema, codigo, novo):
    """Muda a situacao respeitando o fluxo e registra no historico (pilha)."""
    oc = consultar_por_id(sistema, codigo)
    novo = normalizar(novo)
    if oc is None:
        return False, "Ocorrência '" + codigo + "' não encontrada."
    if novo not in STATUS:
        return False, "Situação desconhecida: '" + novo + "'. Use: aberta, em análise ou concluída."
    atual = oc["status"]
    if novo == atual:
        return False, "A ocorrência " + oc["id"] + " já está em '" + STATUS[atual] + "'."
    if atual == "concluida" and not (novo == "concluida"):
        return False, "Ocorrência concluída não pode ser reaberta."
    if novo not in TRANSICOES[atual]:
        return False, "Mudança inválida: " + STATUS[atual] + " -> " + STATUS[novo] + \
            " (o fluxo é Aberta -> Em análise -> Concluída)."

    oc["status"] = novo
    if novo == "em analise":
        oc["dia_analise"] = sistema["dia_atual"]
        if oc["id"] in sistema["fila"]:
            sistema["fila"].remove(oc["id"])    # sai da fila
    elif novo == "concluida":
        oc["dia_conclusao"] = sistema["dia_atual"]
    empilhar_evento(sistema, oc["id"], atual, novo, sistema["dia_atual"])
    return True, "Ocorrência " + oc["id"] + ": " + STATUS[atual] + " -> " + STATUS[novo] + \
        " (dia " + str(sistema["dia_atual"]) + ")."


def analisar_proxima(sistema):
    """Atende a demanda mais antiga da fila (FIFO)."""
    if len(sistema["fila"]) == 0:
        return False, "Fila vazia: não há demandas aguardando análise."
    primeiro = sistema["fila"][0]
    return atualizar_status(sistema, primeiro, "em analise")


# ----------------------------------------------------------------------
# Indicadores
# ----------------------------------------------------------------------
def calcular_matriz(sistema):
    """Matriz (lista de listas): linhas = categorias, colunas = situacoes."""
    matriz = []
    for cat in CATEGORIAS:
        linha = []
        for st in STATUS:
            contador = 0
            for oc in sistema["lista"]:
                if oc["categoria"] == cat and oc["status"] == st:
                    contador = contador + 1
            linha.append(contador)
        matriz.append(linha)
    return matriz


def tempo_medio_conclusao(sistema):
    soma = 0
    quantidade = 0
    detalhes = []
    for oc in sistema["lista"]:
        if oc["status"] == "concluida" and oc["dia_conclusao"] is not None:
            dias = oc["dia_conclusao"] - oc["dia_abertura"]
            soma = soma + dias
            quantidade = quantidade + 1
            detalhes.append((oc["id"], dias))
    if quantidade == 0:
        return None, detalhes
    return soma / quantidade, detalhes


def mostrar_indicadores(sistema):
    total = len(sistema["lista"])
    print("\n=== INDICADORES ===")
    if total == 0:
        print("Nenhuma ocorrência cadastrada.")
        return
    matriz = calcular_matriz(sistema)
    nomes_cat = list(CATEGORIAS.keys())
    nomes_st = list(STATUS.keys())

    print("Dados de origem: " + str(total) + " ocorrências válidas na lista.")
    print("Fórmula: proporção (%) = (quantidade / total) * 100\n")

    # Matriz categoria x situacao
    print("Matriz categoria x situação:")
    cabecalho = "Categoria".ljust(16)
    for st in nomes_st:
        cabecalho = cabecalho + STATUS[st].ljust(12)
    print(cabecalho + "Total  %")
    totais_status = [0, 0, 0]
    maior_total = -1
    totais_cat = []
    for i in range(len(nomes_cat)):
        linha_txt = CATEGORIAS[nomes_cat[i]].ljust(16)
        soma_linha = 0
        for j in range(len(nomes_st)):
            linha_txt = linha_txt + str(matriz[i][j]).ljust(12)
            soma_linha = soma_linha + matriz[i][j]
            totais_status[j] = totais_status[j] + matriz[i][j]
        pct = soma_linha / total * 100
        print(linha_txt + str(soma_linha).ljust(7) + "{:.1f}%".format(pct))
        totais_cat.append(soma_linha)
        if soma_linha > maior_total:
            maior_total = soma_linha

    linha_txt = "TOTAL".ljust(16)
    for j in range(len(nomes_st)):
        linha_txt = linha_txt + str(totais_status[j]).ljust(12)
    print(linha_txt + str(total))

    print("\nProporção por situação:")
    for j in range(len(nomes_st)):
        pct = totais_status[j] / total * 100
        print("  " + STATUS[nomes_st[j]].ljust(12) + str(totais_status[j]) + " de " +
              str(total) + " = {:.1f}%".format(pct))

    # Indicadores adicionais
    pendentes = totais_status[0] + totais_status[1]
    pct_pend = pendentes / total * 100
    media, detalhes = tempo_medio_conclusao(sistema)
    print("\nPendências (abertas + em análise) = " + str(pendentes) +
          " ({:.1f}%)".format(pct_pend))
    if media is None:
        print("Tempo médio até a conclusão: sem ocorrências concluídas.")
    else:
        print("Tempo médio simulado até a conclusão = soma dos dias / concluídas")
        partes = []
        for item in detalhes:
            partes.append(item[0] + ":" + str(item[1]) + "d")
        print("  Origem: " + ", ".join(partes))
        print("  Resultado: {:.1f} dias".format(media))

    # Conclusao interpretada por regras
    lideres = []
    for i in range(len(nomes_cat)):
        if totais_cat[i] == maior_total:
            lideres.append(CATEGORIAS[nomes_cat[i]])
    if len(lideres) == 1:
        print("\nConclusão: a categoria com mais demandas é " + lideres[0] +
              " (" + str(maior_total) + " de " + str(total) + "). ", end="")
    else:
        print("\nConclusão: as categorias com mais demandas (empate) são " +
              " e ".join(lideres) + " (" + str(maior_total) + " de " + str(total) + " cada). ", end="")
    if pct_pend >= 50:
        print("Mais da metade das demandas segue pendente, o que sugere "
              "necessidade de ampliar a capacidade de atendimento.")
    elif pct_pend >= 25:
        print("Há uma parcela relevante de pendências, mas o atendimento avança.")
    else:
        print("A maior parte das demandas já foi tratada.")
    print("Aviso: dados fictícios; a conclusão vale só para este conjunto simulado.")


# ----------------------------------------------------------------------
# Exibicao
# ----------------------------------------------------------------------
def exibir_listagem(ocorrencias):
    if len(ocorrencias) == 0:
        print("Nenhuma ocorrência encontrada para esse filtro.")
        return
    print("\n" + "COD".ljust(5) + "CATEGORIA".ljust(16) + "LOCAL".ljust(38) + "STATUS")
    print("-" * 70)
    for oc in ocorrencias:
        print(oc["id"].ljust(5) + CATEGORIAS[oc["categoria"]].ljust(16) +
              oc["local"][:36].ljust(38) + STATUS[oc["status"]])
    print("Total: " + str(len(ocorrencias)))


def exibir_detalhe(oc):
    print("\nOcorrência " + oc["id"])
    print("  Bairro    : " + oc["bairro"])
    print("  Categoria : " + CATEGORIAS[oc["categoria"]])
    print("  Descrição : " + oc["descricao"])
    print("  Local     : " + oc["local"])
    print("  Aberta no dia " + str(oc["dia_abertura"]))
    print("  Situação  : " + STATUS[oc["status"]] + " (" + SIGNIFICADO_STATUS[oc["status"]] + ")")


def exibir_hierarquia(sistema):
    print("\n=== HIERARQUIA: bairro -> categoria -> ocorrências ===")
    for bairro in sistema["hierarquia"]:
        print(bairro)
        for cat in sistema["hierarquia"][bairro]:
            print("  " + CATEGORIAS[cat] + ": " + ", ".join(sistema["hierarquia"][bairro][cat]))


def exibir_eventos(sistema, quantidade):
    print("\n=== ÚLTIMOS EVENTOS (topo da pilha) ===")
    eventos = ultimos_eventos(sistema, quantidade)
    if len(eventos) == 0:
        print("Sem eventos registrados.")
    for ev in eventos:
        print("  dia " + str(ev[3]).ljust(3) + "ocorrência " + ev[0] + ": " +
              STATUS[ev[1]] + " -> " + STATUS[ev[2]])


def exibir_invalidos(sistema):
    print("\n=== REGISTROS REJEITADOS NA VALIDAÇÃO ===")
    if len(sistema["invalidos"]) == 0:
        print("Nenhum registro inválido.")
    for inv in sistema["invalidos"]:
        reg = inv["registro"]
        print("  Linha " + str(reg.get("_linha", "?")) + " (id " + reg.get("id", "?") + "): " +
              "; ".join(inv["problemas"]))


def exibir_resumo_status(sistema):
    contagem = {}
    for st in STATUS:
        contagem[st] = 0
    for oc in sistema["lista"]:
        contagem[oc["status"]] = contagem[oc["status"]] + 1
    print("Resumo: " + str(len(sistema["lista"])) + " ocorrências | " +
          str(contagem["aberta"]) + " abertas | " + str(contagem["em analise"]) +
          " em análise | " + str(contagem["concluida"]) + " concluídas | " +
          str(len(sistema["fila"])) + " na fila")


# ----------------------------------------------------------------------
# Entrada do usuario
# ----------------------------------------------------------------------
def pedir_categoria():
    print("Categorias: " + ", ".join(CATEGORIAS.values()))
    return normalizar(input("Categoria: "))


def pedir_status(opcional):
    texto = "Situação (aberta / em análise / concluída)"
    if opcional:
        texto = texto + " ou Enter para todas"
    return normalizar(input(texto + ": "))


def opcao_cadastrar(sistema):
    print("\n--- Novo cadastro (use apenas dados fictícios, sem dados pessoais) ---")
    bairro = input("Bairro: ")
    categoria = pedir_categoria()
    descricao = input("Descrição breve: ")
    local = input("Local genérico: ")
    ok, msg = cadastrar_ocorrencia(sistema, bairro, categoria, descricao, local)
    print(msg)


def opcao_consultar(sistema):
    codigo = input("Código da ocorrência (ex.: 014): ")
    oc = consultar_por_id(sistema, codigo)
    if oc is None:
        print("Ocorrência '" + codigo.strip() + "' não encontrada.")
    else:
        exibir_detalhe(oc)


def opcao_filtrar(sistema):
    categoria = ""
    status = ""
    entrada = normalizar(input("Filtrar por categoria? (Enter para todas): "))
    if entrada != "":
        if entrada in CATEGORIAS:
            categoria = entrada
        else:
            print("Categoria desconhecida: '" + entrada + "'.")
            return
    entrada = pedir_status(True)
    if entrada != "":
        if entrada in STATUS:
            status = entrada
        else:
            print("Situação desconhecida: '" + entrada + "'.")
            return
    exibir_listagem(filtrar(sistema, categoria, status))


def opcao_atualizar(sistema):
    codigo = input("Código da ocorrência: ")
    novo = pedir_status(False)
    ok, msg = atualizar_status(sistema, codigo, novo)
    print(msg)


def opcao_avancar_dia(sistema):
    entrada = input("Avançar quantos dias? (Enter = 1): ").strip()
    if entrada == "":
        entrada = "1"
    if entrada.isdigit() and int(entrada) > 0:
        sistema["dia_atual"] = sistema["dia_atual"] + int(entrada)
        print("Dia simulado atual: " + str(sistema["dia_atual"]))
    else:
        print("Valor inválido: informe um número inteiro positivo.")


def demonstracao(sistema):
    """Roteiro automatico (util para o video): cadastro, consulta, status e indicadores."""
    print("\n##### DEMONSTRAÇÃO AUTOMÁTICA #####")
    print("\n1) Cadastro válido:")
    ok, msg = cadastrar_ocorrencia(sistema, "Centro", "iluminacao",
                                   "Poste apagado na rua da escola", "Rua da Escola")
    print("   " + msg)
    print("\n2) Cadastro inválido (categoria vazia):")
    ok, msg = cadastrar_ocorrencia(sistema, "Centro", "", "Sem categoria", "Praça Central")
    print("   " + msg)
    print("\n3) Cadastro inválido (dado pessoal no texto):")
    ok, msg = cadastrar_ocorrencia(sistema, "Centro", "limpeza",
                                   "Falar com maria@email.com", "Praça Central")
    print("   " + msg)
    print("\n4) Consulta: ocorrências ABERTAS de ILUMINAÇÃO")
    exibir_listagem(filtrar(sistema, "iluminacao", "aberta"))
    print("\n5) Atualizar a ocorrência 016 para 'em análise':")
    ok, msg = atualizar_status(sistema, "016", "em análise")
    print("   " + msg)
    print("\n6) Tentativa inválida: reabrir a ocorrência 001 (concluída):")
    ok, msg = atualizar_status(sistema, "001", "aberta")
    print("   " + msg)
    print("\n7) Status desconhecido:")
    ok, msg = atualizar_status(sistema, "010", "arquivada")
    print("   " + msg)
    print("\n8) Código inexistente:")
    oc = consultar_por_id(sistema, "999")
    if oc is None:
        print("   Ocorrência '999' não encontrada.")
    print("\n9) Analisar a próxima da fila (FIFO):")
    ok, msg = analisar_proxima(sistema)
    print("   " + msg)
    exibir_eventos(sistema, 5)
    exibir_resumo_status(sistema)
    mostrar_indicadores(sistema)


# ----------------------------------------------------------------------
# Menu principal
# ----------------------------------------------------------------------
def exibir_menu():
    print("\n===== NEIGHBORHOOD ACTION DASHBOARD =====")
    print(" 1 - Listar ocorrências")
    print(" 2 - Consultar por código")
    print(" 3 - Filtrar por categoria e/ou situação")
    print(" 4 - Cadastrar nova ocorrência")
    print(" 5 - Atualizar situação")
    print(" 6 - Analisar próxima da fila")
    print(" 7 - Últimos eventos (pilha)")
    print(" 8 - Hierarquia bairro > categoria")
    print(" 9 - Indicadores")
    print("10 - Registros inválidos da carga")
    print("11 - Avançar dia simulado")
    print("12 - Demonstração automática")
    print(" 0 - Sair")


def main():
    sistema = criar_sistema()
    pasta = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(pasta, "..", "data", "dados.csv")
    if os.path.exists(caminho):
        qtd = carregar_dados(sistema, caminho)
        print("Dados carregados: " + str(qtd) + " ocorrências válidas, " +
              str(len(sistema["invalidos"])) + " rejeitada(s) na validação.")
    else:
        print("Arquivo data/dados.csv não encontrado. Iniciando sem dados.")

    opcao = ""
    while opcao != "0":
        exibir_menu()
        exibir_resumo_status(sistema)
        try:
            opcao = input("Escolha: ").strip()
        except EOFError:
            break
        if opcao == "1":
            exibir_listagem(sistema["lista"])
        elif opcao == "2":
            opcao_consultar(sistema)
        elif opcao == "3":
            opcao_filtrar(sistema)
        elif opcao == "4":
            opcao_cadastrar(sistema)
        elif opcao == "5":
            opcao_atualizar(sistema)
        elif opcao == "6":
            print(analisar_proxima(sistema)[1])
        elif opcao == "7":
            exibir_eventos(sistema, 5)
        elif opcao == "8":
            exibir_hierarquia(sistema)
        elif opcao == "9":
            mostrar_indicadores(sistema)
        elif opcao == "10":
            exibir_invalidos(sistema)
        elif opcao == "11":
            opcao_avancar_dia(sistema)
        elif opcao == "12":
            demonstracao(sistema)
        elif opcao == "0":
            print("Encerrando. Obrigado!")
        else:
            print("Opção inválida. Escolha um número do menu.")


if __name__ == "__main__":
    main()
