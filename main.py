import asyncio
import logging
import json
import os
import sys
import time

# Получаем токен из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения Render!")
    sys.exit(1)

from datetime import datetime
from typing import Dict, List

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp import web

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# Хранение данных (временное, так как файловая система на Render непостоянная)
user_data: Dict[int, Dict[str, List]] = {}
DATA_FILE = "user_data.json"

def load_data():
    """Безопасная загрузка данных из JSON файла"""
    global user_data
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    user_data = {int(k): v for k, v in data.items()}
                    logger.info(f"Загружены данные для {len(user_data)} пользователей")
                else:
                    user_data = {}
                    logger.info("Файл данных пуст")
        else:
            user_data = {}
            logger.info("Файл данных не найден")
    except Exception as e:
        logger.error(f"Ошибка загрузки данных: {e}")
        user_data = {}

def save_data():
    """Сохранение данных в JSON файл"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
        logger.debug("Данные сохранены")
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}")

# Состояния FSM
class Form(StatesGroup):
    waiting_for_schedule_day = State()
    waiting_for_schedule_time = State()
    waiting_for_schedule_subject = State()
    waiting_for_deadline_name = State()
    waiting_for_deadline_date = State()
    waiting_for_note_text = State()
    waiting_for_search_query = State()

# Клавиатуры
def get_main_keyboard():
    buttons = [
        [KeyboardButton(text="📅 Расписание"), KeyboardButton(text="⏰ Дедлайны")],
        [KeyboardButton(text="📝 Заметки"), KeyboardButton(text="🔍 Поиск")],
        [KeyboardButton(text="📋 Сегодня"), KeyboardButton(text="ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_back_keyboard():
    buttons = [[KeyboardButton(text="↩️ Назад")]]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    
    if user_id not in user_data:
        user_data[user_id] = {
            "schedule": [],
            "deadlines": [],
            "notes": [],
            "name": user_name
        }
        save_data()
    
    await message.answer(
        f"👋 Привет, {user_name}!\n\n"
        "Я StudyBuddy - твой помощник в учебе!\n\n"
        "Выбери действие:",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_keyboard())

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📚 <b>StudyBuddy - Помощник студента</b>\n\n"
        "<b>Команды:</b>\n"
        "/start - начать\n"
        "/menu - главное меню\n"
        "/today - расписание на сегодня\n"
        "/help - справка\n"
        "/ping - проверить работу бота\n\n"
        "Используй кнопки для навигации!\n\n"
        "⚠️ <i>Бот работает на бесплатном хостинге.</i>\n"
        "<i>После 15 минут бездействия он 'засыпает'.</i>\n"
        "<i>Первое сообщение после сна может прийти с задержкой до 50 секунд.</i>",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await message.answer("Сначала нажми /start")
        return
    
    # Простая логика для демонстрации
    schedule = user_data[user_id].get("schedule", [])
    if schedule:
        await message.answer(f"📅 У тебя {len(schedule)} пар в расписании!")
    else:
        await message.answer("📭 Расписание пусто. Добавь пары!")

@dp.message(Command("ping"))
async def cmd_ping(message: types.Message):
    """Команда для проверки работы бота"""
    start_time = time.time()
    response = await message.answer("🏓 Проверка связи...")
    response_time = (time.time() - start_time) * 1000
    
    await message.answer(
        f"✅ <b>Pong!</b>\n"
        f"📶 Время ответа: {response_time:.0f} мс\n"
        f"⏰ Серверное время: {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"🔄 Бот активен и готов к работе!"
    )

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Команда для проверки статуса бота"""
    await message.answer(
        f"🤖 <b>Статус бота</b>\n\n"
        f"✅ Бот работает корректно\n"
        f"👤 Пользователей в базе: {len(user_data)}\n"
        f"⏰ Время сервера: {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"ℹ️ <i>Бот использует бесплатный Render</i>\n"
        f"<i>При простое >15 минут происходит 'сон'</i>\n"
        f"<i>Пробуждение занимает ~50 секунд</i>"
    )

