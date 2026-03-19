import json
import os
from langchain_mistralai import ChatMistralAI
from langchain_core.messages import HumanMessage

def load_config():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    config_path = os.path.join(project_root, 'config.json')
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)

    return {}

def load_subtopics():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    subtopics_path = os.path.join(project_root, 'subtopics.json')
    
    if os.path.exists(subtopics_path):
        with open(subtopics_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def get_llm():
    config = load_config()
    api_key = config.get('mistral_api_key')
    model = config.get('mistral_model', 'mistral-small-latest')
    
    if not api_key:
        raise ValueError("Mistral API key not found in config.json")
        
    return ChatMistralAI(api_key=api_key, model=model)

def classify_review(review_text, tag):
    """
    Classifies a single review into one of the sub-topics for the given tag.
    Returns the sub-topic name or "Прочее".
    """
    subtopics_map = load_subtopics()
    
    # Normalize tag (ensure it has #)
    if not tag.startswith('#'):
        tag = f"#{tag}"
        
    themes = subtopics_map.get(tag)
    
    if not themes:
        return "" # No subtopics for this tag
        
    llm = get_llm()
    
    themes_list_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(themes)])
    
    prompt = f"""You are a classifier. Return ONLY a number.
Tag: {tag}
Themes:
{themes_list_str}

Review:
{review_text}

Classify this review into ONE of the themes above.
Return ONLY the index number (1-{len(themes)}) or 0 for Other.
Do not include any explanations or additional text.
"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Robust number extraction
        import re
        match = re.search(r'\d+', content)
        if match:
            idx = int(match.group(0))
            if idx == 0:
                return "Прочее"
            elif 1 <= idx <= len(themes):
                return themes[idx-1]
                
        return "Прочее"
        
    except Exception as e:
        print(f"Error classifying review: {e}")
        if 'content' in locals():
            print(f"  Response snippet: {content[:100]}...")
        return "Ошибка"

def classify_batch(reviews_data):
    """
    Classifies a batch of reviews.
    Args:
        reviews_data: List of dicts {'id': id, 'text': text, 'tag': tag}
    Returns:
        Dict {id: sub_topic}
    """
    # Group by tag to optimize prompts
    by_tag = {}
    for item in reviews_data:
        tag = item['tag']
        if not tag: continue
        if tag not in by_tag: by_tag[tag] = []
        by_tag[tag].append(item)
        
    results = {}
    subtopics_map = load_subtopics()
    llm = get_llm()
    
    for tag, items in by_tag.items():
        # Normalize tag
        lookup_tag = tag if tag.startswith('#') else f"#{tag}"
        themes = subtopics_map.get(lookup_tag)
        
        if not themes:
            for item in items:
                results[item['id']] = ""
            continue
            
        themes_list_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(themes)])
        
        # Process in smaller chunks if needed, but for batch of 30 mixed tags it's fine
        # Construct prompt for multiple items
        reviews_block = ""
        for i, item in enumerate(items):
            reviews_block += f"Review {i+1}: {item['text']}\n"
            
        prompt = f"""
        You are a classifier.
        Tag: {tag}
        Themes:
        {themes_list_str}
        
        Reviews:
        {reviews_block}
        
        Classify EACH review into ONE of the themes above.
        Return a JSON object where keys are "1", "2", etc. (corresponding to Review 1, Review 2...) and values are the theme index (1-{len(themes)} or 0 for Other).
        Example: {{"1": 2, "2": 0, "3": 1}}
        """
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            # Robust JSON extraction using regex
            import re
            # First, try to extract JSON object
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                json_str = json_match.group(0)
            else:
                # Fallback: clean markdown
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                json_str = content.strip()
            
            mapping = json.loads(json_str)
            
            for i, item in enumerate(items):
                key = str(i+1)
                theme_idx = mapping.get(key, 0)
                
                if theme_idx == 0:
                    sub_topic = "Прочее"
                elif isinstance(theme_idx, int) and 1 <= theme_idx <= len(themes):
                    sub_topic = themes[theme_idx-1]
                else:
                    sub_topic = "Прочее"
                    
                results[item['id']] = sub_topic
                
        except Exception as e:
            print(f"Error classifying batch for tag {tag}: {e}")
            if 'content' in locals():
                print(f"  Response snippet: {content[:150]}...")
            for item in items:
                results[item['id']] = "Ошибка"
                
    return results
