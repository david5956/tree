import telebot
from telebot import types
import sqlite3
import threading
import time
from datetime import datetime, timedelta
import os
import logging

# Настройка логирования
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

# Инициализация бота
try:
    bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))
    logger.info("Бот успешно инициализирован")
except Exception as e:
    logger.error(f"Ошибка при инициализации бота: {str(e)}")
    exit()

# Инициализация БД
def init_db():
    try:
        conn = sqlite3.connect('reminders.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            time TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            repeat_interval TEXT,
            next_time TEXT NOT NULL
        )
        ''')
        conn.commit()
        logger.info("База данных инициализирована")
        return conn, cursor
    except Exception as e:
        logger.error(f"Ошибка базы данных: {str(e)}")
        exit()

conn, cursor = init_db()

# Установка меню команд
def set_bot_commands():
    try:
        bot.set_my_commands([
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("remind", "Создать напоминание"),
            types.BotCommand("my_reminders", "Мои напоминания"),
            types.BotCommand("del_reminder", "Удалить напоминание"),
            types.BotCommand("set_repeat", "Настроить повтор")
        ])
    except Exception as e:
        logger.error(f"Ошибка установки команд: {str(e)}")

set_bot_commands()

# Состояния пользователей
user_states = {}

# Клавиатуры
def create_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "➕ Создать напоминание",
        "📝 Мои напоминания",
        "❌ Удалить напоминание",
        "🔄 Настроить повтор"
    ]
    markup.add(*buttons)
    return markup

def create_repeat_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("Ежедневно", callback_data='repeat_daily'),
        types.InlineKeyboardButton("Еженедельно", callback_data='repeat_weekly'),
        types.InlineKeyboardButton("Ежемесячно", callback_data='repeat_monthly'),
        types.InlineKeyboardButton("❌ Без повтора", callback_data='repeat_none')
    ]
    markup.add(*buttons)
    return markup

# Обработчики команд
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    try:
        text = (
            "🔔 <b>Бот-напоминалка</b>\n\n"
            "📌 <b>Доступные команды:</b>\n"
            "/remind - Создать напоминание\n"
            "/my_reminders - Список напоминаний\n"
            "/del_reminder - Удалить напоминание\n"
            "/set_repeat - Настроить повтор\n\n"
            "Или используйте кнопки ниже:"
        )
        bot.send_message(
            message.chat.id,
            text,
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в send_welcome: {str(e)}")

@bot.message_handler(commands=['remind'])
def handle_remind_command(message):
    ask_for_reminder(message)

@bot.message_handler(commands=['my_reminders'])
def handle_my_reminders_command(message):
    show_reminders(message)

@bot.message_handler(commands=['del_reminder'])
def handle_del_reminder_command(message):
    ask_for_reminder_id(message)

@bot.message_handler(commands=['set_repeat'])
def handle_set_repeat_command(message):
    ask_for_repeat_id(message)

# Обработчики кнопок
@bot.message_handler(func=lambda m: m.text in ["➕ Создать напоминание", "Создать напоминание"])
def handle_create_button(message):
    ask_for_reminder(message)

@bot.message_handler(func=lambda m: m.text in ["📝 Мои напоминания", "Мои напоминания"])
def handle_list_button(message):
    show_reminders(message)

@bot.message_handler(func=lambda m: m.text in ["❌ Удалить напоминание", "Удалить напоминание"])
def handle_delete_button(message):
    ask_for_reminder_id(message)

@bot.message_handler(func=lambda m: m.text in ["🔄 Настроить повтор", "Настроить повтор"])
def handle_repeat_button(message):
    ask_for_repeat_id(message)

# Основные функции
def ask_for_reminder(message):
    try:
        user_states[message.chat.id] = {'state': 'waiting_for_reminder'}
        bot.send_message(
            message.chat.id,
            "📝 Введите напоминание в формате:\n"
            "<code>ДД.ММ.ГГГГ ЧЧ:MM Текст</code>\n\n"
            "Пример:\n"
            "<code>20.10.2025 10:00 Поздравить Давида с ДР</code>",
            parse_mode='HTML',
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Ошибка в ask_for_reminder: {str(e)}")

def process_reminder(message):
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError("Недостаточно параметров")
            
        date_str, time_str, text = parts
        date_obj = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        formatted_time = date_obj.strftime("%Y-%m-%d %H:%M")
        
        cursor.execute(
            'INSERT INTO reminders(chat_id, text, time, next_time) VALUES (?, ?, ?, ?)',
            (message.chat.id, text, formatted_time, formatted_time)
        )
        conn.commit()
        
        response = (
            f"✅ <b>Напоминание создано!</b>\n\n"
            f"📅 <b>Дата:</b> {date_str} {time_str}\n"
            f"📝 <b>Текст:</b> {text}\n\n"
            f"ID: {cursor.lastrowid}"
        )
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ <b>Ошибка формата!</b>\nИспользуйте: ДД.ММ.ГГГГ ЧЧ:MM Текст\n\n"
            "Пример: <code>20.10.2025 10:00 Поздравить Давида с ДР</code>",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка создания напоминания: {str(e)}")
        bot.send_message(
            message.chat.id,
            "❌ Произошла ошибка при создании напоминания",
            reply_markup=create_main_keyboard()
        )
    finally:
        user_states.pop(message.chat.id, None)

def show_reminders(message):
    try:
        cursor.execute(
            '''SELECT id, time, text, repeat_interval 
               FROM reminders 
               WHERE chat_id = ? AND is_active = 1 
               ORDER BY time''',
            (message.chat.id,)
        )
        reminders = cursor.fetchall()
        
        if not reminders:
            bot.send_message(
                message.chat.id,
                "📭 У вас пока нет активных напоминаний",
                reply_markup=create_main_keyboard()
            )
            return
            
        response = "📋 <b>Ваши напоминания:</b>\n\n"
        for rem in reminders:
            date_obj = datetime.strptime(rem[1], "%Y-%m-%d %H:%M")
            formatted_time = date_obj.strftime("%d.%m.%Y %H:%M")
            repeat_info = f" (повтор: {rem[3]})" if rem[3] else ""
            response += f"🆔 <b>{rem[0]}</b>: ⏰ {formatted_time}{repeat_info}\n✏️ {rem[2]}\n\n"
            
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка показа напоминаний: {str(e)}")
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при получении напоминаний",
            reply_markup=create_main_keyboard()
        )

def ask_for_reminder_id(message):
    try:
        user_states[message.chat.id] = {'state': 'waiting_for_reminder_id'}
        bot.send_message(
            message.chat.id,
            "✏️ Введите <b>ID напоминания</b> для удаления:",
            parse_mode='HTML',
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Ошибка в ask_for_reminder_id: {str(e)}")

def delete_reminder(message):
    try:
        reminder_id = int(message.text)
        cursor.execute(
            'DELETE FROM reminders WHERE id = ? AND chat_id = ?',
            (reminder_id, message.chat.id)
        )
        conn.commit()
        
        if cursor.rowcount > 0:
            bot.send_message(
                message.chat.id,
                f"✅ Напоминание <b>{reminder_id}</b> успешно удалено!",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                f"❌ Напоминание <b>{reminder_id}</b> не найдено!",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Введите <b>числовой ID</b> напоминания!",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка удаления напоминания: {str(e)}")
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при удалении напоминания",
            reply_markup=create_main_keyboard()
        )
    finally:
        user_states.pop(message.chat.id, None)

def ask_for_repeat_id(message):
    try:
        user_states[message.chat.id] = {'state': 'waiting_for_repeat_id'}
        bot.send_message(
            message.chat.id,
            "✏️ Введите <b>ID напоминания</b> для настройки повтора:",
            parse_mode='HTML',
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f"Ошибка в ask_for_repeat_id: {str(e)}")

def process_repeat_id(message):
    try:
        reminder_id = int(message.text)
        cursor.execute(
            'SELECT id FROM reminders WHERE id = ? AND chat_id = ?',
            (reminder_id, message.chat.id)
        )
        if not cursor.fetchone():
            bot.send_message(
                message.chat.id,
                f"❌ Напоминание <b>{reminder_id}</b> не найдено!",
                parse_mode='HTML',
                reply_markup=create_main_keyboard()
            )
            return
            
        user_states[message.chat.id] = {
            'state': 'waiting_for_repeat_interval',
            'reminder_id': reminder_id
        }
        bot.send_message(
            message.chat.id,
            f"Выберите интервал повторения для напоминания <b>{reminder_id}</b>:",
            parse_mode='HTML',
            reply_markup=create_repeat_keyboard()
        )
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ Введите <b>числовой ID</b> напоминания!",
            parse_mode='HTML',
            reply_markup=create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка обработки ID для повтора: {str(e)}")
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при обработке запроса",
            reply_markup=create_main_keyboard()
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('repeat_'))
def handle_repeat_selection(call):
    try:
        chat_id = call.message.chat.id
        if user_states.get(chat_id, {}).get('state') != 'waiting_for_repeat_interval':
            bot.answer_callback_query(call.id, "Неверный контекст")
            return
            
        reminder_id = user_states[chat_id]['reminder_id']
        interval = call.data.split('_')[1]
        
        if interval == 'none':
            cursor.execute(
                'UPDATE reminders SET repeat_interval = NULL WHERE id = ?',
                (reminder_id,)
            )
            message_text = f"🔄 Повтор для напоминания <b>{reminder_id}</b> отключен"
        else:
            cursor.execute(
                'UPDATE reminders SET repeat_interval = ? WHERE id = ?',
                (interval, reminder_id)
            )
            message_text = f"🔄 Установлен повтор для напоминания <b>{reminder_id}</b>: {interval}"
        
        conn.commit()
        bot.edit_message_text(
            message_text,
            chat_id,
            call.message.message_id,
            parse_mode='HTML'
        )
        bot.send_message(
            chat_id,
            "Готово! ✅",
            reply_markup=create_main_keyboard()
        )
        user_states.pop(chat_id, None)
    except Exception as e:
        logger.error(f"Ошибка в handle_repeat_selection: {str(e)}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка")

# Функции для напоминаний
def check_reminders():
    while True:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor.execute(
                "SELECT id, chat_id, text, repeat_interval, next_time "
                "FROM reminders WHERE next_time <= ? AND is_active = 1",
                (now,)
            )
            reminders = cursor.fetchall()

            for rem in reminders:
                try:
                    bot.send_message(
                        rem[1], 
                        f"🔔 <b>Напоминание:</b> {rem[2]}", 
                        parse_mode='HTML'
                    )
                    
                    if rem[3]:  # Если есть повтор
                        update_repeated_reminder(rem)
                    else:
                        cursor.execute(
                            "UPDATE reminders SET is_active = 0 WHERE id = ?",
                            (rem[0],)
                        )
                    conn.commit()
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания {rem[0]}: {str(e)}")
                    time.sleep(5)

            time.sleep(30)
        except Exception as e:
            logger.error(f"Ошибка в check_reminders: {str(e)}")
            time.sleep(60)

def update_repeated_reminder(reminder):
    try:
        interval = reminder[3]
        next_time = datetime.strptime(reminder[4], "%Y-%m-%d %H:%M")
        
        if interval == 'daily':
            next_time += timedelta(days=1)
        elif interval == 'weekly':
            next_time += timedelta(weeks=1)
        elif interval == 'monthly':
            next_time += timedelta(days=30)
            
        cursor.execute(
            "UPDATE reminders SET next_time = ? WHERE id = ?",
            (next_time.strftime("%Y-%m-%d %H:%M"), reminder[0])
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка обновления повтора: {str(e)}")

# Обработчики состояний
@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('state') == 'waiting_for_reminder')
def handle_reminder_input(message):
    process_reminder(message)

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('state') == 'waiting_for_reminder_id')
def handle_reminder_id_input(message):
    delete_reminder(message)

@bot.message_handler(func=lambda m: user_states.get(m.chat.id, {}).get('state') == 'waiting_for_repeat_id')
def handle_repeat_id_input(message):
    process_repeat_id(message)

# Запуск бота
if __name__ == '__main__':
    try:
        logger.info("----- Запуск бота -----")
        threading.Thread(target=check_reminders, daemon=True).start()
        bot.infinity_polling()
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {str(e)}")
    finally:
        conn.close()
        logger.info("----- Работа завершена -----")