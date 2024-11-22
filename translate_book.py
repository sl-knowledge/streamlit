import translators.server as tss
import pypinyin
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, List
from functools import partial
from tqdm import tqdm
import sys
import time
import random
import jieba


def split_sentence(text: str) -> List[str]:
    """Split text into sentences or meaningful chunks"""
    print("Debug: Starting sentence split")  # 添加调试信息

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # 更复杂的分割模式，考虑引号和标点的组合
    pattern = r'([。！？，：；.!?,][」"』\'）)]*(?:\s*[「""『\'（(]*)?)'
    splits = re.split(pattern, text)

    print(f"Debug: Initial splits: {len(splits)}")  # 添加调试信息

    # 合并短句和处理引号
    chunks = []
    current_chunk = ""
    min_length = 20
    quote_count = 0  # 跟踪引号状态

    for i in range(0, len(splits)-1, 2):
        if splits[i]:
            chunk = splits[i] + (splits[i+1] if i+1 < len(splits) else '')

            # 计算当前块中的引号数量
            quote_count += chunk.count('"') + \
                chunk.count('"') + chunk.count('"')
            quote_count += chunk.count('「') + chunk.count('」')
            quote_count += chunk.count('『') + chunk.count('』')

            # 如果在引号内或当前块太短，继续累积
            if quote_count % 2 == 1 or (len(current_chunk) + len(chunk) < min_length and i < len(splits)-2):
                current_chunk += chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk + chunk)
                    current_chunk = ""
                else:
                    chunks.append(chunk)
                quote_count = 0  # 重置引号计数

    # 处理最后剩余的文本
    if splits[-1] or current_chunk:
        last_chunk = splits[-1] if splits[-1] else ""
        if current_chunk:
            chunks.append(current_chunk + last_chunk)
        elif last_chunk:
            chunks.append(last_chunk)

    # 清理并返回结果
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def convert_to_pinyin(text: str, style: str = 'tone_marks') -> str:
    """
    Convert Chinese text to pinyin with specified style
    style: 'tone_marks' (default) or 'tone_numbers'
    """
    try:
        # Select pinyin style based on parameter
        if style == 'tone_numbers':
            pinyin_style = pypinyin.TONE3
        else:  # default to tone marks
            pinyin_style = pypinyin.TONE

        # Convert to pinyin with selected style
        pinyin_list = pypinyin.pinyin(text, style=pinyin_style)
        # Flatten the list and join with spaces
        return ' '.join([item[0] for item in pinyin_list])
    except Exception as e:
        print(f"Error converting to pinyin: {e}")
        return "[Pinyin Error]"


