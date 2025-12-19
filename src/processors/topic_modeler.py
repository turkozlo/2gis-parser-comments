import json
import os
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import HumanMessage

def load_config():
    # Assuming config.json is in the project root
    # We need to find the project root relative to this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    config_path = os.path.join(project_root, 'config.json')
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def get_llm():
    config = load_config()
    api_key = config.get('mistral_api_key')
    model = config.get('mistral_model', 'mistral-small-latest')
    
    if not api_key:
        raise ValueError("Mistral API key not found in config.json")
        
    return ChatMistralAI(api_key=api_key, model=model)

def _discover_themes(reviews, tag, chunk_size=30):
    """
    Phase 1: Discover top 5 themes.
    """
    llm = get_llm()
    chunks = [reviews[i:i + chunk_size] for i in range(0, len(reviews), chunk_size)]
    chunk_summaries = []
    
    print(f"  [Phase 1] Discovering themes in {len(chunks)} chunks...")
    
    for i, chunk in enumerate(chunks):
        reviews_text = "\n---\n".join(chunk)
        prompt = f"""
        Analyze the following reviews which are tagged with '{tag}'.
        Identify the top 5 distinct specific problems, themes, or sub-topics mentioned in these reviews.
        Focus on the negative aspects or specific issues if the tag implies problems.
        Return ONLY a bulleted list of sub-topics.
        IMPORTANT: The output MUST be in Russian language.
        
        Reviews:
        {reviews_text}
        """
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            chunk_summaries.append(response.content)
        except Exception as e:
            print(f"    Error processing chunk {i+1}: {e}")
            
    if not chunk_summaries:
        return []

    if len(chunks) > 1:
        combined_summaries = "\n\n".join(chunk_summaries)
        final_prompt = f"""
        Here are several lists of sub-topics identified from reviews tagged with '{tag}'.
        Consolidate these lists into a single, comprehensive list of EXACTLY 5 most important and distinct sub-topics.
        Merge similar items.
        Format the output as a clean bulleted list (just the text of the topics).
        IMPORTANT: The output MUST be in Russian language.
        
        Lists to consolidate:
        {combined_summaries}
        """
        try:
            final_response = llm.invoke([HumanMessage(content=final_prompt)])
            text = final_response.content
        except Exception as e:
            print(f"Error aggregating results: {e}")
            return []
    else:
        text = chunk_summaries[0]
        
    # Parse the bulleted list into a python list of strings
    themes = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('- ') or line.startswith('* '):
            themes.append(line[2:].strip())
        elif line and line[0].isdigit() and '. ' in line:
             # Handle numbered lists "1. Theme"
             parts = line.split('. ', 1)
             if len(parts) > 1:
                 themes.append(parts[1].strip())
    
    # Ensure we have at most 5
    return themes[:5]

def _count_themes(reviews, themes, chunk_size=30):
    """
    Phase 2: Count reviews for each theme.
    """
    if not themes:
        return {}
        
    llm = get_llm()
    chunks = [reviews[i:i + chunk_size] for i in range(0, len(reviews), chunk_size)]
    
    # Initialize counts
    total_counts = {theme: 0 for theme in themes}
    total_counts['Other'] = 0
    
    print(f"  [Phase 2] Counting reviews for {len(themes)} themes in {len(chunks)} chunks...")
    
    themes_list_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(themes)])
    
    for i, chunk in enumerate(chunks):
        print(f"    Processing chunk {i+1}/{len(chunks)}...")
        reviews_text = ""
        for idx, r in enumerate(chunk):
            reviews_text += f"Review {idx+1}: {r}\n"
            
        prompt = f"""
        You are a classifier. Here are {len(themes)} themes:
        {themes_list_str}
        
        Here are {len(chunk)} reviews:
        {reviews_text}
        
        For each review, determine which SINGLE theme index (1-{len(themes)}) it best belongs to. 
        If it does not fit any of the themes well, assign it to 0 (Other).
        
        Return ONLY a JSON object with the counts for this batch.
        Example format:
        {{
            "1": 5,
            "2": 3,
            "0": 1
        }}
        """
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            # Clean up markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            counts = json.loads(content)
            
            # Update total counts
            for key, val in counts.items():
                key = str(key)
                if key == "0":
                    total_counts['Other'] += val
                elif key.isdigit():
                    idx = int(key) - 1
                    if 0 <= idx < len(themes):
                        theme_name = themes[idx]
                        total_counts[theme_name] += val
                        
        except Exception as e:
            print(f"    Error counting chunk {i+1}: {e}")
            # If error, add all to Other to preserve total count roughly? 
            # Or just ignore. Let's add to Other to be safe.
            total_counts['Other'] += len(chunk)
            
    return total_counts

def analyze_subtopics(reviews, tag, chunk_size=30):
    """
    Analyzes reviews to find top 5 sub-topics and count them.
    Returns a dictionary: { 'Theme Name': count, ..., 'Other': count }
    """
    # Phase 1: Discover
    themes = _discover_themes(reviews, tag, chunk_size)
    if not themes:
        return {"Error": "Could not identify themes"}
        
    # Phase 2: Count
    counts = _count_themes(reviews, themes, chunk_size)
    
    return counts
