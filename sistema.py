# -*- coding: utf-8 -*-
"""
Neighborhood Action Dashboard - Global Solution 2026.2 (FIAP)

Prototipo em terminal para cadastrar, consultar e acompanhar ocorrencias
comunitarias (iluminacao, acessibilidade, limpeza e conservacao).
Todos os dados sao FICTICIOS. Nao ha integracao com orgaos publicos.

Executar:  python src/sistema.py

Estruturas usadas (e por que):
  - LISTA      : guarda todas as ocorrencias e permite percorre-las.
  - FILA       : demandas ainda nao examinadas, na ordem de registro (FIFO).
  - PILHA      : ultimos eventos de status (LIFO: o mais recente sai primeiro).
  - DICIONARIO : acesso direto a uma ocorrencia pelo identificador.
  - HIERARQUIA : bairro -> categoria -> ocorrencias (dicionarios aninhados).
  - MATRIZ     : lista de listas com quantidade por categoria x situacao.
"""

import os

# Valores padronizados (identificadores em minusculo e sem acento)
CATEGORIAS = {
    "iluminacao": "Iluminação",
    "acessibilidade": "Acessibilidade",
    "limpeza": "Limpeza",
    "conservacao": "Conservação",
}

# Situacoes e o significado de cada uma
STATUS = {"aberta": "Aberta", "em analise": "Em análise", "concluida": "Concluída"}
SIGNIFICADO = {
    "aberta": "registrada e ainda na fila, ninguém examinou",
    "em analise": "já foi examinada e está sendo avaliada",
    "concluida": "problema tratado e caso encerrado",
}

# Fluxo permitido: a situacao so avanca, nunca volta
TRANSICOES = {
    "aberta": ["em analise"],
    "em analise": ["concluida"],
    "concluida": [],
}

OBRIGATORIOS = ["id", "bairro", "categoria", "descricao", "local", "dia_abertura", "status"]


# ----------------------------------------------------------------------
# Utilitarios
# ----------------------------------------------------------------------
def normalizar(texto):
    """Minusculo e sem acento: 'Em Análise' -> 'em analise'."""
    texto = texto.strip().lower()
    for com, sem in [("á", "a"), ("à", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("ê", "e"),
                     ("í", "i"), ("ó", "o"), ("õ", "o"), ("ô", "o"), ("ú", "u"), ("ç", "c")]:
        texto = texto.replace(com, sem)
    return texto


def contem_dado_pessoal(texto):
    """Privacidade: recusa e-mail (@) ou 8+ digitos (telefone/CPF)."""
    digitos = 0
    for letra in texto:
        if letra.isdigit():
            digitos = digitos + 1
    return ("@" in texto) or (digitos >= 8)


def criar_sistema():
    return {
        "lista": [],        # lista de ocorrencias (cada uma e um dicionario)
        "indice": {},       # dicionario: id -> ocorrencia
        "fila": [],         # fila de ids ainda nao examinados
        "pilha": [],        # pilha de eventos (id, de, para, dia)
        "hierarquia": {},   # bairro -> categoria -> [ids]
        "invalidos": [],    # registros rejeitados na carga
        "dia_atual": 1,     # relogio simulado
    }


# ----------------------------------------------------------------------
# Validacao e carga
# ----------------------------------------------------------------------
def validar_registro(reg, indice):
    """Devolve a lista de problemas (lista vazia = registro valido)."""
    problemas = []

    # Regra 1: campos obrigatorios nao podem faltar
    for campo in OBRIGATORIOS:
        if reg.get(campo, "") == "":
            problemas.append("campo obrigatório ausente: " + campo)
    if len(problemas) > 0:
        return problemas

    status = normalizar(reg["status"])
    dia_analise = reg.get("dia_analise", "")
    dia_conclusao = reg.get("dia_conclusao", "")

    # Regra 2: categoria e situacao precisam ser valores conhecidos
    if normalizar(reg["categoria"]) not in CATEGORIAS:
        problemas.append("categoria desconhecida: " + reg["categoria"])
    if status not in STATUS:
        problemas.append("situação desconhecida: " + reg["status"])

    # Regra 3: identificador numerico e unico
    if not reg["id"].isdigit():
        problemas.append("identificador deve ser numérico: " + reg["id"])
    if reg["id"] in indice:
        problemas.append("identificador duplicado: " + reg["id"])

    # Regra 4: datas simuladas devem ser numeros
    for dia in [reg["dia_abertura"], dia_analise, dia_conclusao]:
        if dia != "" and not dia.isdigit():
            problemas.append("data simulada inválida: " + dia)

    # Regra 5: concluida exige as duas datas (usa AND e OR)
    if status == "concluida" and (dia_analise == "" or dia_conclusao == ""):
        problemas.append("ocorrência concluída sem dia de análise/conclusão")
    return problemas


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
        "dia_analise": None,
        "dia_conclusao": None,
    }
    if reg.get("dia_analise", "") != "":
        oc["dia_analise"] = int(reg["dia_analise"])
    if reg.get("dia_conclusao", "") != "":
        oc["dia_conclusao"] = int(reg["dia_conclusao"])

    sistema["lista"].append(oc)                      # lista
    sistema["indice"][oc["id"]] = oc                 # dicionario
    h = sistema["hierarquia"]                        # hierarquia
    if oc["bairro"] not in h:
        h[oc["bairro"]] = {}
    if oc["categoria"] not in h[oc["bairro"]]:
        h[oc["bairro"]][oc["categoria"]] = []
    h[oc["bairro"]][oc["categoria"]].append(oc["id"])
    if oc["status"] == "aberta":                     # fila
        sistema["fila"].append(oc["id"])
    sistema["dia_atual"] = max(sistema["dia_atual"], oc["dia_abertura"],
                               oc["dia_analise"] or 0, oc["dia_conclusao"] or 0)
    return oc


