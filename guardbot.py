import logging
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import re

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Token do seu bot
TOKEN = "7948125593:AAEpuhx-uGGv-y4p_AN4Z9Xw6OceaSJ3nvM"

# Configurações fixas
SALARIO_FIXO = {
    "valor": 680,
    "dia": 20,
    "descricao": "Salário fixo"
}

FRELA_FIXO = {
    "valor": 780,
    "dia_util": 5,
    "descricao": "Freela (5º dia útil)"
}

DESPESAS_FIXAS = [
    {"valor": 500, "dia": 20, "descricao": "Aluguel"},
    {"valor": 150, "dia": 1, "descricao": "Vale Alimentação"},
    {"valor": 30, "dia": 10, "descricao": "Internet"}
]

# Inicialização do banco de dados
def init_db():
    conn = sqlite3.connect('guardbot.db')
    c = conn.cursor()
    
    # Tabela de transações
    c.execute('''CREATE TABLE IF NOT EXISTS transacoes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data TEXT NOT NULL,
                  tipo TEXT NOT NULL,
                  valor REAL NOT NULL,
                  descricao TEXT,
                  categoria TEXT)''')
    
    # Tabela de saldos
    c.execute('''CREATE TABLE IF NOT EXISTS saldos
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  data TEXT NOT NULL,
                  saldo REAL NOT NULL)''')
    
    # Tabela de configurações
    c.execute('''CREATE TABLE IF NOT EXISTS configuracoes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ultima_atualizacao TEXT)''')
    
    conn.commit()
    conn.close()

# Funções de banco de dados
def registrar_transacao(data, tipo, valor, descricao, categoria=None):
    conn = sqlite3.connect('guardbot.db')
    c = conn.cursor()
    c.execute("INSERT INTO transacoes (data, tipo, valor, descricao, categoria) VALUES (?, ?, ?, ?, ?)",
              (data, tipo, valor, descricao, categoria))
    conn.commit()
    conn.close()
    atualizar_saldo()

def obter_ultimas_transacoes(limite=5):
    conn = sqlite3.connect('guardbot.db')
    c = conn.cursor()
    c.execute("SELECT data, tipo, valor, descricao FROM transacoes ORDER BY id DESC LIMIT ?", (limite,))
    transacoes = c.fetchall()
    conn.close()
    return transacoes

def calcular_saldo_atual():
    conn = sqlite3.connect('guardbot.db')
    c = conn.cursor()
    c.execute("SELECT SUM(CASE WHEN tipo='receita' THEN valor ELSE -valor END) FROM transacoes")
    saldo = c.fetchone()[0] or 0
    conn.close()
    return saldo

def atualizar_saldo():
    saldo = calcular_saldo_atual()
    data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect('guardbot.db')
    c = conn.cursor()
    c.execute("INSERT INTO saldos (data, saldo) VALUES (?, ?)", (data, saldo))
    conn.commit()
    conn.close()
    return saldo

def verificar_transacoes_do_dia():
    hoje = datetime.now()
    dia = hoje.day
    
    # Verificar se é dia de salário
    if dia == SALARIO_FIXO["dia"]:
        registrar_transacao(
            hoje.strftime("%Y-%m-%d %H:%M:%S"),
            "receita",
            SALARIO_FIXO["valor"],
            SALARIO_FIXO["descricao"],
            "Salário"
        )
    
    # Verificar se é o 5º dia útil (para o freela)
    if eh_quinto_dia_util(hoje):
        registrar_transacao(
            hoje.strftime("%Y-%m-%d %H:%M:%S"),
            "receita",
            FRELA_FIXO["valor"],
            FRELA_FIXO["descricao"],
            "Freela"
        )
    
    # Verificar despesas fixas
    for despesa in DESPESAS_FIXAS:
        if dia == despesa["dia"]:
            registrar_transacao(
                hoje.strftime("%Y-%m-%d %H:%M:%S"),
                "despesa",
                despesa["valor"],
                despesa["descricao"],
                "Despesa Fixa"
            )

def eh_quinto_dia_util(data):
    # Verifica se é o quinto dia útil do mês
    if data.day < 5:
        return False
        
    dia_util_count = 0
    temp_date = datetime(data.year, data.month, 1)
    
    while temp_date.month == data.month:
        if temp_date.weekday() < 5:  # Segunda a sexta
            dia_util_count += 1
            if dia_util_count == 5 and temp_date.day == data.day:
                return True
        temp_date += timedelta(days=1)
    
    return False

