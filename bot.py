import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from datetime import datetime

# ==================== КОНФИГ ====================
BOT_TOKEN = 'ТВОЙ_ТОКЕН_ОТ_BOTFATHER'  # 👈 ЗАМЕНИ НА РЕАЛЬНЫЙ ТОКЕН
ADMIN_ID = 8478884644                   # 👈 ТВОЙ ID
USERNAME_DEPOSIT = '@debashev'          # 👈 СЮДА ПИСАТЬ ДЛЯ ПОПОЛНЕНИЯ
COMMISSION = 0.05                       # 5% комиссия

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ==================== БАЗА ДАННЫХ ====================
def get_db():
    return sqlite3.connect('exchange.db', check_same_thread=False)

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Таблица валют
    c.execute('''CREATE TABLE IF NOT EXISTS currencies (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        rate_to_usd REAL
    )''')
    # Таблица истории обменов
    c.execute('''CREATE TABLE IF NOT EXISTS exchange_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        from_curr TEXT,
        to_curr TEXT,
        amount REAL,
        result REAL,
        commission REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # Добавляем тестовые валюты если пусто
    c.execute("SELECT COUNT(*) FROM currencies")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO currencies (name, rate_to_usd) VALUES ('GRAMM', 1.0)")
        c.execute("INSERT INTO currencies (name, rate_to_usd) VALUES ('ЗВЕЗДЫ', 2.0)")
        c.execute("INSERT INTO currencies (name, rate_to_usd) VALUES ('M¢', 0.8)")
        conn.commit()
    conn.close()

init_db()

# ==================== РАБОТА С БАЗОЙ ====================
def get_currencies():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name FROM currencies ORDER BY name")
    res = [row[0] for row in c.fetchall()]
    conn.close()
    return res

def get_rate(name):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT rate_to_usd FROM currencies WHERE name=?", (name,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def add_currency(name, rate):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO currencies (name, rate_to_usd) VALUES (?, ?)", (name.upper(), rate))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def delete_currency(name):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM currencies WHERE name=?", (name.upper(),))
    conn.commit()
    conn.close()

def update_rate(name, new_rate):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE currencies SET rate_to_usd=? WHERE name=?", (new_rate, name.upper()))
    conn.commit()
    conn.close()

def save_exchange(user_id, username, from_curr, to_curr, amount, result, commission):
    conn = get_db()
    c = conn.cursor()
    c.execute("""INSERT INTO exchange_history 
                 (user_id, username, from_curr, to_curr, amount, result, commission) 
                 VALUES (?,?,?,?,?,?,?)""",
              (user_id, username, from_curr, to_curr, amount, result, commission))
    conn.commit()
    conn.close()

def get_history(limit=20):
    conn = get_db()
    c = conn.cursor()
    c.execute("""SELECT user_id, username, from_curr, to_curr, amount, result, commission, timestamp 
                 FROM exchange_history ORDER BY id DESC LIMIT ?""", (limit,))
    res = c.fetchall()
    conn.close()
    return res

# ==================== ХРАНЕНИЕ СОСТОЯНИЙ ====================
user_state = {}

# ==================== АДМИН-ПАНЕЛЬ ====================
def is_admin(user_id):
    return user_id == ADMIN_ID

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Добавить валюту", callback_data="admin_add"),
        InlineKeyboardButton("➖ Удалить валюту", callback_data="admin_del"),
        InlineKeyboardButton("📊 Изменить курс", callback_data="admin_rate"),
        InlineKeyboardButton("📋 Список валют", callback_data="admin_list"),
        InlineKeyboardButton("📜 История обменов", callback_data="admin_history")
    )
    await message.answer("⚙️ <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=markup, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data.startswith("admin_"))
async def admin_actions(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("Нет прав", show_alert=True)
        return
    action = callback_query.data.split("_")[1]
    
    if action == "add":
        await bot.send_message(callback_query.from_user.id, "📝 Введите название валюты и курс (в USD) через пробел:\n\nПример: <code>BTC 50000</code>", parse_mode="HTML")
        user_state[callback_query.from_user.id] = {"admin_action": "add"}
    
    elif action == "del":
        curr_list = "\n".join([f"• {c}" for c in get_currencies()])
        await bot.send_message(callback_query.from_user.id, f"🗑 Введите название валюты для удаления:\n\n{curr_list}")
        user_state[callback_query.from_user.id] = {"admin_action": "del"}
    
    elif action == "rate":
        curr_list = "\n".join([f"• {c} = {get_rate(c)} USD" for c in get_currencies()])
        await bot.send_message(callback_query.from_user.id, f"📊 Введите валюту и новый курс:\n\n{curr_list}\n\nПример: <code>BTC 60000</code>", parse_mode="HTML")
        user_state[callback_query.from_user.id] = {"admin_action": "rate"}
    
    elif action == "list":
        currencies = get_currencies()
        if not currencies:
            await bot.send_message(callback_query.from_user.id, "⚠️ Нет добавленных валют")
        else:
            text = "💰 <b>Список валют и курсов</b>\n\n"
            for curr in currencies:
                rate = get_rate(curr)
                text += f"• {curr} = {rate} USD\n"
            await bot.send_message(callback_query.from_user.id, text, parse_mode="HTML")
    
    elif action == "history":
        history = get_history(30)
        if not history:
            await bot.send_message(callback_query.from_user.id, "📭 История обменов пуста")
        else:
            text = "📜 <b>Последние 30 обменов</b>\n\n"
            for h in history:
                text += f"👤 {h[1] or h[0]} | {h[2]} → {h[3]} | {h[4]} → {round(h[5],4)} | комиссия: {round(h[6],4)} | {h[7][:16]}\n"
            await bot.send_message(callback_query.from_user.id, text[:4000], parse_mode="HTML")
    
    await callback_query.answer()

@dp.message_handler(lambda msg: msg.from_user.id in user_state and "admin_action" in user_state.get(msg.from_user.id, {}))
async def admin_text_input(message: types.Message):
    action = user_state[message.from_user.id]["admin_action"]
    
    if action == "add":
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Ошибка! Формат: <code>Название Курс</code>\nПример: <code>BTC 50000</code>", parse_mode="HTML")
            return
        name, rate = parts[0].upper(), float(parts[1])
        if add_currency(name, rate):
            await message.answer(f"✅ Валюта <b>{name}</b> добавлена с курсом {rate} USD", parse_mode="HTML")
        else:
            await message.answer(f"❌ Валюта <b>{name}</b> уже существует", parse_mode="HTML")
    
    elif action == "del":
        name = message.text.upper()
        if get_rate(name) is not None:
            delete_currency(name)
            await message.answer(f"✅ Валюта <b>{name}</b> удалена", parse_mode="HTML")
        else:
            await message.answer(f"❌ Валюта <b>{name}</b> не найдена", parse_mode="HTML")
    
    elif action == "rate":
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Ошибка! Формат: <code>Валюта НовыйКурс</code>\nПример: <code>BTC 60000</code>", parse_mode="HTML")
            return
        name, new_rate = parts[0].upper(), float(parts[1])
        if get_rate(name) is not None:
            update_rate(name, new_rate)
            await message.answer(f"✅ Курс <b>{name}</b> обновлён: {new_rate} USD", parse_mode="HTML")
        else:
            await message.answer(f"❌ Валюта <b>{name}</b> не найдена", parse_mode="HTML")
    
    del user_state[message.from_user.id]

# ==================== ОСНОВНОЙ БОТ ====================
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    currencies = get_currencies()
    if not currencies:
        await message.answer("⚠️ Валюты ещё не добавлены. Админ может добавить их через /admin")
        return
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(curr, callback_data=f"from_{curr}") for curr in currencies]
    markup.add(*buttons)
    await message.answer(
        f"👋 <b>Здравствуйте!</b>\n\n"
        f"💰 Выберите валюту, которую хотите обменять:\n\n"
        f"💡 <b>Как пополнить баланс?</b>\n"
        f"Напишите {USERNAME_DEPOSIT} с указанием валюты и суммы.",
        reply_markup=markup,
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda c: c.data.startswith("from_"))
async def choose_from(callback_query: types.CallbackQuery):
    from_curr = callback_query.data.split("_")[1]
    currencies = [c for c in get_currencies() if c != from_curr]
    
    if not currencies:
        await bot.send_message(callback_query.from_user.id, "❌ Нет доступных валют для обмена")
        await callback_query.answer()
        return
    
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(curr, callback_data=f"pair_{from_curr}_{curr}") for curr in currencies]
    markup.add(*buttons)
    markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_start"))
    
    # Показываем курсы
    text = f"💱 <b>{from_curr} → ?</b>\n\n"
    for curr in currencies:
        rate_from = get_rate(from_curr)
        rate_to = get_rate(curr)
        if rate_from and rate_to:
            exchange_rate = (rate_from / rate_to) * (1 - COMMISSION)
            text += f"• 1 {from_curr} ≈ {round(exchange_rate, 6)} {curr} (с учётом 5% комиссии)\n"
    
    await bot.send_message(callback_query.from_user.id, text, reply_markup=markup, parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "back_to_start")
async def back_to_start(callback_query: types.CallbackQuery):
    await start(callback_query.message)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("pair_"))
async def choose_to(callback_query: types.CallbackQuery):
    _, from_curr, to_curr = callback_query.data.split("_")
    user_state[callback_query.from_user.id] = {"from": from_curr, "to": to_curr}
    
    rate_from = get_rate(from_curr)
    rate_to = get_rate(to_curr)
    raw_rate = rate_from / rate_to
    rate_with_comission = raw_rate * (1 - COMMISSION)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("◀️ Назад к выбору", callback_data=f"from_{from_curr}"))
    
    await bot.send_message(
        callback_query.from_user.id,
        f"💱 <b>{from_curr} → {to_curr}</b>\n\n"
        f"📊 Курс: 1 {from_curr} = {round(rate_with_comission, 6)} {to_curr}\n"
        f"💰 Комиссия: 5%\n\n"
        f"✏️ <b>Введите сумму {from_curr}</b>, которую хотите обменять:",
        reply_markup=markup,
        parse_mode="HTML"
    )
    await callback_query.answer()

@dp.message_handler(lambda msg: msg.from_user.id in user_state and "to" in user_state.get(msg.from_user.id, {}))
async def process_exchange(message: types.Message):
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except:
        await message.answer("❌ Введите <b>положительное число</b> (например: 100 или 50.5)", parse_mode="HTML")
        return
    
    user_data = user_state[message.from_user.id]
    from_curr = user_data["from"]
    to_curr = user_data["to"]
    
    rate_from = get_rate(from_curr)
    rate_to = get_rate(to_curr)
    
    if rate_from is None or rate_to is None:
        await message.answer("❌ Ошибка курса, попробуйте /start")
        del user_state[message.from_user.id]
        return
    
    # Расчёт
    usd_value = amount * rate_from
    raw_result = usd_value / rate_to
    commission_amount = raw_result * COMMISSION
    result_after_commission = raw_result - commission_amount
    
    # Сохраняем в историю
    username = message.from_user.username or str(message.from_user.id)
    save_exchange(message.from_user.id, username, from_curr, to_curr, amount, result_after_commission, commission_amount)
    
    # Кнопки
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔄 Новый обмен", callback_data="new_exchange"),
        InlineKeyboardButton("📊 Курсы валют", callback_data="show_rates")
    )
    
    await message.answer(
        f"✅ <b>Обмен выполнен!</b>\n\n"
        f"📤 <b>Отдаёте:</b> {amount} {from_curr}\n"
        f"📥 <b>Получаете:</b> {round(result_after_commission, 6)} {to_curr}\n"
        f"💸 <b>Комиссия (5%):</b> {round(commission_amount, 6)} {to_curr}\n"
        f"📈 <b>Курс с комиссией:</b> 1 {from_curr} = {round((rate_from/rate_to)*(1-COMMISSION), 6)} {to_curr}\n\n"
        f"💡 <b>Пополнить баланс:</b> {USERNAME_DEPOSIT}",
        reply_markup=markup,
        parse_mode="HTML"
    )
    del user_state[message.from_user.id]

@dp.callback_query_handler(lambda c: c.data == "new_exchange")
async def new_exchange(callback_query: types.CallbackQuery):
    await start(callback_query.message)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "show_rates")
async def show_rates(callback_query: types.CallbackQuery):
    currencies = get_currencies()
    if not currencies:
        await bot.send_message(callback_query.from_user.id, "⚠️ Нет валют")
        await callback_query.answer()
        return
    
    text = "💰 <b>Текущие курсы (база USD)</b>\n\n"
    for curr in currencies:
        rate = get_rate(curr)
        text += f"• 1 {curr} = {rate} USD\n"
    
    text += f"\n💸 <b>Комиссия за обмен:</b> {int(COMMISSION*100)}%"
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_start"))
    
    await bot.send_message(callback_query.from_user.id, text, reply_markup=markup, parse_mode="HTML")
    await callback_query.answer()

# ==================== КОМАНДА ДЛЯ АДМИНА (ПОСМОТРЕТЬ СТАТИСТИКУ) ====================
@dp.message_handler(commands=['stats'])
async def stats(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет прав")
        return
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM exchange_history")
    total_exchanges = c.fetchone()[0]
    c.execute("SELECT SUM(commission) FROM exchange_history")
    total_commission = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(DISTINCT user_id) FROM exchange_history")
    unique_users = c.fetchone()[0]
    conn.close()
    
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"🔄 Всего обменов: {total_exchanges}\n"
        f"👥 Уникальных пользователей: {unique_users}\n"
        f"💰 Собрано комиссии: {round(total_commission, 6)} (в целевой валюте)\n"
        f"⚙️ Комиссия: {int(COMMISSION*100)}%",
        parse_mode="HTML"
    )

# ==================== ЗАПУСК ====================
if __name__ == '__main__':
    print("✅ Бот запущен!")
    print(f"👤 Админ ID: {ADMIN_ID}")
    print(f"💰 Комиссия: {COMMISSION*100}%")
    executor.start_polling(dp, skip_updates=True)
