"""
Модуль для отправки Telegram уведомлений о новых отзывах
"""
import json
import asyncio
from pathlib import Path
from datetime import datetime
import pandas as pd
from telegram import Bot, Update
from telegram.constants import ParseMode

# Загрузка конфигурации
CONFIG_PATH = Path(__file__).parent.parent / "config.json"
SUBSCRIBERS_PATH = Path(__file__).parent.parent / "subscribers.txt"

def load_config():
    """Загружает конфигурацию из config.json"""
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_subscribers():
    """
    Загружает список подписчиков из subscribers.txt
    
    Returns:
        set: Множество chat_id подписчиков
    """
    if not SUBSCRIBERS_PATH.exists():
        print("⚠️ Файл subscribers.txt не найден. Создаю новый...")
        SUBSCRIBERS_PATH.write_text("# Список подписчиков\n", encoding="utf-8")
        return set()
    
    subscribers = set()
    with open(SUBSCRIBERS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Пропускаем комментарии и пустые строки
            if line and not line.startswith("#"):
                try:
                    subscribers.add(int(line))
                except ValueError:
                    print(f"⚠️ Некорректный chat_id: {line}")
    
    return subscribers

def save_subscribers(subscribers_set):
    """
    Сохраняет список подписчиков в subscribers.txt
    
    Args:
        subscribers_set: Множество chat_id
    """
    with open(SUBSCRIBERS_PATH, "w", encoding="utf-8") as f:
        f.write("# Список подписчиков Telegram бота\n")
        for chat_id in sorted(subscribers_set):
            f.write(f"{chat_id}\n")

async def process_subscriptions_async():
    """
    Обрабатывает все пропущенные /start команды
    Сохраняет новые chat_id в subscribers.txt
    """
    config = load_config()
    bot_token = config.get("telegram_bot_token")
    
    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token не настроен в config.json.")
        return
    
    current_subscribers = load_subscribers()
    new_subscribers = []
    
    print("\n🤖 Проверка новых подписчиков...")
    
    try:
        async with Bot(token=bot_token) as bot:
            # Получаем информацию о боте для проверки токена
            me = await bot.get_me()
            print(f"   Бот: @{me.username} (ID: {me.id})")
            
            # Получаем все обновления (включая пропущенные)
            # timeout=5 ждет 5 секунд, если нет новых. Но старые вернет сразу.
            updates = await bot.get_updates(timeout=5)
            print(f"   Получено обновлений: {len(updates)}")
            
            for update in updates:
                if update.message and update.message.text:
                    text = update.message.text.strip()
                    chat_id = update.message.chat.id
                    print(f"   Сообщение от {chat_id}: {text}")
                    
                    if text == "/start":
                        if chat_id not in current_subscribers:
                            current_subscribers.add(chat_id)
                            new_subscribers.append(chat_id)
                            print(f"   ✅ Новый подписчик: {chat_id}")
                            
                            # Отправляем приветственное сообщение
                            try:
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text="✅ <b>Вы подписались на уведомления!</b>\n\n"
                                         "Теперь вы будете получать отчеты о новых отзывах.\n"
                                         "Отчеты отправляются автоматически после каждого парсинга.",
                                    parse_mode=ParseMode.HTML
                                )
                            except Exception as e:
                                print(f"   ⚠️ Ошибка отправки приветствия {chat_id}: {e}")
                        else:
                            print(f"   ℹ️ Пользователь {chat_id} уже подписан")
            
            # Подтверждаем обработку всех updates
            if updates:
                last_update_id = updates[-1].update_id
                await bot.get_updates(offset=last_update_id + 1)
                print("   Updates подтверждены")
            
            # Сохраняем обновленный список
            if new_subscribers:
                save_subscribers(current_subscribers)
                print(f"\n📝 Добавлено новых подписчиков: {len(new_subscribers)}")
                print(f"📊 Всего подписчиков: {len(current_subscribers)}")
            else:
                print("ℹ️ Новых подписчиков нет")
            
    except Exception as e:
        print(f"❌ Ошибка при обработке подписок: {e}")
        import traceback
        traceback.print_exc()

def process_subscriptions():
    """Синхронная обертка для обработки подписок"""
    try:
        asyncio.run(process_subscriptions_async())
    except Exception as e:
        print(f"Error processing subscriptions: {e}")


def format_report(df):
    """
    Форматирует отчет о новых отзывах из DataFrame
    
    Args:
        df: DataFrame с новыми отзывами
        
    Returns:
        str: Отформатированный отчет для Telegram (с HTML разметкой)
    """
    if df.empty:
        return "📊 <b>Новых отзывов нет</b>"
    
    # Общая статистика
    total = len(df)
    negative = len(df[df['Tags'] != '#Позитивное/без_комментария'])
    negative_pct = (negative / total * 100) if total > 0 else 0
    
    # Сегодняшняя дата
    today = datetime.now().strftime("%d.%m.%Y")
    
    report = f"""📊 <b>Новые отзывы ({today})</b>

<b>Всего:</b> {total} отзывов
<b>Негативных:</b> {negative} ({negative_pct:.1f}%)
"""
    
    # Статистика по тегам (только для негативных)
    if negative > 0:
        negative_df = df[df['Tags'] != '#Позитивное/без_комментария']
        
        # Подсчет тегов
        tag_counts = {}
        for tags_str in negative_df['Tags']:
            for tag in tags_str.split(', '):
                tag = tag.strip()
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # Сортировка по количеству
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        
        report += "\n<b>По тегам:</b>\n"
        for tag, count in sorted_tags:
            report += f"{tag}: {count}\n"
        
        # Примеры негативных отзывов (максимум 3)
        report += "\n<b>Примеры негативных:</b>\n"
        examples = negative_df.head(3)
        
        for idx, row in examples.iterrows():
            city = row.get('City', 'Н/Д')
            address = row.get('Address', 'Н/Д')
            text = row.get('Review Text', '')
            tags = row.get('Tags', '')
            rating = row.get('Rating', 0)
            
            # Обрезаем длинный текст
            if len(text) > 150:
                text = text[:150] + "..."
            
            report += f"\n{idx + 1}. <b>{city}</b> | {address}\n"
            report += f"   ⭐ {rating} | {tags}\n"
            report += f"   <i>\"{text}\"</i>\n"
    
    return report

async def send_report_async(df):
    """
    Асинхронная функция для отправки отчета всем подписчикам
    
    Args:
        df: DataFrame с новыми отзывами
    """
    config = load_config()
    bot_token = config.get("telegram_bot_token")
    
    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        print("⚠️ Bot token не настроен в config.json. Пропускаем отправку уведомлений.")
        return
    
    subscribers = load_subscribers()
    
    if not subscribers:
        print("⚠️ Нет подписчиков. Уведомления не отправлены.")
        return
    
    bot = Bot(token=bot_token)
    report = format_report(df)
    
    print(f"\n📨 Отправка отчета {len(subscribers)} подписчикам...")
    
    success_count = 0
    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=report,
                parse_mode=ParseMode.HTML
            )
            success_count += 1
            print(f"✅ Отправлено пользователю {chat_id}")
        except Exception as e:
            print(f"❌ Ошибка отправки пользователю {chat_id}: {e}")
    
    print(f"\n📬 Отчет отправлен {success_count}/{len(subscribers)} подписчикам")

def send_report(df):
    """
    Синхронная обертка для отправки отчета
    
    Args:
        df: DataFrame с новыми отзывами
    """
    try:
        asyncio.run(send_report_async(df))
    except Exception as e:
        print(f"❌ Ошибка при отправке уведомлений: {e}")
        import traceback
        traceback.print_exc()