# ========== ОБРАБОТЧИКИ КНОПОК ==========
@dp.message(lambda m: m.text == "📅 Расписание")
async def handle_schedule(message: types.Message):
    buttons = [
        [KeyboardButton(text="➕ Добавить пару")],
        [KeyboardButton(text="📋 Посмотреть расписание")],
        [KeyboardButton(text="↩️ Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("📅 <b>Управление расписанием</b>\n\nВыберите действие:", reply_markup=keyboard)

@dp.message(lambda m: m.text == "➕ Добавить пару")
async def add_schedule_start(message: types.Message, state: FSMContext):
    await message.answer("Введите день недели:", reply_markup=get_back_keyboard())
    await state.set_state(Form.waiting_for_schedule_day)

@dp.message(Form.waiting_for_schedule_day)
async def add_schedule_day(message: types.Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        await handle_schedule(message)
        return
    
    await state.update_data(day=message.text)
    await message.answer("Введите время (например: 10:30):")
    await state.set_state(Form.waiting_for_schedule_time)

@dp.message(Form.waiting_for_schedule_time)
async def add_schedule_time(message: types.Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        await add_schedule_start(message, state)
        return
    
    await state.update_data(time=message.text)
    await message.answer("Введите название предмета:")
    await state.set_state(Form.waiting_for_schedule_subject)

@dp.message(Form.waiting_for_schedule_subject)
async def add_schedule_subject(message: types.Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        await add_schedule_start(message, state)
        return
    
    data = await state.get_data()
    user_id = message.from_user.id
    
    new_class = {
        "day": data["day"],
        "time": data["time"],
        "subject": message.text,
        "added": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    
    user_data[user_id].setdefault("schedule", []).append(new_class)
    save_data()
    
    await message.answer(f"✅ <b>Пара добавлена!</b>\n\n{data['day']} {data['time']} - {message.text}")
    await state.clear()

@dp.message(lambda m: m.text == "📋 Посмотреть расписание")
async def handle_view_schedule(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await message.answer("Сначала нажмите /start")
        return
    
    schedule = user_data[user_id].get("schedule", [])
    
    if not schedule:
        await message.answer("📭 <b>Расписание пусто</b>\n\nДобавьте первую пару!")
        return
    
    response = "📅 <b>Ваше расписание:</b>\n\n"
    for i, cls in enumerate(schedule, 1):
        response += f"{i}. {cls.get('day', 'День')} {cls.get('time', 'Время')}\n"
        response += f"   📚 {cls.get('subject', 'Предмет')}\n"
        if cls.get('added'):
            response += f"   📅 Добавлено: {cls['added']}\n"
        response += "\n"
    
    await message.answer(response)

@dp.message(lambda m: m.text == "⏰ Дедлайны")
async def handle_deadlines(message: types.Message):
    buttons = [
        [KeyboardButton(text="➕ Новый дедлайн")],
        [KeyboardButton(text="📋 Мои дедлайны")],
        [KeyboardButton(text="↩️ Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("⏰ <b>Управление дедлайнами</b>\n\nВыберите действие:", reply_markup=keyboard)

@dp.message(lambda m: m.text == "➕ Новый дедлайн")
async def add_deadline_start(message: types.Message, state: FSMContext):
    await message.answer("Введите название задания:", reply_markup=get_back_keyboard())
    await state.set_state(Form.waiting_for_deadline_name)

@dp.message(Form.waiting_for_deadline_name)
async def add_deadline_name(message: types.Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        await handle_deadlines(message)
        return
    
    await state.update_data(name=message.text)
    await message.answer("Введите дату сдачи (ДД.ММ.ГГГГ):")
    await state.set_state(Form.waiting_for_deadline_date)

@dp.message(Form.waiting_for_deadline_date)
async def add_deadline_date(message: types.Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        await add_deadline_start(message, state)
        return
    
    data = await state.get_data()
    user_id = message.from_user.id
    
    new_deadline = {
        "name": data["name"],
        "due_date": message.text,
        "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "completed": False
    }
    
    user_data[user_id].setdefault("deadlines", []).append(new_deadline)
    save_data()
    
    await message.answer(f"✅ <b>Дедлайн добавлен!</b>\n\n{data['name']} - {message.text}")
    await state.clear()

@dp.message(lambda m: m.text == "📋 Мои дедлайны")
async def handle_view_deadlines(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await message.answer("Сначала нажмите /start")
        return
    
    deadlines = user_data[user_id].get("deadlines", [])
    
    if not deadlines:
        await message.answer("📭 <b>Дедлайнов нет</b>\n\nДобавьте первый дедлайн!")
        return
    
    response = "⏰ <b>Ваши дедлайны:</b>\n\n"
    for i, dl in enumerate(deadlines, 1):
        response += f"{i}. {dl.get('name', 'Задание')}\n"
        if dl.get('due_date'):
            response += f"   📅 Срок: {dl['due_date']}\n"
        if dl.get('created'):
            response += f"   📝 Добавлено: {dl['created']}\n"
        response += "\n"
    
    await message.answer(response)

@dp.message(lambda m: m.text == "📝 Заметки")
async def handle_notes(message: types.Message):
    buttons = [
        [KeyboardButton(text="➕ Новая заметка")],
        [KeyboardButton(text="📋 Все заметки")],
        [KeyboardButton(text="↩️ Назад")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("📝 <b>Управление заметками</b>\n\nВыберите действие:", reply_markup=keyboard)

@dp.message(lambda m: m.text == "➕ Новая заметка")
async def handle_add_note_button(message: types.Message, state: FSMContext):
    await message.answer("Напишите текст заметки:", reply_markup=get_back_keyboard())
    await state.set_state(Form.waiting_for_note_text)

@dp.message(Form.waiting_for_note_text)
async def add_note_text(message: types.Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        await handle_notes(message)
        return
    
    user_id = message.from_user.id
    new_note = {
        "text": message.text,
        "created": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    
    user_data[user_id].setdefault("notes", []).append(new_note)
    save_data()
    
    await message.answer(f"✅ <b>Заметка сохранена!</b>\n\nВсего заметок: {len(user_data[user_id]['notes'])}")
    await state.clear()

@dp.message(lambda m: m.text == "📋 Все заметки")
async def handle_view_all_notes(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_data:
        await message.answer("Сначала нажмите /start")
        return
    
    notes = user_data[user_id].get("notes", [])
    
    if not notes:
        await message.answer("📭 <b>Заметок нет</b>\n\nДобавьте первую заметку!")
        return
    
    response = f"📝 <b>Ваши заметки</b> (всего: {len(notes)})\n\n"
    for i, note in enumerate(reversed(notes[-10:]), 1):  # Последние 10
        text = note.get('text', '')
        preview = text[:50] + "..." if len(text) > 50 else text
        response += f"{i}. {preview}\n"
        if note.get('created'):
            response += f"   📅 {note['created']}\n"
        response += "\n"
    
    await message.answer(response)

@dp.message(lambda m: m.text == "🔍 Поиск")
async def handle_search(message: types.Message, state: FSMContext):
    await message.answer("🔍 <b>Поиск по заметкам</b>\n\nВведите текст для поиска:", reply_markup=get_back_keyboard())
    await state.set_state(Form.waiting_for_search_query)

@dp.message(Form.waiting_for_search_query)
async def process_search(message: types.Message, state: FSMContext):
    if message.text == "↩️ Назад":
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_keyboard())
        return
    
    user_id = message.from_user.id
    notes = user_data.get(user_id, {}).get("notes", [])
    
    found = [n for n in notes if message.text.lower() in n.get("text", "").lower()]
    
    if found:
        response = f"🔍 <b>Найдено заметок: {len(found)}</b>\n\n"
        for i, note in enumerate(found[:5], 1):  # Первые 5
            text = note.get('text', '')
            preview = text[:80] + "..." if len(text) > 80 else text
            response += f"{i}. {preview}\n"
            if note.get('created'):
                response += f"   📅 {note['created']}\n"
            response += "\n"
        
        if len(found) > 5:
            response += f"<i>Показано 5 из {len(found)}</i>"
    else:
        response = "🔍 <b>Ничего не найдено</b>"
    
    await message.answer(response)
    await state.clear()

@dp.message(lambda m: m.text == "📋 Сегодня")
async def handle_today_button(message: types.Message):
    await cmd_today(message)

@dp.message(lambda m: m.text == "ℹ️ Помощь")
async def handle_help_button(message: types.Message):
    await cmd_help(message)

@dp.message(lambda m: m.text == "↩️ Назад")
async def handle_back(message: types.Message):
    await message.answer("🏠 <b>Главное меню</b>", reply_markup=get_main_keyboard())

# ========== ОБРАБОТЧИК ОСТАЛЬНЫХ СООБЩЕНИЙ ==========
@dp.message()
async def handle_other_messages(message: types.Message):
    """Обработчик всех остальных сообщений (быстрые заметки)"""
    user_id = message.from_user.id
    
    if user_id not in user_data:
        return
    
    # Проверяем, не является ли сообщение командой
    if message.text.startswith('/'):
        return
    
    # Проверяем, не является ли сообщение текстом кнопки
    button_texts = [
        "📅 Расписание", "⏰ Дедлайны", "📝 Заметки", "🔍 Поиск",
        "📋 Сегодня", "ℹ️ Помощь", "↩️ Назад",
        "➕ Добавить пару", "📋 Посмотреть расписание",
        "➕ Новый дедлайн", "📋 Мои дедлайны",
        "➕ Новая заметка", "📋 Все заметки"
    ]
    
    if message.text in button_texts:
        return
    
    # Если не команда и не кнопка - сохраняем как быструю заметку
    new_note = {
        "text": message.text,
        "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "quick_save": True
    }
    
    user_data[user_id].setdefault("notes", []).append(new_note)
    save_data()
    
    # Отправляем подтверждение для коротких сообщений
    if len(message.text) < 100:
        await message.answer(f"💾 <b>Сохранено как заметка!</b>\n\nВсего заметок: {len(user_data[user_id]['notes'])}")

# ========== УТРЕННИЕ НАПОМИНАНИЯ ==========
async def send_digests():
    """Отправка утренних напоминаний"""
    logger.info("Отправка утренних напоминаний...")
    for user_id in user_data:
        try:
            await bot.send_message(
                user_id,
                "🌅 <b>Доброе утро!</b>\n\nУдачи в учебе сегодня! 🎓\n\n"
                "Не забудь проверить расписание и дедлайны!"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

# ========== HEALTH-CHECK СЕРВЕР ДЛЯ RENDER ==========
async def health_handler(request):
    """Обработчик для health-check от Render"""
    return web.Response(
        text=f"✅ StudyBuddy Bot работает\n"
             f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n"
             f"👤 Пользователей: {len(user_data)}",
        status=200
    )

async def wakeup_handler(request):
    """Специальный endpoint для внешних сервисов пробуждения"""
    logger.info("🔔 Wake-up запрос получен")
    return web.Response(
        text=f"✅ Bot woken up!\n"
             f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}",
        status=200
    )

async def start_web_server():
    """Запуск веб-сервера для health-check"""
    app = web.Application()
    
    # Основные endpoint'ы
    app.router.add_get('/', health_handler)
    app.router.add_get('/health', health_handler)
    app.router.add_get('/wakeup', wakeup_handler)  # Для внешних сервисов пробуждения
    app.router.add_get('/ping', health_handler)
    
    # Получаем порт из переменной окружения Render
    port = int(os.getenv("PORT", 10000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"✅ Веб-сервер запущен на порту {port}")
    logger.info(f"✅ Health-check доступен по адресу: /")
    logger.info(f"✅ Wake-up endpoint: /wakeup")
    
    return runner

# ========== ГЛАВНАЯ ФУНКЦИЯ ==========
async def main():
    """Основная функция запуска бота"""
    try:
        # Загружаем данные
        load_data()
        logger.info("🤖 Бот запускается...")
        
        # Настройка планировщика
        scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
        scheduler.add_job(send_digests, "cron", hour=8, minute=0)
        scheduler.start()
        logger.info("📅 Планировщик запущен (утренние напоминания в 8:00)")
        
        # Запуск health-check сервера
        health_runner = await start_web_server()
        
        # Даем время на запуск веб-сервера
        await asyncio.sleep(1)
        
        # Очистка webhook перед запуском polling
        logger.info("🧹 Очистка webhook...")
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook очищен")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось очистить webhook: {e}")
        
        # Пауза перед запуском polling
        await asyncio.sleep(2)
        
        # Запуск polling
        logger.info("🚀 Запуск Telegram polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при запуске: {e}")
        raise
    finally:
        # Корректное завершение
        logger.info("👋 Завершение работы бота...")
        try:
            if 'health_runner' in locals():
                await health_runner.cleanup()
            await bot.session.close()
        except Exception as e:
            logger.error(f"Ошибка при завершении: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 StudyBuddy Bot - Учебный помощник")
    print(f"⏰ Запуск: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Проверка токена
    if len(BOT_TOKEN) < 10:
        print("❌ ОШИБКА: Неверный BOT_TOKEN!")
        sys.exit(1)
    
    print(f"✅ Токен получен")
    print(f"✅ Порт: {os.getenv('PORT', 10000)}")
    print("=" * 60)
    
    # Запускаем бота
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен вручную")
    except Exception as e:
        print(f"💥 Непредвиденная ошибка: {e}")