def carregar_dados(sistema, caminho):
    """Le o CSV (separador ';'), separa validos de invalidos e monta o historico."""
    arquivo = open(caminho, "r", encoding="utf-8-sig")
    linhas = arquivo.readlines()
    arquivo.close()
    campos = linhas[0].strip().split(";")
    for numero in range(1, len(linhas)):
        if linhas[numero].strip() == "":
            continue
        partes = linhas[numero].strip().split(";")
        reg = {}
        for i in range(len(campos)):
            if i < len(partes):
                reg[campos[i]] = partes[i].strip()
            else:
                reg[campos[i]] = ""
        reg["_linha"] = numero + 1
        problemas = validar_registro(reg, sistema["indice"])
        if len(problemas) == 0:
            registrar_ocorrencia(sistema, reg)
        else:
            sistema["invalidos"].append({"registro": reg, "problemas": problemas})

    # Historico simulado: cada mudanca de situacao vira um evento na pilha
    eventos = []
    for oc in sistema["lista"]:
        if oc["dia_analise"] is not None:
            eventos.append((oc["dia_analise"], oc["id"], "aberta", "em analise"))
        if oc["dia_conclusao"] is not None:
            eventos.append((oc["dia_conclusao"], oc["id"], "em analise", "concluida"))
    eventos.sort()
    for dia, id_oc, de, para in eventos:
        sistema["pilha"].append((id_oc, de, para, dia))
    return len(sistema["lista"])


# ----------------------------------------------------------------------
# Operacoes: cadastro, consulta, filtro, atualizacao
# ----------------------------------------------------------------------
def proximo_id(sistema):
    maior = 0
    for oc in sistema["lista"]:
        if int(oc["id"]) > maior:
            maior = int(oc["id"])
    for inv in sistema["invalidos"]:
        if inv["registro"]["id"].isdigit() and int(inv["registro"]["id"]) > maior:
            maior = int(inv["registro"]["id"])
    return str(maior + 1).zfill(3)


