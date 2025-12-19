import pandas as pd
import json
import os
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import HumanMessage
import time

def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_llm():
    config = load_config()
    api_key = config.get('mistral_api_key')
    model = config.get('mistral_model', 'mistral-small-latest')
    return ChatMistralAI(api_key=api_key, model=model)

def check_service_topic(review_text, llm):
    """
    Check if a positive review is about service/customer service.
    """
    prompt = f"""Определи, относится ли этот ПОЗИТИВНЫЙ отзыв к теме "Обслуживание".

Тема "Обслуживание" включает:
- Хорошее/быстрое обслуживание
- Вежливые/добрые/профессиональные сотрудники
- Качество сервиса
- Помощь персонала

Отзыв:
{review_text}

Ответь ТОЛЬКО "ДА" или "НЕТ".
"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        answer = response.content.strip().upper()
        return "ДА" in answer or "YES" in answer
    except Exception as e:
        print(f"  Ошибка LLM: {e}")
        return False

def analyze_positive_service_reviews():
    csv_file = 'sberbank_all_reviews.csv'
    
    print(f"Загрузка {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Convert Date to datetime
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    
    # Filter positive reviews for 2025 with text
    positive_2025 = df[
        (df['Rating'] >= 4) &
        (df['Tags'] == '#Позитивное/без_комментария') &
        (df['Review Text'].notna()) &
        (df['Review Text'].str.strip() != '') &
        (df['Date'] >= '2025-01-01') &
        (df['Date'] <= '2025-12-31')
    ].copy()
    
    print(f"Найдено {len(positive_2025)} позитивных отзывов с текстом за 2025 год")
    print(f"Начинаем анализ через LLM...")
    
    llm = get_llm()
    service_count = 0
    
    for idx, (_, row) in enumerate(positive_2025.iterrows(), start=1):
        print(f"Обработка {idx}/{len(positive_2025)}...", end='\r')
        
        if check_service_topic(row['Review Text'], llm):
            service_count += 1
        
        # Rate limiting - wait after each request
        time.sleep(2)
    
    print(f"\n\n{'='*60}")
    print(f"РЕЗУЛЬТАТЫ:")
    print(f"{'='*60}")
    print(f"Всего позитивных отзывов с текстом за 2025: {len(positive_2025)}")
    print(f"Из них относятся к 'Обслуживанию': {service_count}")
    print(f"Процент: {service_count/len(positive_2025)*100:.1f}%")
    print(f"{'='*60}")

if __name__ == "__main__":
    analyze_positive_service_reviews()
