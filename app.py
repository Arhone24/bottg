import requests
from bs4 import BeautifulSoup
import time
import schedule
import telebot
from threading import Thread
from telebot import types

# Настройки бота
TELEGRAM_TOKEN = '7818314844:AAF73EocVoYtocd-m8Qpp7E1QCjcgbYWx-s'
CHAT_ID = 'YOUR_CHAT_ID'
CHECK_URL = 'https://fogplay.mts.ru/promo/computer/Onlinemmo/'
CHECK_INTERVAL = 2  # минуты

# Все возможные номера
ALL_NUMBERS = ['60A3X21', '60A3X10', '60A3X11', '60A3X13', '60A3X22', '60A3X16']

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Словари для хранения данных
user_tracked_numbers = {}  # {user_id: [numbers]}
last_statuses = {}         # {number: status}
status_subscribers = {}     # {number: [user_ids]}

def update_status(number):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(CHECK_URL, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('h2', {'class': 'card__title'}, string=number)
        new_status = "онлайн" if title else "занят"
        
        if number in last_statuses and last_statuses[number] != new_status:
            notify_subscribers(number, last_statuses[number], new_status)
        
        last_statuses[number] = new_status
        return new_status
    
    except Exception as e:
        print(f"Ошибка при проверке номера {number}: {str(e)}")
        return None

def notify_subscribers(number, old_status, new_status):
    if number in status_subscribers:
        for user_id in status_subscribers[number]:
            bot.send_message(
                user_id,
                f"🔔 Изменение статуса!\n"
                f"Номер: {number}\n"
                f"Был: {old_status} → Стал: {new_status}\n"
                f"Ссылка: {CHECK_URL}"
            )

def check_all_tracked_numbers():
    for number in list(last_statuses.keys()):
        update_status(number)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(func=lambda message: message.text in ALL_NUMBERS)
def track_number(message):
    user_id = message.from_user.id
    number = message.text
    
    if user_id not in user_tracked_numbers:
        user_tracked_numbers[user_id] = []
    
    if number not in user_tracked_numbers[user_id]:
        user_tracked_numbers[user_id].append(number)
        
        if number not in status_subscribers:
            status_subscribers[number] = []
            last_statuses[number] = update_status(number)
        
        if user_id not in status_subscribers[number]:
            status_subscribers[number].append(user_id)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Мои отслеживаемые", callback_data="my_tracking"))
        
        bot.reply_to(
            message,
            f"✅ Теперь отслеживаю номер {number}\n"
            f"Текущий статус: {last_statuses.get(number, 'неизвестен')}",
            reply_markup=markup
        )
    else:
        bot.reply_to(message, f"❕ Номер {number} уже в списке отслеживаемых")

@bot.message_handler(commands=['untrack'])
def untrack_number(message):
    user_id = message.from_user.id
    if user_id not in user_tracked_numbers or not user_tracked_numbers[user_id]:
        bot.reply_to(message, "У вас нет отслеживаемых номеров")
        return
    
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    for number in user_tracked_numbers[user_id]:
        markup.add(types.KeyboardButton(number))
    
    msg = bot.reply_to(message, "Выберите номер для удаления:", reply_markup=markup)
    bot.register_next_step_handler(msg, process_untrack)

def process_untrack(message):
    user_id = message.from_user.id
    number = message.text
    
    if number in user_tracked_numbers.get(user_id, []):
        user_tracked_numbers[user_id].remove(number)
        if user_id in status_subscribers.get(number, []):
            status_subscribers[number].remove(user_id)
        
        bot.reply_to(message, f"❎ Номер {number} больше не отслеживается")
    else:
        bot.reply_to(message, "Этот номер не был в вашем списке")

@bot.callback_query_handler(func=lambda call: call.data == "my_tracking")
def show_tracked_numbers(call):
    user_id = call.from_user.id
    if user_id in user_tracked_numbers and user_tracked_numbers[user_id]:
        numbers_list = "\n".join([
            f"• {num}: {last_statuses.get(num, 'неизвестен')}" 
            for num in user_tracked_numbers[user_id]
        ])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Удалить номер", callback_data="untrack_number"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📋 Ваши отслеживаемые номера:\n{numbers_list}",
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "У вас нет отслеживаемых номеров")

@bot.message_handler(commands=['status'])
def check_status(message):
    user_id = message.from_user.id
    if user_id in user_tracked_numbers and user_tracked_numbers[user_id]:
        for number in user_tracked_numbers[user_id]:
            current_status = update_status(number)
            bot.send_message(
                user_id,
                f"Номер: {number}\n"
                f"Статус: {current_status}\n"
                f"Последняя проверка: {time.strftime('%H:%M:%S')}"
            )
    else:
        bot.reply_to(message, "У вас нет отслеживаемых номеров. Отправьте мне номер для отслеживания")

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for number in ALL_NUMBERS:
        markup.add(types.KeyboardButton(number))
    
    bot.reply_to(
        message,
        "Привет! Я бот для отслеживания статусов компьютеров.\n"
        "Просто отправь мне номер компьютера, который хочешь отслеживать.\n"
        "Доступные номера: " + ", ".join(ALL_NUMBERS),
        reply_markup=markup
    )

if __name__ == "__main__":
    print("Бот запускается...")
    
    # Настраиваем расписание
    schedule.every(CHECK_INTERVAL).minutes.do(check_all_tracked_numbers)
    
    # Запускаем расписание в отдельном потоке
    scheduler_thread = Thread(target=run_schedule)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Запускаем бота
    bot.polling(none_stop=True)
