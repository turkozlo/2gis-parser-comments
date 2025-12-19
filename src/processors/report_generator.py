import pandas as pd

def generate_report_text(df):
    """
    Генерирует текст отчета по новым отзывам.
    
    Args:
        df (pd.DataFrame): DataFrame с новыми отзывами
        
    Returns:
        str: Текст отчета
    """
    if df.empty:
        return "📊 Отчет: Новых отзывов нет."

    # Фильтруем негативные отзывы (все, кроме #Позитивное/без_комментария)
    negative_df = df[df['Tags'] != '#Позитивное/без_комментария'].copy()
    total_negative = len(negative_df)
    total_reviews = len(df)
    
    report_lines = []
    report_lines.append("\n" + "="*50)
    report_lines.append(f"ОТЧЕТ ЗА ПЕРИОД")
    report_lines.append("="*50)
    report_lines.append(f"За отчётный период поступило {total_negative} плохих отзывов(всего {total_reviews})")

    if total_negative > 0:
        # 1. Темы отзывов
        all_tags = []
        for tags_str in negative_df['Tags']:
            if isinstance(tags_str, str):
                # Убираем решетки и разбиваем
                tags = [t.strip().replace('#', '') for t in tags_str.split(',')]
                all_tags.extend(tags)
        
        # Считаем топ тем с количеством
        from collections import Counter
        tag_counts = Counter(all_tags)
        # Формируем строку вида "тема(кол-во)"
        # Сортируем по убыванию количества
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        tags_formatted = [f"{tag.lower()}({count})" for tag, count in sorted_tags]
        
        report_lines.append(f"Темы отзывов - {', '.join(tags_formatted)}")

        # Функция для расчета рейтинга "худших"
        def calculate_worst(grouped_df):
            # Считаем общее кол-во и кол-во негативных
            stats = grouped_df.agg(
                total_count=('Tags', 'count'),
                negative_count=('Tags', lambda x: sum(x != '#Позитивное/без_комментария'))
            )
            # Считаем процент негатива
            stats['negative_ratio'] = stats['negative_count'] / stats['total_count']
            
            # Сортируем: сначала по % негатива (убывание), потом по кол-ву отзывов (убывание)
            # Чтобы "хуже то, где больше отзывов" при равном проценте
            stats = stats.sort_values(by=['negative_ratio', 'total_count'], ascending=[False, False])
            return stats

        # 2. Худшие ГОСБ
        # Группируем по ГОСБ весь датафрейм (чтобы учесть и позитивные для корректного соотношения)
        gosb_stats = calculate_worst(df.groupby('GOSB'))
        # Берем топ-3, но только те, где есть негатив
        worst_gosbs = gosb_stats[gosb_stats['negative_count'] > 0].head(3)
        
        worst_gosb_strings = []
        for name, row in worst_gosbs.iterrows():
            worst_gosb_strings.append(f"{name}({row['negative_count']}/{row['total_count']})")
            
        if worst_gosb_strings:
            report_lines.append(f"Худшие госбы - {', '.join(worst_gosb_strings)}")

        # 3. Худшие офисы
        # Создаем идентификатор офиса: Город, Адрес
        df['Office_ID'] = df['City'].astype(str) + ", " + df['Address'].astype(str)
        office_stats = calculate_worst(df.groupby('Office_ID'))
        worst_offices = office_stats[office_stats['negative_count'] > 0].head(3)
        
        worst_office_strings = []
        for name, row in worst_offices.iterrows():
            worst_office_strings.append(f"{name} ({row['negative_count']}/{row['total_count']})")
            
        if worst_office_strings:
            report_lines.append(f"Худшие офисы - {'; '.join(worst_office_strings)}")

        # 4. Офисы с наибольшим количеством негатива
        # Сортируем по количеству негативных отзывов (убывание)
        worst_offices_by_count = office_stats.sort_values(by=['negative_count', 'total_count'], ascending=[False, False]).head(3)
        # Исключаем те, у которых 0 негативных (на всякий случай)
        worst_offices_by_count = worst_offices_by_count[worst_offices_by_count['negative_count'] > 0]
        
        worst_office_count_strings = []
        for name, row in worst_offices_by_count.iterrows():
            worst_office_count_strings.append(f"{name} ({row['negative_count']}/{row['total_count']})")
            
        if worst_office_count_strings:
            report_lines.append(f"Офисы с наибольшим количеством негатива - {'; '.join(worst_office_count_strings)}")
            
            # Находим пример отзыва для самого худшего офиса
            worst_office_id = worst_offices.index[0]
            worst_office_reviews = df[df['Office_ID'] == worst_office_id]
            
            # Ищем негативные отзывы
            neg_reviews = worst_office_reviews[worst_office_reviews['Tags'] != '#Позитивное/без_комментария']
            
            if not neg_reviews.empty:
                # Пытаемся найти отзыв БЕЗ тега #Прочее
                meaningful_reviews = neg_reviews[~neg_reviews['Tags'].str.contains('#Прочее', na=False)]
                
                if not meaningful_reviews.empty:
                    example_review = meaningful_reviews.iloc[0]
                else:
                    # Если только #Прочее, берем любой негативный
                    example_review = neg_reviews.iloc[0]
                
                review_text = example_review['Review Text']
                # Обрезаем если слишком длинный
                if len(review_text) > 200:
                    review_text = review_text[:200] + "..."
                    
                report_lines.append(f"\nПример отзыва ({worst_office_id}):")
                report_lines.append(f"\"{review_text}\"")
                report_lines.append(f"Теги: {example_review['Tags']}")
            
    report_lines.append("="*50 + "\n")
    return "\n".join(report_lines)

def generate_console_report(df):
    """
    Генерирует и выводит в консоль отчет по новым отзывам.
    
    Args:
        df (pd.DataFrame): DataFrame с новыми отзывами
    """
    report_text = generate_report_text(df)
    print(report_text)
