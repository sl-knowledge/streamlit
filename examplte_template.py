import os
import markdown
from jinja2 import Template
import re
from urllib.parse import urlparse, parse_qs
import translators as ts
import jieba
from pypinyin import pinyin, Style
import html
import concurrent.futures
from typing import List, Tuple, Dict
import time
from collections import OrderedDict

# Configuration
MAX_TRANSLATION_WORKERS = 5
MAX_PINYIN_WORKERS = 5
MAX_LINE_WORKERS = 8

WORD_BY_WORD_TRANSLATION = True
GENERATE_PINYIN = True

# 缓存
TRANSLATION_CACHE: Dict[str, str] = {}
PINYIN_CACHE: Dict[str, str] = {}

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    if not url:
        return ""
    parsed_url = urlparse(url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path.lstrip('/')
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query).get('v', [''])[0]
        if parsed_url.path.startswith(('/embed/', '/v/')):
            return parsed_url.path.split('/')[2]
    return ""

def generate_pinyin(text: str) -> str:
    """Generate pinyin for Chinese text with caching."""
    if text in PINYIN_CACHE:
        return PINYIN_CACHE[text]

    try:
        result = ' '.join([p[0] for p in pinyin(text, style=Style.TONE)])
        PINYIN_CACHE[text] = result
        return result
    except Exception as e:
        print(f"Error generating pinyin for '{text}': {str(e)}")
        return ""

def translate_word_batch(words: List[str], from_language: str, to_language: str) -> List[str]:
    """Translate a batch of words while maintaining order."""
    translations = [None] * len(words)
    words_to_translate = []
    indices_to_translate = []

    # Check cache first
    for idx, word in enumerate(words):
        if word in TRANSLATION_CACHE:
            translations[idx] = TRANSLATION_CACHE[word]
        else:
            words_to_translate.append(word)
            indices_to_translate.append(idx)

    if words_to_translate:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_TRANSLATION_WORKERS) as executor:
            future_to_index = {
                executor.submit(
                    ts.translate_text,
                    word,
                    from_language=from_language,
                    to_language=to_language,
                    translator='bing'
                ): idx
                for idx, word in zip(indices_to_translate, words_to_translate)
            }

            for future in concurrent.futures.as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    result = future.result()
                    TRANSLATION_CACHE[words[idx]] = result
                    translations[idx] = result
                except Exception as e:
                    print(f"Translation error for word '{words[idx]}': {str(e)}")
                    translations[idx] = words[idx]  # 失败时保留原词

    return translations

def wrap_chinese_words(text: str) -> str:
    """Process Chinese text with parallel pinyin and translation."""
    if not text.strip():
        return text

    words = list(jieba.cut(text))

    # Generate pinyin for each word
    if GENERATE_PINYIN:
        pinyin_results = generate_pinyin_parallel(words)
    else:
        pinyin_results = [""] * len(words)

    # Generate translations if needed
    translations = translate_word_batch(words, 'zh', 'en') if WORD_BY_WORD_TRANSLATION else [""] * len(words)

    # Combine results
    wrapped_words = []
    for word, py, translation in zip(words, pinyin_results, translations):
        wrapped_words.append(
            f'<span class="chinese-word" '
            f'data-word="{html.escape(word)}" '
            f'data-pinyin="{html.escape(py)}" '
            f'data-translation="{html.escape(translation)}">'
            f'{html.escape(word)}</span>'
        )

    return ''.join(wrapped_words)

def process_lines_parallel(lines: List[str]) -> List[str]:
    """Process lines in parallel while maintaining order."""
    results = [None] * len(lines)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_LINE_WORKERS) as executor:
        future_to_index = {
            executor.submit(
                lambda l: translate_and_wrap(l) if l.strip().startswith('##') else l,
                line
            ): idx
            for idx, line in enumerate(lines)
        }

        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                print(f"Error processing line {idx}: {str(e)}")
                results[idx] = lines[idx]

    return results

def translate_and_wrap(text: str) -> str:
    """Process a single line of text."""
    match = re.match(r'^##\s*(\d+\.?\s*)(.*)', text)
    if match:
        index, content = match.groups()
        index_html = f'<span class="section-index">{html.escape(index)}</span>'
        wrapped_content = wrap_chinese_words(content)
        return f'<h2>{index_html}{wrapped_content}</h2>'
    return wrap_chinese_words(text)

def process_markdown_file(file_path: str) -> Tuple[str, str]:
    """Process a markdown file and return title and HTML content."""
    print(f"\nProcessing file: {file_path}")
    start_time = time.time()

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 处理后的新内容
    new_lines = []
    for line in lines:
        line = line.rstrip()
        new_lines.append(line)

        # 如果是中文标题行，添加拼音
        if line.strip().startswith('## '):
            match = re.match(r'^##\s*\d+\.\s*(.+)$', line.strip())
            if match:
                chinese_text = match.group(1)
                # 生成拼音
                pinyin_line = ' '.join([p[0] for p in pinyin(chinese_text, style=Style.TONE)])
                print(f"Added pinyin for: {chinese_text}")
                print(f"Pinyin: {pinyin_line}")
                # 添加拼音行
                new_lines.append(f"- *{pinyin_line}*")

    md_content = '\n'.join(new_lines)

    # Extract title and YouTube link
    title_match = re.search(r'^# (.+)$', md_content, re.MULTILINE)
    youtube_match = re.search(
        r'\[Watch on Youtube\]\((https?://[^\)]+)\)',
        md_content,
        re.IGNORECASE
    )

    title = title_match.group(1) if title_match else "Unknown Title"
    youtube_link = youtube_match.group(1) if youtube_match else ""
    video_id = extract_video_id(youtube_link)

    # Process content
    processed_lines = process_lines_parallel(new_lines)

    # Convert to HTML
    html_content = markdown.markdown('\n'.join(processed_lines))

    # Read template
    with open('/content/drive/My Drive/template_Chinese.html', 'r', encoding='utf-8') as f:
        template_content = f.read()

    # Render template
    rendered_html = Template(template_content).render(
        content=html_content,
        title=title,
        video_id=video_id,
        word_by_word_translation=WORD_BY_WORD_TRANSLATION,
        generate_pinyin=GENERATE_PINYIN
    )

    end_time = time.time()
    print(f"Processing completed in {end_time - start_time:.2f} seconds")

    return title, rendered_html

def main():
    print("\n=== Starting main function ===")

    # Configuration
    input_file = "translated_output.md"  # 输入的markdown文件
    output_html = video_title + ".html"  # 输出的HTML文件

    # Process markdown and generate HTML
    title, html_content = process_markdown_file(input_file)

    # Save HTML
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\nProcessed markdown file: {input_file}")
    print(f"Generated HTML file: {output_html}")

if __name__ == '__main__':
    main()