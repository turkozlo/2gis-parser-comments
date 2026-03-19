import pandas as pd
from playwright.sync_api import sync_playwright
import time
import re
import datetime
import os
import sys
import argparse
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.sentiment_analyzer import analyze_tags
from src.telegram_notifier import send_report, process_subscriptions
from src.processors.gosb_mapper import get_gosb
from src.processors.report_generator import generate_console_report

def parse_date(date_str):
    if not date_str:
        return ""
    
    # Remove "edited" suffixes
    date_str = date_str.replace(", отредактирован", "").replace(", edited", "").strip()
    
    # Handle "today" and "yesterday"
    today = datetime.date.today()
    if date_str.lower() == "сегодня" or date_str.lower() == "today":
        return today.strftime("%Y-%m-%d")
    if date_str.lower() == "вчера" or date_str.lower() == "yesterday":
        return (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
    # Month mappings
    months = {
        'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04', 'мая': '05', 'июня': '06',
        'июля': '07', 'августа': '08', 'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12',
        'january': '01', 'february': '02', 'march': '03', 'april': '04', 'may': '05', 'june': '06',
        'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    try:
        parts = date_str.split()
        if len(parts) == 3:
            day = parts[0]
            month_str = parts[1].lower()
            year = parts[2]
            
            if month_str in months:
                month = months[month_str]
                # Ensure day is 2 digits
                day = day.zfill(2)
                return f"{year}-{month}-{day}"
    except Exception as e:
        print(f"Error parsing date '{date_str}': {e}")
        
    return date_str

def parse_reviews(start_date, end_date):
    input_csv = 'sberbank_DVB_VSP.csv'
    output_csv = f'sberbank_reviews_{start_date}_to_{end_date}.csv'  # Dedicated file for selected period
    
    # Обработка новых подписчиков (все /start команды что пришли пока бот был выключен)
    print("=" * 60)
    print("ОБРАБОТКА ПОДПИСОК")
    print("=" * 60)
    process_subscriptions()
    
    print("\n" + "=" * 60)
    print(f"ПАРСИНГ ОТЗЫВОВ (С {start_date} ПО {end_date})")
    print("=" * 60 + "\n")
    
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print(f"File {input_csv} not found.")
        return

    # Для этого запуска мы НЕ загружаем старые отзывы, чтобы файл был чистым
    branch_latest_dates = {}
    print(f"Парсинг будет сохранен в НОВЫЙ файл: {output_csv}", flush=True)

    all_reviews = []

    with sync_playwright() as p:
        # Запускаем браузер с аргументами для обхода детектирования (БЕЗ slow_mo)
        browser = p.chromium.launch(
            headless=False,

            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        
        # Создаем контекст с настройками реального браузера
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            locale='ru-RU',
            timezone_id='Asia/Vladivostok'
        )
        
        page = context.new_page()
        
        # Скрываем webdriver флаг
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        for index, row in df.iterrows():
            # Фильтрация: обрабатываем только отделения Сбера
            branch_name = row.get('Наименование', '')
            if not pd.isna(branch_name) and 'сбер' not in branch_name.lower():
                continue
            
            url = row['2GIS URL']
            if pd.isna(url):
                continue
            
            # Получаем последнюю известную дату для этого отделения
            latest_known_date = branch_latest_dates.get(url, None)
            if latest_known_date:
                print(f"  Последняя известная дата для этого отделения: {latest_known_date}", flush=True)
            
            # Extract branch info from CSV
            branch_city = row.get('Город', '')
            branch_address = row.get('Адрес', '')
            
            reviews_url = f"{url}/tab/reviews"
            print(f"\n[{index + 1}/{len(df)}] Processing: {reviews_url}", flush=True)
            print(f"  City: {branch_city}, Address: {branch_address}", flush=True)
            
            try:
                page.goto(reviews_url, timeout=60000)
                
                # Check if captcha is present
                captcha_present = page.locator('form[action="/form"]').count() > 0
                
                if captcha_present:
                    print("⚠️  CAPTCHA detected! Please solve it in the browser window...", flush=True)
                    print("Waiting for you to solve the captcha...", flush=True)
                    page.wait_for_selector('div._1k5soqfl', timeout=300000)
                    print("✓ Captcha solved! Continuing...", flush=True)
                else:
                    page.wait_for_selector('div._1k5soqfl', timeout=10000)
                
                # Scroll to load more reviews
                print("Loading reviews...", flush=True)
                for i in range(10):
                    page.mouse.wheel(0, 3000)
                    time.sleep(0.5)
                
                # Get total number of reviews
                reviews = page.query_selector_all('div._1k5soqfl')
                total_reviews = len(reviews)
                print(f"Found {total_reviews} reviews. Parsing...", flush=True)

                # Use index-based iteration to avoid stale elements
                for rev_index in range(total_reviews):
                    # Re-query reviews each time to avoid stale elements
                    reviews = page.query_selector_all('div._1k5soqfl')
                    if rev_index >= len(reviews):
                        print(f"  [Review {rev_index + 1}] Review not found, skipping", flush=True)
                        continue
                        
                    review = reviews[rev_index]
                    try:
                        # Review Text
                        text_el = review.query_selector('a._1msln3t')
                        text = text_el.inner_text() if text_el else ""
                        
                        # Rating - count filled stars
                        rating_container = review.query_selector('div._1fkin5c')
                        rating = 0
                        if rating_container:
                            filled_stars = rating_container.query_selector_all('svg[fill="#ffb81c"]')
                            rating = len(filled_stars)
                        
                        # Date
                        date_el = review.query_selector('div._a5f6uz')
                        date_text = date_el.inner_text() if date_el else ""
                        date = parse_date(date_text)
                        
                        # Username
                        user_el = review.query_selector('span._16s5yj36')
                        username = user_el.inner_text() if user_el else ""
                        
                        # User ID - click on avatar to open profile
                        user_id = ""
                        print(f"  [Review {rev_index}] Username: {username}", flush=True)
                        
                        # Find avatar element
                        avatar = review.query_selector('div._1dk5lq4')
                        print(f"  [Review {rev_index}] Avatar found: {avatar is not None}", flush=True)
                        
                        if avatar:
                            try:
                                # Click on the avatar to open user profile
                                print(f"  [Review {rev_index}] Clicking on avatar...", flush=True)
                                avatar.click()
                                # Wait for SPA navigation
                                time.sleep(1)
                                
                                # Get URL using JavaScript (page.url doesn't update for SPA navigation!)
                                profile_url = page.evaluate("window.location.href")
                                print(f"  [Review {rev_index}] Current URL: {profile_url}", flush=True)
                                
                                # Extract user ID from URL like https://2gis.ru/khabarovsk/user/d3af698ec4804f75879f1cd8ff82b5f2
                                match = re.search(r'/user/([a-f0-9]+)', profile_url)
                                if match:
                                    user_id = match.group(1)
                                    print(f"  [Review {rev_index}] User ID extracted: {user_id}", flush=True)
                                else:
                                    print(f"  [Review {rev_index}] Could not extract User ID from URL", flush=True)
                                
                                # Navigate back to reviews page
                                print(f"  [Review {rev_index}] Navigating back...", flush=True)
                                page.go_back()
                                time.sleep(1)
                                
                            except Exception as e:
                                print(f"  [Review {rev_index}] Error extracting user ID: {e}", flush=True)
                                # Try to go back if we're stuck
                                try:
                                    page.go_back()
                                    time.sleep(1)
                                except:
                                    pass
                        else:
                            print(f"  [Review {rev_index}] No avatar found in review", flush=True)

                        # ФИЛЬТР ПО ДАТЕ
                        if date:
                            if date > end_date:
                                print(f"  [Review {rev_index}] Отзыв новее {end_date} ({date}), пропускаем...", flush=True)
                                continue
                            if date < start_date:
                                print(f"  [Review {rev_index}] Достигнута дата до {start_date} ({date}), останавливаем парсинг этого отделения", flush=True)
                                break
                        
                        # ОПТИМИЗАЦИЯ: Временно закомментирована для полного парсинга января
                        # if latest_known_date and date:
                        #     if date <= latest_known_date:
                        #         print(f"  [Review {rev_index}] Достигнута известная дата ({date} <= {latest_known_date}), останавливаем парсинг этого отделения", flush=True)
                        #         break

                        
                        # Анализ тегов через Mistral API
                        print(f"  [Review {rev_index}] Определяем теги...", flush=True)
                        tags = analyze_tags(text)
                        
                        # --- NEW: Sub-topic Classification ---
                        from src.processors.subtopic_classifier import classify_review
                        # We classify based on the first/primary tag
                        primary_tag = tags.split(',')[0].strip() if tags else ""
                        sub_tag = classify_review(text, primary_tag)
                        print(f"  [Review {rev_index}] Tags: {tags} | Sub-tag: {sub_tag}", flush=True)
                        # -------------------------------------
                        
                        all_reviews.append({
                            'Branch URL': url,
                            'City': branch_city,
                            'Address': branch_address,
                            'Review Text': text,
                            'Rating': rating,
                            'Date': date,
                            'Username': username,
                            'User ID': user_id,
                            'Tags': tags,
                            'Sub_tag': sub_tag
                        })
                        
                    except Exception as e:
                        print(f"Error parsing review: {e}", flush=True)
                        continue

            except Exception as e:
                print(f"Error processing URL {url}: {e}", flush=True)
                continue
        
        context.close()
        browser.close()

    # Сохраняем ТОЛЬКО новые отзывы за выбранный период
    if all_reviews:
        new_reviews_df = pd.DataFrame(all_reviews)
        final_df = new_reviews_df
        print(f"Подготовлено {len(final_df)} отзывов за период {start_date} - {end_date}", flush=True)
        
        # Добавляем колонку GOSB (нужно и для отчета, и для сохранения)
        print("Обновление колонки GOSB...", flush=True)
        # Применяем к new_reviews_df тоже, чтобы отчет был корректным
        new_reviews_df['GOSB'] = new_reviews_df['City'].apply(get_gosb)
        final_df['GOSB'] = final_df['City'].apply(get_gosb)
        
        # Генерируем отчет по НОВЫМ отзывам
        from src.processors.report_generator import generate_report_text
        report_text = generate_report_text(new_reviews_df)
        print(report_text)
        
        # Генерируем хитмапу по НОВЫМ отзывам
        heatmap_path = None
        print("\n📊 Генерация хитмапы по новым данным...", flush=True)
        try:
            from generate_heatmap import generate_heatmap
            heatmap_path = generate_heatmap(new_reviews_df)
        except Exception as e:
            print(f"⚠️ Ошибка генерации хитмапы: {e}", flush=True)
        
        # Сохраняем итоговый файл
        final_df.to_csv(output_csv, index=False)
        print(f"Сохранено {len(final_df)} отзывов в {output_csv}", flush=True)
        
        # Отправка уведомлений в Telegram
        print("\n📨 Отправка уведомлений в Telegram...", flush=True)
        try:
            send_report(new_reviews_df)
        except Exception as e:
            print(f"⚠️ Ошибка отправки уведомлений: {e}", flush=True)

        # Отправка отчета на Email
        print("\n📧 Отправка отчета на Email...", flush=True)
        try:
            from src.email_notifier import send_email_report
            attachments = [output_csv]
            if heatmap_path and os.path.exists(heatmap_path):
                attachments.append(heatmap_path)
            send_email_report(report_text, attachments)
        except Exception as e:
            print(f"⚠️ Ошибка отправки Email: {e}", flush=True)
    else:
        print("Нет новых отзывов для добавления", flush=True)

def get_date_range():
    parser = argparse.ArgumentParser(description="Парсер отзывов 2GIS")
    parser.add_argument("--start", type=str, help="Начальная дата (ГГГГ-ММ-ДД)")
    parser.add_argument("--end", type=str, help="Конечная дата (ГГГГ-ММ-ДД)")
    
    args, _ = parser.parse_known_args()
    
    start_date = args.start
    end_date = args.end
    
    if not start_date:
        start_date = input("Введите начальную дату (ГГГГ-ММ-ДД, например 2026-01-01): ").strip()
    if not end_date:
        end_date = input("Введите конечную дату (ГГГГ-ММ-ДД, например 2026-01-31): ").strip()
        
    try:
        datetime.datetime.strptime(start_date, "%Y-%m-%d")
        datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        print("Ошибка: Неверный формат даты. Используйте ГГГГ-ММ-ДД!")
        sys.exit(1)
        
    return start_date, end_date

if __name__ == "__main__":
    start_date, end_date = get_date_range()
    parse_reviews(start_date, end_date)
