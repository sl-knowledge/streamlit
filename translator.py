import streamlit as st
import requests
import uuid
import time
from pypinyin import pinyin, Style
import jieba
from datetime import datetime
import plotly.graph_objects as go

class Translator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if not self.initialized:
            # Azure 配置
            self.azure_config = {
                'key': st.secrets.get("azure_translator", {}).get("key", ""),
                'region': st.secrets.get("azure_translator", {}).get("region", "southeastasia"),
                'endpoint': st.secrets.get("azure_translator", {}).get("endpoint", "https://api.cognitive.microsofttranslator.com")
            }
            # 将缓存移到类级别
            self.translated_words = {}
            self.initialized = True

    def translate_text(self, text, target_lang):
        """Translate text using Azure Translator"""
        cache_key = f"{text}_{target_lang}"
        
        # Check cache first
        if cache_key in self.translated_words:
            translation = self.translated_words[cache_key]
            # print(f"[Cache] '{text}' -> '{translation}'")  # Commented out for debugging
            return translation
        
        try:
            # Only call Azure if not in cache
            translation = self._call_azure_translate(text, target_lang)  # Actual API call
            self.translated_words[cache_key] = translation  # Update cache
            # print(f"[Azure] '{text}' -> '{translation}'")  # Commented out for debugging
            return translation
        except Exception as e:
            print(f"Translation error: {str(e)}")
            return ""

    def _call_azure_translate(self, text, target_lang):
        """Translate text using Azure Translator API"""
        endpoint = self.azure_config['endpoint']
        location = self.azure_config['region']
        key = self.azure_config['key']
        
        # Debug logging
        # print(f"Endpoint: {endpoint}")  # Commented out for debugging
        # print(f"Location: {location}")  # Commented out for debugging
        # print(f"Key exists: {bool(key)}")  # Commented out for debugging
        
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
            # Make the request
            response = requests.post(constructed_url, params=params, headers=headers, json=body)
            response.raise_for_status()  # This will raise an exception for bad status codes
            
            # Debug logging
            # print(f"Response status: {response.status_code}")  # Commented out for debugging
            # print(f"Response content: {response.text}")  # Commented out for debugging
            
            # Parse response with proper error checking
            response_json = response.json()
            if not response_json or not isinstance(response_json, list) or len(response_json) == 0:
                print("Invalid response format")
                return ""
            
            translations = response_json[0].get('translations', [])
            if not translations:
                print("No translations in response")
                return ""
            
            translation = translations[0].get('text', '')
            if translation:
                # print(f"Azure translated '{text}' to '{translation}'")  # Commented out for debugging
                return translation
            else:
                # print("No translated text found")  # Commented out for debugging
                return ""
            
        except requests.exceptions.RequestException as e:
            print(f"Request error: {str(e)}")
            return ""
        except (KeyError, IndexError, ValueError) as e:
            print(f"Response parsing error: {str(e)}")
            return ""
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
            
            # 使用类级别的缓存
            cache_key = f"{word}_{target_lang}"
            for word in words:
                try:
                    # Skip translation for punctuation and numbers
                    if (len(word.strip()) == 1 and not '\u4e00' <= word <= '\u9fff') or word.isdigit():
                        word_translations.append("")
                        continue
                    
                    # 检查缓存
                    cache_key = f"{word}_{target_lang}"
                    if cache_key in self.translated_words:
                        translation = self.translated_words[cache_key]
                        print(f"Cache hit: '{word}' -> '{translation}'")
                    else:
                        # Add delay between requests
                        time.sleep(0.5)
                        
                        # Translate using Azure
                        translation = self.translate_text(word, target_lang)
                        self.translated_words[cache_key] = translation  # 更新缓存
                        print(f"New translation: '{word}' -> '{translation}'")
                    
                    if translation:
                        word_translations.append(translation)
                    else:
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