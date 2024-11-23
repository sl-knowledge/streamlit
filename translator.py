import streamlit as st
import requests
import uuid
import time
from pypinyin import pinyin, Style
import jieba
from datetime import datetime
import plotly.graph_objects as go

class Translator:
    def __init__(self):
        # Azure 配置
        self.azure_config = {
            'key': st.secrets.get("azure_translator", {}).get("key", ""),
            'region': st.secrets.get("azure_translator", {}).get("region", "southeastasia"),
            'endpoint': st.secrets.get("azure_translator", {}).get("endpoint", "https://api.cognitive.microsofttranslator.com")
        }

    def translate_text(self, text, target_lang):
        """使用 Azure Translator 进行翻译"""
        endpoint = self.azure_config['endpoint']
        location = self.azure_config['region']
        key = self.azure_config['key']
        
        path = '/translate'
        constructed_url = endpoint + path
        
        headers = {
            'Ocp-Apim-Subscription-Key': key,
            'Ocp-Apim-Subscription-Region': location,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        
        body = [{
            'text': text
        }]
        
        params = {
            'api-version': '3.0',
            'from': 'zh-Hans',
            'to': target_lang
        }
        
        try:
            response = requests.post(constructed_url, params=params, headers=headers, json=body)
            response.raise_for_status()
            translation = response.json()[0]['translations'][0]['text']
            print(f"Azure translated '{text}' to '{translation}'")
            return translation
        except Exception as e:
            print(f"Azure translation error: {str(e)}")
            return ""

    def process_chinese_text(self, text, target_lang="en"):
        """Process Chinese text for word-by-word translation"""
        try:
            # Segment the text using jieba
            words = list(jieba.cut(text))
            
            # Get pinyin for each word
            word_pinyins = []
            for word in words:
                try:
                    char_pinyins = []
                    for char in word:
                        try:
                            char_pinyin = pinyin(char, style=Style.TONE)[0][0]
                            char_pinyins.append(char_pinyin)
                        except Exception as e:
                            print(f"Error getting pinyin for char '{char}': {str(e)}")
                            char_pinyins.append("")
                    word_pinyins.append(' '.join(char_pinyins))
                except Exception as e:
                    print(f"Error processing word '{word}' for pinyin: {str(e)}")
                    word_pinyins.append("")
            
            # Get translations using Azure
            word_translations = []
            translated_words = {}  # 缓存已翻译的词
            
            for word in words:
                try:
                    # Skip translation for punctuation and numbers
                    if (len(word.strip()) == 1 and not '\u4e00' <= word <= '\u9fff') or word.isdigit():
                        word_translations.append("")
                        continue
                    
                    # 检查是否已翻译过这个词
                    if word in translated_words:
                        translation = translated_words[word]
                    else:
                        # Add delay between requests
                        time.sleep(0.5)
                        
                        # Translate using Azure
                        translation = self.translate_text(word, target_lang)
                        translated_words[word] = translation  # 缓存翻译结果
                    
                    if translation:
                        print(f"Word: '{word}' -> '{translation}'")  # 只打印一次
                        word_translations.append(translation)
                    else:
                        print(f"Translation failed for '{word}'")
                        word_translations.append("")
                    
                except Exception as e:
                    print(f"Translation error for word '{word}': {str(e)}")
                    word_translations.append("")
            
            # Combine results
            processed_words = []
            for i, (word, pinyin_text, translation) in enumerate(zip(words, word_pinyins, word_translations)):
                try:
                    if '\u4e00' <= word <= '\u9fff':
                        processed_words.append({
                            'word': word,
                            'pinyin': pinyin_text,
                            'translations': [translation] if translation else []
                        })
                    else:
                        processed_words.append({
                            'word': word,
                            'pinyin': '',
                            'translations': []
                        })
                except Exception as e:
                    print(f"Error combining results for word at index {i}: {str(e)}")
                    processed_words.append({
                        'word': word,
                        'pinyin': '',
                        'translations': []
                    })
            
            return processed_words
            
        except Exception as e:
            print(f"Error processing text: {str(e)}")
            return None