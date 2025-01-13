import telebot
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

API_TOKEN = '7645647001:AAEMeDbIehBAjAIkxGHa42oX-VdUTKamfAY'
CHANNEL_ID = '@formfox'  # или используйте ID канала
bot = telebot.TeleBot(API_TOKEN)

# Подключение к базе данных
DB_CONFIG = {
    'dbname': 'formfoxbot',
    'user': 'postgres',
    'password': 'postgres',
    'host': 'localhost'
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

def send_job_to_channel(job_title, job_description, job_salary, job_location, job_contact, hashtag):
    # Убираем символ # в начале хештега, если он есть
    if hashtag.startswith('#'):
        hashtag = hashtag[1:]

    # Экранируем символы, которые могут вызвать ошибку в Markdown
    message = f"📝 *{job_title.replace('*', '\\*')}*\n" \
              f"📍 {job_location.replace('*', '\\*').replace('_', '\\_')}\n" \
              f"💰 {job_salary.replace('*', '\\*').replace('_', '\\_')}\n" \
              f"📱 Контакт: {job_contact.replace('*', '\\*').replace('_', '\\_')}\n\n" \
              f"{job_description.replace('*', '\\*').replace('_', '\\_')}\n\n"

    # Добавляем хештег без повторного символа #
    message += f"#{hashtag}"

    bot.send_message(CHANNEL_ID, message, parse_mode="Markdown")



# Команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO users (telegram_id, username, first_name, last_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (telegram_id) DO NOTHING;
            """, (telegram_id, username, first_name, last_name))
    bot.reply_to(message, "Добро пожаловать в FormFoxBot! Здесь вы можете найти или опубликовать работу.")

# Команда для публикации вакансии
@bot.message_handler(commands=['new_job'])
def new_job_command(message):
    msg = bot.reply_to(message, "Введите название вакансии:")
    bot.register_next_step_handler(msg, process_job_title, "job")

def process_job_title(message, hashtag):
    title = message.text
    msg = bot.reply_to(message, "Введите описание вакансии:")
    bot.register_next_step_handler(msg, process_job_description, title, hashtag)

def process_job_description(message, title, hashtag):
    description = message.text
    msg = bot.reply_to(message, "Укажите зарплату (если нет, напишите 'договорная'):")
    bot.register_next_step_handler(msg, process_job_salary, title, description, hashtag)

def process_job_salary(message, title, description, hashtag):
    salary = message.text
    msg = bot.reply_to(message, "Укажите местоположение:")
    bot.register_next_step_handler(msg, process_job_location, title, description, salary, hashtag)

def process_job_location(message, title, description, salary, hashtag):
    location = message.text
    msg = bot.reply_to(message, "Введите контакт (или напишите '.', чтобы использовать свой аккаунт):")
    bot.register_next_step_handler(msg, preview_job, title, description, salary, location, hashtag)

def preview_job(message, title, description, salary, location, hashtag):
    contact = message.text.strip()
    if contact == ".":
        contact = f"@{message.from_user.username}"
    
    # Создаем уникальный идентификатор вакансии (например, UUID)
    job_id = f"{message.from_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Отправляем предварительный просмотр
    preview_message = f"📝 *{title}*\n📍 {location}\n💰 {salary}\n📱 Контакт: {contact}\n\n{description}"
    preview_msg = bot.reply_to(message, preview_message)

    # Спрашиваем пользователя о подтверждении
    confirmation_msg = bot.reply_to(message, "Предварительный просмотр вакансии. Вы хотите опубликовать её? Ответьте 'да' или 'нет'.")
    
    # Сохраняем данные вакансии до получения ответа
    bot.register_next_step_handler(confirmation_msg, confirm_or_cancel_job, job_id, title, description, salary, location, contact, preview_msg, message, hashtag)

def confirm_or_cancel_job(message, job_id, title, description, salary, location, contact, preview_msg, initial_message, hashtag):
    answer = message.text.strip().lower()
    
    if answer == 'да':
        # Сохраняем вакансию в базе данных
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO jobs (job_id, title, description, salary, location, contact, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (job_id, title, description, salary, location, contact, datetime.now()))

        # Отправляем вакансию в канал с хештегом
        send_job_to_channel(title, description, salary, location, contact, f"#formfox #{hashtag}")
        bot.reply_to(message, "Вакансия была успешно добавлена и опубликована в канале.")
    elif answer == 'нет':
        bot.reply_to(message, "Публикация вакансии отменена.")
    else:
        bot.reply_to(message, "Пожалуйста, ответьте 'да' или 'нет'.")
        # Повторно просим подтвердить
        confirmation_msg = bot.reply_to(message, "Вы хотите опубликовать её? Ответьте 'да' или 'нет'.")
        bot.register_next_step_handler(confirmation_msg, confirm_or_cancel_job, job_id, title, description, salary, location, contact, preview_msg, initial_message, hashtag)

# Команда для создания нового заказа
@bot.message_handler(commands=['new_order'])
def new_order_command(message):
    msg = bot.reply_to(message, "Введите название заказа:")
    bot.register_next_step_handler(msg, process_order_title, "order")

def process_order_title(message, hashtag):
    title = message.text
    msg = bot.reply_to(message, "Введите описание заказа:")
    bot.register_next_step_handler(msg, process_order_description, title, hashtag)

def process_order_description(message, title, hashtag):
    description = message.text
    msg = bot.reply_to(message, "Укажите требуемую сумма:")
    bot.register_next_step_handler(msg, process_order_price, title, description, hashtag)

def process_order_price(message, title, description, hashtag):
    price = message.text
    msg = bot.reply_to(message, "Укажите местоположение:")
    bot.register_next_step_handler(msg, process_order_location, title, description, price, hashtag)

def process_order_location(message, title, description, price, hashtag):
    location = message.text
    msg = bot.reply_to(message, "Введите контакт (или напишите '.', чтобы использовать свой аккаунт):")
    bot.register_next_step_handler(msg, preview_order, title, description, price, location, hashtag)

def preview_order(message, title, description, price, location, hashtag):
    contact = message.text.strip()
    if contact == ".":
        contact = f"@{message.from_user.username}"
    
    # Создаем уникальный идентификатор заказа (например, UUID)
    order_id = f"{message.from_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Отправляем предварительный просмотр
    preview_message = f"📦 *{title}*\n📍 {location}\n💵 {price}\n📱 Контакт: {contact}\n\n{description}"
    preview_msg = bot.reply_to(message, preview_message)

    # Спрашиваем пользователя о подтверждении
    confirmation_msg = bot.reply_to(message, "Предварительный просмотр заказа. Вы хотите опубликовать его? Ответьте 'да' или 'нет'.")
    
    # Сохраняем данные заказа до получения ответа
    bot.register_next_step_handler(confirmation_msg, confirm_or_cancel_order, order_id, title, description, price, location, contact, preview_msg, message, hashtag)

def confirm_or_cancel_order(message, order_id, title, description, price, location, contact, preview_msg, initial_message, hashtag):
    answer = message.text.strip().lower()
    
    if answer == 'да':
        # Сохраняем заказ в базе данных
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO orders (order_id, title, description, price, location, contact, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                """, (order_id, title, description, price, location, contact, datetime.now()))

        # Отправляем заказ в канал с хештегом
        send_job_to_channel(title, description, price, location, contact, f"#formfox #{hashtag}")
        bot.reply_to(message, "Заказ был успешно добавлен и опубликован в канале.")
    elif answer == 'нет':
        bot.reply_to(message, "Публикация заказа отменена.")
    else:
        bot.reply_to(message, "Пожалуйста, ответьте 'да' или 'нет'.")
        # Повторно просим подтвердить
        confirmation_msg = bot.reply_to(message, "Вы хотите опубликовать его? Ответьте 'да' или 'нет'.")
        bot.register_next_step_handler(confirmation_msg, confirm_or_cancel_order, order_id, title, description, price, location, contact, preview_msg, initial_message, hashtag)

# Запуск бота
bot.polling(none_stop=True)
