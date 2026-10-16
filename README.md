# Financat

Aplicativo desktop para Windows para organizar contas a pagar, gastos fixos e recorrentes,
com visão mensal, funcionando offline. Dados em SQLite, no seu computador.

Vou ficar feliz se puderem contribuir

## Baixar e usar (Windows)

1. Acesse a página de [releases](https://github.com/machntoshh/financat/releases/latest) e baixe `Financat.exe`.
2. Dê dois cliques no arquivo. Não precisa instalar nem ter Python.
3. Como o app ainda não tem assinatura digital, o Windows pode mostrar "O Windows protegeu o seu PC".
   Clique em **Mais informações** e depois em **Executar assim mesmo**.
4. Confira a integridade com o arquivo `Financat.exe.sha256` da mesma release (opcional):

```bash
certutil -hashfile Financat.exe SHA256
```

Requisitos: Windows 10 ou 11 (64 bits). Tudo fica no seu computador; nenhuma conta é necessária.

## Como rodar durante o desenvolvimento

Requisitos: Python 3.11+ (testado com 3.14) e Windows.

```bash
python -m pip install -r requirements.txt
python main.py
```

## Testes

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
```

Os testes cobrem as regras (recorrência, status, pagamento, sem duplicatas, backup, CSV)
e um teste de fumaça da interface em modo offscreen.

## Gerar o executável (.exe)

Dê dois cliques em `build_exe.bat`, ou rode no terminal:

```bash
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconsole --onefile --clean --name Financat main.py
```

O arquivo sai em `dist\Financat.exe` e não precisa de Python instalado.

## Onde ficam os dados

- Banco: `%APPDATA%\OrganizadorFinanceiro\financas.db` (salvo a cada ação; nada fica só na memória).
- A pasta de dados mantém o nome antigo para não perder os dados já existentes.
- Erros inesperados: `%APPDATA%\OrganizadorFinanceiro\erros.log`.
- Cópias de segurança automáticas feitas antes de uma restauração: mesma pasta, `antes_da_restauracao_*.db`.

## Como usar

- **Mês**: dashboard principal. Use ‹ e › para navegar entre meses; “Hoje” volta ao mês atual.
  Os quatro indicadores mostram total, já pago, pendente e o próximo vencimento.
  Use os filtros para ver pendentes, pagas, vencidas, fixos ou recorrentes.
- **Marcar como paga**: um clique na linha. “Desfazer” volta a conta para pendente
  (o gatinho só comemora na primeira marcação).
- **+ Adicionar conta**: na barra lateral ou no dashboard. Tipo *Única*, *Fixa* ou *Recorrente*.
- **Converter em fixa ou recorrente**: abra a conta com *Editar* e troque o *Tipo*.
  O pagamento já feito é preservado.
- **Alterar o valor só de um mês**: abra a conta daquele mês e altere o valor.
  Os demais meses não mudam.
- **Editar fixas e recorrentes**: nas abas *Gastos fixos* / *Gastos recorrentes*.
  Mudanças valem a partir do mês atual; contas já pagas não mudam.
- **Exportar CSV**, **Fazer backup** e **Restaurar backup**: na parte de baixo da barra lateral.
  O CSV usa `;` como separador e abre direto no Excel em português.

## Estrutura

```
main.py                  ponto de entrada (janela, tratamento de erros)
financas/                regras de negócio e persistência (sem Qt)
  models.py              Expense, Series e status
  recurrence.py          datas de vencimento (semanal, mensal, anual)
  formatting.py          valores em R$ e textos como "Vence amanhã"
  db.py                  esquema SQLite, backup e restauração
  repository.py          todo o SQL
  services.py            FinanceService: a única fachada usada pela interface
ui/                      interface PySide6 (sem regras de negócio)
  main_window.py         barra lateral + páginas
  dashboard.py           visão mensal
  bills_page.py          Contas a pagar (avulsas)
  series_page.py         Gastos fixos e recorrentes
  expense_dialog.py      formulário de conta/série
  mascot.py + sprites.py gatinho pixel art (estados idle, happy, returning)
  theme.py               cores e QSS
tests/                   testes unitários e de interface
```

## Decisões de modelo

- Fixas e recorrentes são **séries**. As contas de cada mês são criadas sob demanda,
  com chave única `(série, data)`: abrir o mês de novo nunca duplica uma cobrança.
- Excluir uma ocorrência de série só a remove daquele mês (fica registrada como ignorada).
- Excluir uma série remove as contas não pagas; as pagas viram contas avulsas no histórico.
- “Vencida” é calculada: conta não paga com vencimento anterior a hoje.

## Mascote

O gatinho é desenhado em código a partir de uma matriz 16×16 (`ui/sprites.py`), sem arquivos
externos, então funciona offline e entra no `.exe`. Ele comemora só quando o pagamento é gravado
no banco. Se o Windows estiver com “Mostrar animações” desligado, o movimento é suprimido
(a cor continua mudando, sem efeitos de movimento).

## Limitações da primeira versão

- Não há gráficos, relatórios por categoria nem múltiplas contas bancárias (de propósito).
- Para mudar a frequência ou a data de início de uma série, exclua a série e crie outra.
- A data de uma ocorrência de série não pode ser alterada individualmente; altere o valor
  ou exclua aquela ocorrência.
- O executável não é assinado digitalmente, então o Windows SmartScreen pode pedir confirmação na
  primeira execução.
