import pandas as pd
import os
import sys
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.processors.subtopic_classifier import classify_batch

def backfill_subtopics():
    csv_file = 'sberbank_all_reviews.csv'
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        return
        
    print(f"Loading {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Check if Sub_tag column exists, if not create it
    if 'Sub_tag' not in df.columns:
        df['Sub_tag'] = ""
    
    # Identify rows that need processing (non-empty tags, empty sub_tag)
    # We treat NaN as empty string for filtering
    df['Sub_tag'] = df['Sub_tag'].fillna("")
    
    # Filter: Has tags AND Sub_tag is empty
    to_process_mask = (df['Tags'].notna()) & (df['Tags'] != "") & (df['Sub_tag'] == "")
    total_to_process = to_process_mask.sum()
    
    print(f"Found {total_to_process} reviews to backfill.")
    
    if total_to_process == 0:
        print("Nothing to do.")
        return

    # Process in batches
    batch_size = 30
    indices = df[to_process_mask].index.tolist()
    
    processed_count = 0
    
    try:
        for i in range(0, len(indices), batch_size):
            batch_indices = indices[i:i+batch_size]
            batch_data = []
            
            for idx in batch_indices:
                row = df.loc[idx]
                tags = row['Tags']
                # Take first tag
                primary_tag = tags.split(',')[0].strip()
                
                batch_data.append({
                    'id': idx,
                    'text': row['Review Text'],
                    'tag': primary_tag
                })
            
            print(f"Processing batch {i//batch_size + 1}/{(len(indices)-1)//batch_size + 1} ({len(batch_data)} reviews)...")
            
            # Retry logic
            max_retries = 3
            retry_delay = 5
            
            for attempt in range(max_retries):
                try:
                    # Call classifier
                    results = classify_batch(batch_data)
                    
                    # Update DataFrame
                    for idx, sub_topic in results.items():
                        df.at[idx, 'Sub_tag'] = sub_topic
                    
                    # If successful, break retry loop
                    break
                except Exception as e:
                    print(f"  Attempt {attempt+1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        print(f"  Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    else:
                        print(f"  Skipping batch after {max_retries} failures.")

            processed_count += len(batch_data)
            
            # Save periodically (every 5 batches)
            if (i // batch_size) % 5 == 0:
                df.to_csv(csv_file, index=False)
                print(f"  Saved progress ({processed_count}/{total_to_process})")
                
            # Rate limit: 2 seconds between batches
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nStopping backfill...")
    except Exception as e:
        print(f"\nError during backfill: {e}")
    finally:
        # Final save
        df.to_csv(csv_file, index=False)
        print(f"Final save completed. Processed {processed_count} reviews.")

if __name__ == "__main__":
    backfill_subtopics()
