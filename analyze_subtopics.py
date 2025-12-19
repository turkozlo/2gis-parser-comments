import pandas as pd
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.processors.topic_modeler import analyze_subtopics

def main():
    csv_file = 'sberbank_all_reviews.csv'
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        return
        
    print(f"Loading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Filter out empty tags
    df = df.dropna(subset=['Tags'])
    
    # Collect all reviews for each tag
    tag_reviews = {}
    
    print("Grouping reviews by tag...")
    for _, row in df.iterrows():
        tags_str = row['Tags']
        review_text = row['Review Text']
        
        if not isinstance(tags_str, str) or not isinstance(review_text, str):
            continue
            
        # Split tags (comma separated)
        tags = [t.strip().replace('#', '') for t in tags_str.split(',')]
        
        for tag in tags:
            # Skip empty tags
            if not tag:
                continue
                
            # Add '#' back for display
            full_tag = f"#{tag}"
            
            if full_tag not in tag_reviews:
                tag_reviews[full_tag] = []
            
            tag_reviews[full_tag].append(review_text)
            
    # Analyze each tag
    print(f"\nFound {len(tag_reviews)} unique tags.")
    
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("ANALYSIS OF SUB-TOPICS BY TAG")
    report_lines.append("=" * 60 + "\n")
    
    for tag, reviews in tag_reviews.items():
        count = len(reviews)
        print(f"\nAnalyzing tag: {tag} ({count} reviews)...")
        
        # Skip tags with very few reviews if needed, but for now process all
        if count < 3:
            print("  Skipping (too few reviews)")
            continue
            
        report_lines.append(f"TAG: {tag} ({count} reviews)")
        report_lines.append("-" * 40)
        
        try:
            results = analyze_subtopics(reviews, tag)
            
            if isinstance(results, dict):
                # Sort by count descending, but keep Other last
                other_count = results.pop('Other', 0)
                sorted_themes = sorted(results.items(), key=lambda x: x[1], reverse=True)
                
                for i, (theme, theme_count) in enumerate(sorted_themes):
                    if theme_count > 0:
                        report_lines.append(f"{i+1}. {theme} - {theme_count} отзывов")
                    
                if other_count > 0:
                    report_lines.append(f"\nНе вошло в топ-5 (Прочее): {other_count} отзывов")
            else:
                # Fallback for error string
                report_lines.append(str(results))
                
            print("  Done.")
        except Exception as e:
            error_msg = f"Error analyzing tag {tag}: {e}"
            print(f"  {error_msg}")
            report_lines.append(error_msg)
            
        report_lines.append("\n")
        
    # Save report
    report_file = 'subtopics_report.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
        
    print(f"\nAnalysis complete! Report saved to {report_file}")
    
    # Print report to console
    print("\n" + "="*60)
    print(open(report_file, 'r', encoding='utf-8').read())
    print("="*60)

if __name__ == "__main__":
    main()
