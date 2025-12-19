import pandas as pd

def filter_sberbank(input_csv, output_csv):
    """
    Фильтрует данные, оставляя только отделения Сбербанка
    
    Args:
        input_csv: путь к входному CSV файлу
        output_csv: путь к выходному CSV файлу
    """
    # Read the full file
    df = pd.read_csv(input_csv)
    
    print(f"Total rows in file: {len(df)}")
    print(f"\nColumns: {df.columns.tolist()}")
    
    # Filter only Sberbank branches (СберБанк, СберПервый, Сбер)
    sber_df = df[df['Наименование'].str.contains('Сбер', case=False, na=False)]
    
    print(f"\nSberbank branches found: {len(sber_df)}")
    
    # Save to new file
    sber_df.to_csv(output_csv, index=False)
    
    print(f"\nSaved to: {output_csv}")
    print(f"\nFirst few entries:")
    print(sber_df[['Наименование', 'Адрес', 'Город', '2GIS URL']].head(10))
    
    return sber_df

if __name__ == "__main__":
    import os
    
    # Определяем пути относительно корня проекта
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    input_file = os.path.join(project_root, 'data', 'input', 'DVB_banks_2gis.csv')
    output_file = os.path.join(project_root, 'sberbank_DVB_VSP.csv')
    
    filter_sberbank(input_file, output_file)
