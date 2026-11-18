# Neighborhood Action Dashboard

**Global Solution 2026.2 – FIAP (CitizenTech)**

## 1. Autora (trabalho individual)

| Nome | RM |
|------|----|
| Maria Luiza Costa Araujo | [RM] |

## 2. Problema e público beneficiado

Bairros e comunidades enfrentam problemas cotidianos de infraestrutura e conservação (poste apagado, rampa quebrada, lixo acumulado, banco danificado). Os relatos ficam dispersos, as prioridades não são claras e o morador não consegue acompanhar o andamento.

O protótipo simula um **painel comunitário de ocorrências**, com três bairros fictícios (Centro, Jardim das Flores e Vila Nova). Ele permite registrar, consultar, atualizar e resumir demandas de **iluminação, acessibilidade, limpeza e conservação de espaços coletivos**.

**Público beneficiado:** moradores que querem acompanhar suas solicitações e equipes comunitárias que precisam organizar prioridades.

> Todos os dados são **fictícios**. Não há integração com prefeituras nem promessa de atendimento.

## 3. Como executar

Requisito: Python 3 (somente biblioteca padrão, sem pandas, numpy ou frameworks).

```bash
python src/sistema.py
```

O menu abre no terminal. A opção **12** roda uma demonstração automática.

## 4. Dados (`data/dados.csv`)

Arquivo CSV com separador `;` e 15 linhas de dados (14 válidas e 1 inválida de propósito).

| Campo | Obrigatório | Descrição |
|-------|:-----------:|-----------|
| id | sim | Código único (ex.: 014) |
| bairro | sim | Bairro fictício |
| categoria | sim | `iluminacao`, `acessibilidade`, `limpeza` ou `conservacao` |
| descricao | sim | Descrição breve (sem dados pessoais) |
| local | sim | Local genérico (ex.: Praça Central) |
| dia_abertura | sim | Dia simulado de abertura (número) |
| status | sim | `aberta`, `em analise` ou `concluida` |
| dia_analise | não* | Dia em que entrou em análise |
| dia_conclusao | não* | Dia da conclusão |

\* Obrigatórios conforme a situação (ver regras lógicas).

**Significado das situações:**
- **Aberta:** registrada, ainda na fila, ninguém examinou.
- **Em análise:** já foi examinada e está sendo avaliada.
- **Concluída:** problema tratado e caso encerrado.

**Pacote de dados:** 14 ocorrências válidas (5 abertas, 4 em análise, 5 concluídas), 14 mudanças de situação no histórico e o registro `015` sem categoria, que é rejeitado pela validação.

## 5. Estruturas de dados e justificativas

| Estrutura | Uso no sistema | Por quê |
|-----------|----------------|---------|
| **Lista** | Guarda todas as ocorrências | Permite percorrer, listar e filtrar com laços |
| **Fila (FIFO)** | Demandas ainda não examinadas, por ordem de registro | Quem registrou primeiro é atendido primeiro |
| **Pilha (LIFO)** | Histórico de mudanças de situação | O evento mais recente é o primeiro a ser consultado |
| **Dicionário** | `id -> ocorrência` | Acesso direto pelo código, sem percorrer a lista |
| **Hierarquia** (dicionários aninhados) | bairro → categoria → ids | Mostra onde se concentram os problemas de cada bairro |
| **Matriz** (lista de listas) | Quantidade por categoria × situação | Base dos indicadores e do resumo por situação |

## 6. Regras lógicas

- **Cadastro e validação:** `IF/ELIF/ELSE` verificam campos obrigatórios, categoria, situação, duplicidade e datas.
- **Fluxo de situação:** só é permitido `Aberta → Em análise → Concluída`. Concluída não reabre, e o sistema informa o motivo de cada recusa.
- **Privacidade:** o cadastro é recusado se o texto tiver `@` ou 8 ou mais dígitos (possível e-mail, telefone ou CPF).
- **Consultas:** busca por código e filtro por categoria e/ou situação.

**Expressões booleanas (AND, OR, NOT):**

```python
# 1) Filtro: categoria E situação (vazio = qualquer)
(categoria == "" or oc["categoria"] == categoria) and (status == "" or oc["status"] == status)

# 2) Validação de coerência: concluída exige as duas datas
status == "concluida" and (dia_analise == "" or dia_conclusao == "")

# 3) Atualização: concluída não pode ser reaberta
atual == "concluida" and not (novo == "concluida")
```

**Por que cada mensagem aparece:**
- Expressão 2 verdadeira: o registro é rejeitado, pois uma concluída precisa ter passado por análise e ter data de conclusão.
- Expressão 3 verdadeira: a mudança é bloqueada, porque um caso encerrado não volta a ser aberto.
- Código inexistente ou situação desconhecida: o sistema informa em vez de falhar.

## 7. Indicadores

| Indicador | Fórmula |
|-----------|---------|
| Total por categoria e por situação | contagem por laço, na matriz categoria × situação |
| Proporção (%) | `(quantidade / total) * 100` |
| Pendências | `abertas + em análise` |
| Tempo médio simulado até a conclusão | `soma(dia_conclusao - dia_abertura) / nº de concluídas` |

O sistema mostra os dados de origem, a fórmula e o resultado em tabela textual (opção **9**).

**Interpretação (conjunto simulado):** a Iluminação lidera em volume (4 de 14), cerca de 64% das demandas ainda estão pendentes e o tempo médio de conclusão é 5,0 dias. Isso sugere que a capacidade de atendimento é menor que a demanda.

## 8. Exemplo de uso (saída real)

```text
Dados carregados: 14 ocorrências válidas, 1 rejeitada(s) na validação.

1) Cadastro válido:
   Ocorrência 016 cadastrada com sucesso (situação: Aberta).
2) Cadastro inválido (categoria vazia):
   Cadastro recusado: campo obrigatório ausente: categoria
5) Atualizar a ocorrência 016 para 'em análise':
   Ocorrência 016: Aberta -> Em análise (dia 12).
6) Tentativa inválida: reabrir a ocorrência 001 (concluída):
   Ocorrência concluída não pode ser reaberta.
8) Código inexistente:
   Ocorrência '999' não encontrada.

Categoria       Aberta      Em análise  Concluída   Total  %
Iluminação      0           2           2           4      28.6%
Acessibilidade  1           1           1           3      21.4%
Limpeza         1           2           1           4      28.6%
Conservação     1           1           1           3      21.4%
```

## 9. Acessibilidade, inclusão e privacidade

- Interface textual simples, com mensagens claras e menu numerado.
- Rótulos com acentuação para leitura, e entradas aceitam com ou sem acento.
- Descrições curtas, com locais genéricos.
- Nenhum dado pessoal é armazenado, e o sistema bloqueia textos com e-mail ou números longos.
- Limitação: o terminal não atende todos os perfis, e uma versão futura poderia ter interface gráfica ou por voz.

## 10. Vídeo

[COLE AQUI O LINK DO YOUTUBE – NÃO LISTADO]

## 11. Conclusões, limitações e aprendizados

- **Conclusão:** estruturas simples (lista, fila, pilha, dicionário, matriz) resolvem um problema comunitário real quando bem escolhidas.
- **Limitações:** dados fictícios, sem persistência (alterações não voltam ao CSV), sem integração com órgãos públicos e sem autenticação.
- **Aprendizados:** validar a entrada antes de guardar, justificar a escolha da estrutura e interpretar números sem exagerar o que eles provam.