# Handlers de comandos
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_html(
        rf"Olá {user.mention_html()}! Eu sou seu GuardBot 🤖💸",
        reply_markup=ReplyKeyboardMarkup([["Saldo", "Extrato", "Resumo"]], resize_keyboard=True)
    )
    await update.message.reply_text(
        "Como posso ajudar?\n\n"
        "📌 Exemplos de como registrar:\n"
        "• Gastos: 150$\n"
        "• Motivo: Almoço\n"
        "• +saldo: 134$\n"
        "• -saldo: 100$\n\n"
        "Ou use os botões abaixo para ações rápidas!",
        reply_markup=ReplyKeyboardMarkup([["Saldo", "Extrato", "Resumo"]], resize_keyboard=True)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
💡 *Como usar o GuardBot*:

📥 *Para adicionar dinheiro:*
`+saldo: 100$` ou `+100$`

📤 *Para registrar gastos:*
`Gastos: 50$` ou `-50$`
`Motivo: Almoço`

📋 *Para ver informações:*
• /saldo - Mostra seu saldo atual
• /extrato - Mostra últimas transações
• /resumo - Mostra resumo do mês

💸 *Suas despesas fixas:*
• Todo dia 1: R$ 150 (Alimentação)
• Todo dia 10: R$ 30 (Internet)
• Todo dia 20: R$ 500 (Aluguel) + R$ 680 (Salário)
• 5º dia útil: R$ 780 (Freela)

*Dica:* Você pode usar os botões rápidos abaixo!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saldo_atual = calcular_saldo_atual()
    await update.message.reply_text(f"💎 *Saldo Atual:* R$ {saldo_atual:.2f}", parse_mode='Markdown')

async def extrato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    transacoes = obter_ultimas_transacoes(10)
    if not transacoes:
        await update.message.reply_text("📝 Nenhuma transação registrada ainda.")
        return
    
    extrato_text = "📋 *Últimas Transações:*\n\n"
    for data, tipo, valor, descricao in reversed(transacoes):
        data_formatada = datetime.strptime(data, "%Y-%m-%d %H:%M:%S").strftime("%d/%m %H:%M")
        sinal = "➕" if tipo == "receita" else "➖"
        extrato_text += f"{sinal} *R$ {valor:.2f}* - {descricao}\n   _{data_formatada}_\n\n"
    
    await update.message.reply_text(extrato_text, parse_mode='Markdown')

async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('guardbot.db')
    c = conn.cursor()
    
    # Calcular totais do mês atual
    mes_ano = datetime.now().strftime("%Y-%m")
    c.execute("SELECT SUM(valor) FROM transacoes WHERE tipo='receita' AND data LIKE ?", (f"{mes_ano}%",))
    total_receitas = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(valor) FROM transacoes WHERE tipo='despesa' AND data LIKE ?", (f"{mes_ano}%",))
    total_despesas = c.fetchone()[0] or 0
    
    saldo_mes = total_receitas - total_despesas
    conn.close()
    
    resumo_text = (
        f"📊 *Resumo Financeiro de {datetime.now().strftime('%B/%Y')}*\n\n"
        f"💰 *Total de Entradas:* R$ {total_receitas:.2f}\n"
        f"💸 *Total de Saídas:* R$ {total_despesas:.2f}\n"
        f"💎 *Saldo do Mês:* R$ {saldo_mes:.2f}\n\n"
    )
    
    if saldo_mes > 0:
        resumo_text += "✅ *Situação:* Positiva - Você está dentro do orçamento!"
    else:
        resumo_text += "⚠️ *Situação:* Negativa - Atenção aos gastos!"
    
    await update.message.reply_text(resumo_text, parse_mode='Markdown')

# Handler de mensagens regulares
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()
    user = update.effective_user
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Verificar transações do dia sempre que receber uma mensagem
    verificar_transacoes_do_dia()
    
    # Padrões de regex para detectar comandos
    padrao_gasto = re.compile(r'(?i)(gastos?|despesa|gastei|paguei)[:\s]*[\$]?(\d+[.,]?\d*)')
    padrao_adicionar = re.compile(r'(?i)(\+saldo|adicionar|recebi|entrou)[:\s]*[\$]?(\d+[.,]?\d*)')
    padrao_remover = re.compile(r'(?i)(\-saldo|retirar|saquei|gastei)[:\s]*[\$]?(\d+[.,]?\d*)')
    padrao_motivo = re.compile(r'(?i)(motivo|descricao|por|para)[:\s]*(.+)')
    padrao_valor_simples = re.compile(r'^[\+\-]?\$?\s*(\d+[.,]?\d*)$')
    
    # Verificar se é um comando de gasto
    match = padrao_gasto.search(message_text)
    if match:
        valor = float(match.group(2).replace(',', '.'))
        registrar_transacao(now, "despesa", valor, "Gasto registrado", "Variável")
        saldo_atual = atualizar_saldo()
        await update.message.reply_text(f"💸 *Gasto registrado:* R$ {valor:.2f}\n💎 *Saldo atual:* R$ {saldo_atual:.2f}", parse_mode='Markdown')
        return
    
    # Verificar se é um comando de adicionar saldo
    match = padrao_adicionar.search(message_text)
    if match:
        valor = float(match.group(2).replace(',', '.'))
        registrar_transacao(now, "receita", valor, "Entrada de dinheiro", "Variável")
        saldo_atual = atualizar_saldo()
        await update.message.reply_text(f"💰 *Valor adicionado:* R$ {valor:.2f}\n💎 *Saldo atual:* R$ {saldo_atual:.2f}", parse_mode='Markdown')
        return
    
    # Verificar se é um comando de remover saldo
    match = padrao_remover.search(message_text)
    if match:
        valor = float(match.group(2).replace(',', '.'))
        registrar_transacao(now, "despesa", valor, "Saída de dinheiro", "Variável")
        saldo_atual = atualizar_saldo()
        await update.message.reply_text(f"💸 *Valor retirado:* R$ {valor:.2f}\n💎 *Saldo atual:* R$ {saldo_atual:.2f}", parse_mode='Markdown')
        return
    
    # Verificar se é um valor simples com + ou -
    match = padrao_valor_simples.search(message_text)
    if match:
        valor = float(match.group(1).replace(',', '.'))
        if message_text.startswith('+'):
            registrar_transacao(now, "receita", valor, "Entrada de dinheiro", "Variável")
            saldo_atual = atualizar_saldo()
            await update.message.reply_text(f"💰 *Valor adicionado:* R$ {valor:.2f}\n💎 *Saldo atual:* R$ {saldo_atual:.2f}", parse_mode='Markdown')
        elif message_text.startswith('-'):
            registrar_transacao(now, "despesa", valor, "Saída de dinheiro", "Variável")
            saldo_atual = atualizar_saldo()
            await update.message.reply_text(f"💸 *Valor retirado:* R$ {valor:.2f}\n💎 *Saldo atual:* R$ {saldo_atual:.2f}", parse_mode='Markdown')
        else:
            # Se não tem sinal, perguntar se é entrada ou saída
            await update.message.reply_text(
                f"💡 Valor detectado: R$ {valor:.2f}\n\nÉ uma entrada ou saída de dinheiro?",
                reply_markup=ReplyKeyboardMarkup([["➕ Entrada", "➖ Saída"]], resize_keyboard=True, one_time_keyboard=True)
            )
            context.user_data['ultimo_valor'] = valor
        return
    
    # Verificar se é um motivo/descrição
    match = padrao_motivo.search(message_text)
    if match and 'ultimo_valor' in context.user_data:
        motivo = match.group(2).strip()
        valor = context.user_data['ultimo_valor']
        registrar_transacao(now, "despesa", valor, motivo, "Variável")
        saldo_atual = atualizar_saldo()
        await update.message.reply_text(f"💸 *Gasto registrado:* R$ {valor:.2f}\n📝 *Motivo:* {motivo}\n💎 *Saldo atual:* R$ {saldo_atual:.2f}", 
                                      parse_mode='Markdown')
        del context.user_data['ultimo_valor']
        return
    
    # Se não reconhecer o padrão, mostrar ajuda
    await update.message.reply_text(
        "🤔 Não entendi. Use /help para ver exemplos de como registrar transações.\n\n"
        "📌 Exemplos:\n"
        "• Gastos: 150$\n"
        "• +saldo: 134$\n"
        "• -saldo: 100$\n"
        "• Motivo: Almoço",
        reply_markup=ReplyKeyboardMarkup([["Saldo", "Extrato", "Resumo"]], resize_keyboard=True)
    )

# Handler para botões de resposta rápida
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    if query == "Saldo":
        await saldo(update, context)
    elif query == "Extrato":
        await extrato(update, context)
    elif query == "Resumo":
        await resumo(update, context)
    elif query == "➕ Entrada":
        valor = context.user_data.get('ultimo_valor', 0)
        registrar_transacao(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "receita",
            valor,
            "Entrada de dinheiro",
            "Variável"
        )
        saldo_atual = atualizar_saldo()
        await update.message.reply_text(
            f"💰 *Valor adicionado:* R$ {valor:.2f}\n💎 *Saldo atual:* R$ {saldo_atual:.2f}", 
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["Saldo", "Extrato", "Resumo"]], resize_keyboard=True)
        )
        if 'ultimo_valor' in context.user_data:
            del context.user_data['ultimo_valor']
    elif query == "➖ Saída":
        valor = context.user_data.get('ultimo_valor', 0)
        await update.message.reply_text(
            f"💸 Informe o motivo da saída de R$ {valor:.2f}:\n\nEx: Motivo: Almoço",
            reply_markup=ReplyKeyboardRemove()
        )

def main():
    # Inicializar banco de dados
    init_db()
    
    # Criar Application
    application = Application.builder().token(TOKEN).build()
    
    # Adicionar handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("saldo", saldo))
    application.add_handler(CommandHandler("extrato", extrato))
    application.add_handler(CommandHandler("resumo", resumo))
    
    # Handler para botões de resposta rápida
    application.add_handler(MessageHandler(filters.Regex("^(Saldo|Extrato|Resumo|➕ Entrada|➖ Saída)$"), button_handler))
    
    # Handler para mensagens regulares
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Iniciar o bot
    application.run_polling()
    print("Bot iniciado!")

if __name__ == "__main__":
    main()