def cadastrar_ocorrencia(sistema, bairro, categoria, descricao, local):
    """Valida e cadastra uma nova demanda. Devolve (sucesso, mensagem)."""
    if contem_dado_pessoal(bairro + " " + descricao + " " + local):
        return False, "Cadastro recusado: o texto parece conter dado pessoal (e-mail ou número longo)."
    reg = {
        "id": proximo_id(sistema), "bairro": bairro.strip(), "categoria": categoria,
        "descricao": descricao.strip(), "local": local.strip(),
        "dia_abertura": str(sistema["dia_atual"]), "status": "aberta",
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
        sistema["fila"].remove(oc["id"])             # sai da fila
    else:
        oc["dia_conclusao"] = sistema["dia_atual"]
    sistema["pilha"].append((oc["id"], atual, novo, sistema["dia_atual"]))   # empilha
    return True, "Ocorrência " + oc["id"] + ": " + STATUS[atual] + " -> " + STATUS[novo] + \
        " (dia " + str(sistema["dia_atual"]) + ")."


def analisar_proxima(sistema):
    """Atende a demanda mais antiga da fila (FIFO)."""
    if len(sistema["fila"]) == 0:
        return False, "Fila vazia: não há demandas aguardando análise."
    return atualizar_status(sistema, sistema["fila"][0], "em analise")


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


def mostrar_indicadores(sistema):
    total = len(sistema["lista"])
    print("\n=== INDICADORES ===")
    if total == 0:
        print("Nenhuma ocorrência cadastrada.")
        return

    matriz = calcular_matriz(sistema)
    nomes_cat = list(CATEGORIAS.values())
    nomes_st = list(STATUS.values())
    totais_cat = []                 # total de cada linha (categoria)
    totais_status = [0, 0, 0]       # total de cada coluna (situação)
    for linha in matriz:
        totais_cat.append(sum(linha))
        for j in range(3):
            totais_status[j] = totais_status[j] + linha[j]

    print("Dados de origem: " + str(total) + " ocorrências válidas na lista.")
    print("Fórmula: proporção (%) = (quantidade / total) * 100\n")

    # Matriz categoria x situacao, com totais e proporcao por categoria
    print("Matriz categoria x situação:")
    texto = "Categoria".ljust(16)
    for nome in nomes_st:
        texto = texto + nome.ljust(12)
    print(texto + "Total  %")
    for i in range(4):
        texto = nomes_cat[i].ljust(16)
        for valor in matriz[i]:
            texto = texto + str(valor).ljust(12)
        print(texto + str(totais_cat[i]).ljust(7) + "{:.1f}%".format(totais_cat[i] / total * 100))
    texto = "TOTAL".ljust(16)
    for valor in totais_status:
        texto = texto + str(valor).ljust(12)
    print(texto + str(total))

    # Proporcao por situacao
    print("\nProporção por situação:")
    for j in range(3):
        print("  " + nomes_st[j].ljust(12) + str(totais_status[j]) + " de " + str(total) +
              " = {:.1f}%".format(totais_status[j] / total * 100))

    # Pendencias
    pendentes = totais_status[0] + totais_status[1]
    pct_pend = pendentes / total * 100
    print("\nPendências (abertas + em análise) = " + str(pendentes) + " ({:.1f}%)".format(pct_pend))

    # Tempo medio ate a conclusao
    soma = 0
    origem = []
    for oc in sistema["lista"]:
        if oc["status"] == "concluida":
            dias = oc["dia_conclusao"] - oc["dia_abertura"]
            soma = soma + dias
            origem.append(oc["id"] + ":" + str(dias) + "d")
    if len(origem) == 0:
        print("Tempo médio até a conclusão: sem ocorrências concluídas.")
    else:
        print("Tempo médio simulado até a conclusão = soma dos dias / concluídas")
        print("  Origem: " + ", ".join(origem))
        print("  Resultado: {:.1f} dias".format(soma / len(origem)))

    # Conclusao interpretada (se houver empate, cita as categorias empatadas)
    maior = max(totais_cat)
    lideres = []
    for i in range(4):
        if totais_cat[i] == maior:
            lideres.append(nomes_cat[i])
    if len(lideres) == 1:
        print("\nConclusão: a categoria com mais demandas é " + lideres[0] +
              " (" + str(maior) + " de " + str(total) + "). ", end="")
    else:
        print("\nConclusão: as categorias com mais demandas (empate) são " + " e ".join(lideres) +
              " (" + str(maior) + " de " + str(total) + " cada). ", end="")
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
def mostrar_lista(ocorrencias):
    if len(ocorrencias) == 0:
        print("Nenhuma ocorrência encontrada para esse filtro.")
        return
    print("\n" + "COD".ljust(5) + "CATEGORIA".ljust(16) + "LOCAL".ljust(38) + "STATUS")
    print("-" * 70)
    for oc in ocorrencias:
        print(oc["id"].ljust(5) + CATEGORIAS[oc["categoria"]].ljust(16) +
              oc["local"][:36].ljust(38) + STATUS[oc["status"]])
    print("Total: " + str(len(ocorrencias)))


def mostrar_detalhe(oc):
    print("\nOcorrência " + oc["id"])
    print("  Bairro    : " + oc["bairro"])
    print("  Categoria : " + CATEGORIAS[oc["categoria"]])
    print("  Descrição : " + oc["descricao"])
    print("  Local     : " + oc["local"])
    print("  Aberta no dia " + str(oc["dia_abertura"]))
    print("  Situação  : " + STATUS[oc["status"]] + " (" + SIGNIFICADO[oc["status"]] + ")")


def mostrar_hierarquia(sistema):
    print("\n=== HIERARQUIA: bairro -> categoria -> ocorrências ===")
    for bairro in sistema["hierarquia"]:
        print(bairro)
        for cat in sistema["hierarquia"][bairro]:
            print("  " + CATEGORIAS[cat] + ": " + ", ".join(sistema["hierarquia"][bairro][cat]))


def mostrar_eventos(sistema, quantidade):
    """Le a pilha do topo para a base (evento mais recente primeiro)."""
    print("\n=== ÚLTIMOS EVENTOS (topo da pilha) ===")
    if len(sistema["pilha"]) == 0:
        print("Sem eventos registrados.")
    posicao = len(sistema["pilha"]) - 1
    mostrados = 0
    while posicao >= 0 and mostrados < quantidade:
        id_oc, de, para, dia = sistema["pilha"][posicao]
        print("  dia " + str(dia).ljust(3) + "ocorrência " + id_oc + ": " + STATUS[de] + " -> " + STATUS[para])
        posicao = posicao - 1
        mostrados = mostrados + 1


def mostrar_invalidos(sistema):
    print("\n=== REGISTROS REJEITADOS NA VALIDAÇÃO ===")
    if len(sistema["invalidos"]) == 0:
        print("Nenhum registro inválido.")
    for inv in sistema["invalidos"]:
        reg = inv["registro"]
        print("  Linha " + str(reg["_linha"]) + " (id " + reg["id"] + "): " + "; ".join(inv["problemas"]))


def mostrar_resumo(sistema):
    contagem = {"aberta": 0, "em analise": 0, "concluida": 0}
    for oc in sistema["lista"]:
        contagem[oc["status"]] = contagem[oc["status"]] + 1
    print("Resumo: " + str(len(sistema["lista"])) + " ocorrências | " + str(contagem["aberta"]) +
          " abertas | " + str(contagem["em analise"]) + " em análise | " + str(contagem["concluida"]) +
          " concluídas | " + str(len(sistema["fila"])) + " na fila")


# ----------------------------------------------------------------------
# Demonstracao automatica (util para o video)
# ----------------------------------------------------------------------
def passo(titulo, mensagem):
    print("\n" + titulo)
    print("   " + mensagem)


def demonstracao(sistema):
    print("\n##### DEMONSTRAÇÃO AUTOMÁTICA #####")
    passo("1) Cadastro válido:", cadastrar_ocorrencia(
        sistema, "Centro", "iluminacao", "Poste apagado na rua da escola", "Rua da Escola")[1])
    passo("2) Cadastro inválido (categoria vazia):", cadastrar_ocorrencia(
        sistema, "Centro", "", "Sem categoria", "Praça Central")[1])
    passo("3) Cadastro inválido (dado pessoal no texto):", cadastrar_ocorrencia(
        sistema, "Centro", "limpeza", "Falar com maria@email.com", "Praça Central")[1])
    print("\n4) Consulta: ocorrências ABERTAS de ILUMINAÇÃO")
    mostrar_lista(filtrar(sistema, "iluminacao", "aberta"))
    passo("5) Atualizar a ocorrência 016 para 'em análise':", atualizar_status(sistema, "016", "em análise")[1])
    passo("6) Tentativa inválida: reabrir a ocorrência 001 (concluída):", atualizar_status(sistema, "001", "aberta")[1])
    passo("7) Status desconhecido:", atualizar_status(sistema, "010", "arquivada")[1])
    if consultar_por_id(sistema, "999") is None:
        passo("8) Código inexistente:", "Ocorrência '999' não encontrada.")
    passo("9) Analisar a próxima da fila (FIFO):", analisar_proxima(sistema)[1])
    mostrar_eventos(sistema, 5)
    mostrar_resumo(sistema)
    mostrar_indicadores(sistema)


# ----------------------------------------------------------------------
# Menu principal
# ----------------------------------------------------------------------
MENU = """
===== NEIGHBORHOOD ACTION DASHBOARD =====
 1 - Listar ocorrências
 2 - Consultar por código
 3 - Filtrar por categoria e/ou situação
 4 - Cadastrar nova ocorrência
 5 - Atualizar situação
 6 - Analisar próxima da fila
 7 - Últimos eventos (pilha)
 8 - Hierarquia bairro > categoria
 9 - Indicadores
10 - Registros inválidos da carga
11 - Avançar dia simulado
12 - Demonstração automática
 0 - Sair"""


def main():
    sistema = criar_sistema()
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "dados.csv")
    if os.path.exists(caminho):
        qtd = carregar_dados(sistema, caminho)
        print("Dados carregados: " + str(qtd) + " ocorrências válidas, " +
              str(len(sistema["invalidos"])) + " rejeitada(s) na validação.")
    else:
        print("Arquivo de dados não encontrado em: " + os.path.abspath(caminho))
        print("Dica: extraia o ZIP inteiro (ou clone o repositório) para que a pasta")
        print("'data' fique ao lado da pasta 'src'. Iniciando sem dados.")

    opcao = ""
    while opcao != "0":
        print(MENU)
        mostrar_resumo(sistema)
        try:
            opcao = input("Escolha: ").strip()
        except EOFError:
            break

        if opcao == "1":
            mostrar_lista(sistema["lista"])
        elif opcao == "2":
            codigo = input("Código da ocorrência (ex.: 014): ")
            oc = consultar_por_id(sistema, codigo)
            if oc is None:
                print("Ocorrência '" + codigo.strip() + "' não encontrada.")
            else:
                mostrar_detalhe(oc)
        elif opcao == "3":
            cat = normalizar(input("Filtrar por categoria? (Enter para todas): "))
            st = normalizar(input("Situação (aberta / em análise / concluída) ou Enter para todas: "))
            if cat != "" and cat not in CATEGORIAS:
                print("Categoria desconhecida: '" + cat + "'.")
            elif st != "" and st not in STATUS:
                print("Situação desconhecida: '" + st + "'.")
            else:
                mostrar_lista(filtrar(sistema, cat, st))
        elif opcao == "4":
            print("\n--- Novo cadastro (use apenas dados fictícios, sem dados pessoais) ---")
            bairro = input("Bairro: ")
            print("Categorias: " + ", ".join(CATEGORIAS.values()))
            categoria = normalizar(input("Categoria: "))
            descricao = input("Descrição breve: ")
            local = input("Local genérico: ")
            print(cadastrar_ocorrencia(sistema, bairro, categoria, descricao, local)[1])
        elif opcao == "5":
            codigo = input("Código da ocorrência: ")
            novo = input("Situação (aberta / em análise / concluída): ")
            print(atualizar_status(sistema, codigo, novo)[1])
        elif opcao == "6":
            print(analisar_proxima(sistema)[1])
        elif opcao == "7":
            mostrar_eventos(sistema, 5)
        elif opcao == "8":
            mostrar_hierarquia(sistema)
        elif opcao == "9":
            mostrar_indicadores(sistema)
        elif opcao == "10":
            mostrar_invalidos(sistema)
        elif opcao == "11":
            dias = input("Avançar quantos dias? (Enter = 1): ").strip()
            if dias == "":
                dias = "1"
            if dias.isdigit() and int(dias) > 0:
                sistema["dia_atual"] = sistema["dia_atual"] + int(dias)
                print("Dia simulado atual: " + str(sistema["dia_atual"]))
            else:
                print("Valor inválido: informe um número inteiro positivo.")
        elif opcao == "12":
            demonstracao(sistema)
        elif opcao == "0":
            print("Encerrando. Obrigado!")
        else:
            print("Opção inválida. Escolha um número do menu.")


if __name__ == "__main__":
    main()
