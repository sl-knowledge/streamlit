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


def translate_text(text, dest, max_retries=5):
    providers = {
        'google': lambda t, d: tss.google(t, to_language=d),  # 首选 Google
        'bing': lambda t, d: tss.bing(t, to_language=d),      # 备选 Bing
        'baidu': lambda t, d: tss.baidu(t, to_language=d)     # 备选 Baidu
    }

    # 添加调试信息
    print(f"\nTrying to translate: {text[:50]}...")  # 只打印前50个字符

    for provider_name, translate_func in providers.items():
        retry_count = 0
        while retry_count < max_retries:
            try:
                print(
                    f"Attempting {provider_name} translation (attempt {retry_count + 1})")
                time.sleep(random.uniform(2.0, 3.0))

                translation = translate_func(text, dest)

                if translation and isinstance(translation, str) and len(translation) >= len(text) * 0.3:
                    print(f"Successfully translated using {provider_name}")
                    return translation.strip()
                else:
                    print(f"{provider_name} returned invalid translation")

            except Exception as e:
                print(f"{provider_name} failed: {str(e)}")
                retry_count += 1
                time.sleep(random.uniform(3.0, 5.0))
                continue

            retry_count += 1

    print("All translation providers failed")
    return f"[Translation failed] {text}"


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


def translate_file(input_file: str, progress_callback=None, include_english=True, second_language="vi", pinyin_style='tone_marks'):
    """
    Translate file with progress updates, language options and pinyin style
    pinyin_style: 'tone_marks' or 'tone_numbers'
    """
    print(f"Starting translation of {input_file}")
    print(f"Pinyin style: {pinyin_style}")

    try:
        # Count total chunks first for progress calculation
        print("\nCounting total chunks...")
        with open(input_file, 'r', encoding='utf-8') as file:
            total_chunks = sum(len(split_sentence(line.strip()))
                               for line in file if line.strip())

        print(f"Found {total_chunks} chunks to process")

        with open(input_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        with open('template.html', 'r', encoding='utf-8') as template_file:
            html_content = template_file.read()

        translation_content = ''
        global_index = 0
        chunks_processed = 0

        max_workers = 3
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
                        futures.append(
                            (global_index, line_idx, chunk_idx, future))
                        global_index += 1

            for global_idx, line_idx, chunk_idx, future in futures:
                try:
                    result = future.result(timeout=60)
                    all_results.append((line_idx, chunk_idx, result))
                    chunks_processed += 1

                    # Update progress if callback provided
                    if progress_callback:
                        progress = (chunks_processed / total_chunks) * 100
                        progress_callback(progress)

                except Exception as e:
                    print(f"\nError getting result: {e}")
                    continue

        all_results.sort(key=lambda x: (x[0], x[1]))

        current_line = -1
        for line_idx, chunk_idx, result in all_results:
            if line_idx != current_line:
                if current_line != -1:
                    translation_content += '</div>'
                translation_content += '<div class="translation-block">'
                current_line = line_idx

            # Handle result unpacking more safely
            try:
                if include_english:
                    _, chunk, pinyin, english, second = result
                    translation_content += create_html_block(
                        (chunk, pinyin, english, second), include_english=True)
                else:
                    _, chunk, pinyin, second = result
                    translation_content += create_html_block(
                        (chunk, pinyin, second), include_english=False)
            except ValueError as e:
                print(f"Error unpacking result: {e}")
                # Create error block
                translation_content += create_html_block(
                    (chunk, "[Pinyin Error]",
                     "[Translation Error]", "[Translation Error]"),
                    include_english=include_english
                )

        if all_results:
            translation_content += '</div>'

        html_content = html_content.replace('{{content}}', translation_content)

        base_name = os.path.splitext(input_file)[0]
        output_file = f"{base_name}.html"
        print(f"\nSaving output to {output_file}")

        # Explicitly specify UTF-8 encoding with BOM for better mobile compatibility
        with open(output_file, 'w', encoding='utf-8-sig') as file:
            file.write(html_content)

        # Final progress update
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