def translate_text(text, dest, source='auto', max_retries=5):
    providers = {
        'google': lambda t, d, s: tss.google(t, to_language=d, from_language=s),
        'bing': lambda t, d, s: tss.bing(t, to_language=d, from_language=s),
        'baidu': lambda t, d, s: tss.baidu(t, to_language=d, from_language=s)
    }

    # 添加调试信息
    print(f"\nTrying to translate: {text[:50]}...")  # 只打印前50个字符

    # 将长文本分成小段进行翻译
    batch_size = 5
    words = text.split()
    translations = []
    
    for i in range(0, len(words), batch_size):
        batch = ' '.join(words[i:i + batch_size])
        
        for provider_name, translate_func in providers.items():
            retry_count = 0
            while retry_count < max_retries:
                try:
                    print(f"Attempting {provider_name} translation (attempt {retry_count + 1})")
                    time.sleep(random.uniform(2.0, 3.0))

                    translation = translate_func(batch, dest, source)

                    if translation and isinstance(translation, str):
                        translations.append(translation)
                        break
                    else:
                        print(f"{provider_name} returned invalid translation")

                except Exception as e:
                    print(f"{provider_name} failed: {str(e)}")
                    retry_count += 1
                    time.sleep(random.uniform(3.0, 5.0))
                    continue

                retry_count += 1
            
            if len(translations) == (i // batch_size + 1):
                # Successfully translated this batch
                break
        
        if len(translations) != (i // batch_size + 1):
            # All providers failed for this batch
            translations.append(f"[Translation failed] {batch}")

    # 合并所有翻译结果
    return ' '.join(translations)


def process_chunk(chunk: str, index: int, executor: ThreadPoolExecutor, include_english: bool, second_language: str, pinyin_style: str = 'tone_marks') -> tuple:
    try:
        # Get pinyin with specified style
        pinyin = convert_to_pinyin(chunk, pinyin_style)

        # Get translations
        translations = []
        if include_english:
            english = translate_text(chunk, 'en')
            translations.append(english)

        second_trans = translate_text(chunk, second_language)
        translations.append(second_trans)

        return (index, chunk, pinyin, *translations)

    except Exception as e:
        print(f"\nError processing chunk {index}: {e}")
        error_translations = ["[Translation Error]"] * \
            (1 + int(include_english))
        return (index, chunk, "[Pinyin Error]", *error_translations)


def create_html_block(results: tuple, include_english: bool) -> str:
    # Unpack results based on whether English is included
    if include_english:
        chunk, pinyin, english, second = results
        return f'''
            <div class="sentence-part">
                <div class="original">{chunk}</div>
                <div class="pinyin">{pinyin}</div>
                <div class="english">{english}</div>
                <div class="second-language">{second}</div>
            </div>
        '''
    else:
        chunk, pinyin, second = results
        return f'''
            <div class="sentence-part">
                <div class="original">{chunk}</div>
                <div class="pinyin">{pinyin}</div>
                <div class="second-language">{second}</div>
            </div>
        '''


def process_text(file_path, include_english=True, second_language="vi", pinyin_style='tone_marks'):
    """Process text with language options and pinyin style"""
    print("\nCounting total chunks...")
    with open(file_path, 'r', encoding='utf-8') as file:
        total_chunks = sum(len(split_sentence(line.strip()))
                           for line in file if line.strip())

    print(f"Found {total_chunks} chunks to process")
    print("Note: Processing may slow down occasionally to avoid rate limits")

    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    with open('template.html', 'r', encoding='utf-8') as template_file:
        html_content = template_file.read()

    translation_content = ''
    global_index = 0

    max_workers = 3

    pbar = tqdm(
        total=total_chunks,
        desc="Translating",
        unit="chunk",
        ncols=100,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
    )

    all_results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        for line_idx, line in enumerate(lines):
            if line.strip():
                chunks = split_sentence(line.strip())
                for chunk_idx, chunk in enumerate(chunks):
                    future = executor.submit(
                        process_chunk,
                        chunk,
                        global_index,
                        executor,
                        include_english,
                        second_language,
                        pinyin_style
                    )
                    futures.append((global_index, line_idx, chunk_idx, future))
                    global_index += 1

        for global_idx, line_idx, chunk_idx, future in futures:
            try:
                result = future.result(timeout=60)
                all_results.append((line_idx, chunk_idx, result))
                pbar.update(1)
            except Exception as e:
                print(f"\nError getting result: {e}")
                continue

    pbar.close()

    all_results.sort(key=lambda x: (x[0], x[1]))

    current_line = -1
    for line_idx, chunk_idx, result in all_results:
        if line_idx != current_line:
            if current_line != -1:
                translation_content += '</div>'
            translation_content += '<div class="translation-block">'
            current_line = line_idx

        # Pass include_english to create_html_block
        translation_content += create_html_block(result, include_english)

    if all_results:
        translation_content += '</div>'

    html_content = html_content.replace('{{content}}', translation_content)
    return html_content


def process_interactive_chunk(chunk: str, index: int, executor: ThreadPoolExecutor, include_english: bool, second_language: str, pinyin_style: str = 'tone_marks') -> tuple:
    """Process chunk for interactive word-by-word translation"""
    try:
        # 1. 先获取整句翻译，保持上下文
        full_translations = []
        if include_english:
            full_eng = translate_text(chunk, 'en')
            full_translations.append(full_eng)
        full_second = translate_text(chunk, second_language)
        full_translations.append(full_second)

        # 2. 使用jieba进行分词
        words = list(jieba.cut(chunk))
        
        # 3. 处理每个词
        word_data = []
        for word in words:
            if any('\u4e00' <= char <= '\u9fff' for char in word):
                # 获取拼音
                pinyin = convert_to_pinyin(word, pinyin_style)
                
                # 所有词都使用整句翻译的上下文，避免重复翻译
                word_data.append({
                    'word': word,
                    'pinyin': pinyin,
                    'translations': full_translations
                })
            else:
                # 非中文字符处理
                word_data.append({
                    'word': word,
                    'pinyin': '',
                    'translations': []
                })

        return (index, chunk, word_data)

    except Exception as e:
        print(f"\nError processing interactive chunk {index}: {e}")
        return (index, chunk, [])

def create_interactive_html_block(results: tuple, include_english: bool) -> str:
    """Create HTML for interactive word-by-word translation"""
    chunk, word_data = results
    words_html = []
    
    # 获取整句的翻译，用于显示在底部
    sentence_translations = []
    for data in word_data:
        if data['translations']:
            sentence_translations = data['translations']
            break
    
    # 处理每个词的HTML
    for data in word_data:
        if data['translations']:
            # 转义特殊字符
            translations_escaped = [t.replace('"', '&quot;').replace("'", "&#39;") for t in data['translations']]
            tooltip_content = f"{data['pinyin']}"
            if include_english:
                tooltip_content += f"\nEnglish: {translations_escaped[0]}"
            tooltip_content += f"\n{translations_escaped[-1]}"
            
            # 创建可交互的词
            word_html = f'''
                <span class="interactive-word" 
                      data-tooltip="{tooltip_content}"
                      onclick="speakWord(this.textContent)">
                    {data['word']}
                </span>'''
            words_html.append(word_html)
        else:
            # 处理非中文字符
            words_html.append(f'<span class="non-chinese">{data["word"]}</span>')

    # 构建完整的HTML块
    html = f'''
        <div class="translation-block">
            <div class="sentence-part interactive">
                <div class="original interactive-text">
                    <span class="sentence-index"></span>
                    <span class="original-text">{''.join(words_html)}</span>
                    <button class="speaker-button" onclick="speak(this.previousElementSibling.textContent)">
                        <div class="speaker-icon"></div>
                    </button>
                </div>
            </div>
        </div>
    '''
    
    return html

def translate_file(input_file: str, progress_callback=None, include_english=True, second_language="vi", pinyin_style='tone_marks', translation_mode="Standard Translation"):
    """
    Translate file with progress updates, language options and pinyin style
    """
    print(f"Starting translation of {input_file}")
    print(f"Translation mode: {translation_mode}")

    try:
        with open(input_file, 'r', encoding='utf-8') as file:
            text = file.read().strip()

        with open('template.html', 'r', encoding='utf-8') as template_file:
            html_content = template_file.read()

        translation_content = ''

        if translation_mode == "Interactive Word-by-Word":
            # 直接处理整个文本
            result = process_interactive_chunk(
                text, 0, None, include_english, second_language, pinyin_style
            )
            _, _, word_data = result
            translation_content = create_interactive_html_block(
                (text, word_data), include_english)
        else:
            # 使用原有的标准翻译模式
            chunks = split_sentence(text)
            total_chunks = len(chunks)
            chunks_processed = 0

            for chunk in chunks:
                result = process_chunk(
                    chunk, chunks_processed, None, 
                    include_english, second_language, pinyin_style
                )
                if include_english:
                    _, chunk, pinyin, english, second = result
                    translation_content += create_html_block(
                        (chunk, pinyin, english, second), include_english=True)
                else:
                    _, chunk, pinyin, second = result
                    translation_content += create_html_block(
                        (chunk, pinyin, second), include_english=False)
                
                chunks_processed += 1
                if progress_callback:
                    progress = (chunks_processed / total_chunks) * 100
                    progress_callback(progress)

        html_content = html_content.replace('{{content}}', translation_content)
        output_file = f"{os.path.splitext(input_file)[0]}.html"
        
        with open(output_file, 'w', encoding='utf-8-sig') as file:
            file.write(html_content)

        if progress_callback:
            progress_callback(100)

        print("Translation completed!")

    except Exception as e:
        print(f"Translation error: {str(e)}")
        raise

def main():
    """Main entry point for command line usage"""
    if len(sys.argv) != 2:
        print("Usage: python tranlate_book.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found")
        sys.exit(1)

    translate_file(input_file)


if __name__ == "__main__":
    main()
