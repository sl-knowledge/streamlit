import streamlit as st
import os
from translate_book import translate_file, create_interactive_html_block
from io import BytesIO
from password_manager import PasswordManager
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import streamlit.components.v1 as components
import jieba
# Initialize password manager only when needed
pm = None


def init_password_manager():
    global pm
    if pm is None:
        try:
            pm = PasswordManager()
            return True
        except Exception as e:
            st.error(f"Error initializing password manager: {str(e)}")
            return False
    return True


def show_user_interface(user_password=None):
    if not init_password_manager():
        return

    if user_password is None:
        user_password = st.text_input("Enter your access key", type="password")
        if not user_password:
            st.warning("Please enter your access key to use the translator")
            return

        if not pm.check_password(user_password):
            st.error("Invalid access key")
            return

    # Translation Settings
    st.header("Translation Settings")
    
    # Add translation mode selection
    st.subheader("Choose Translation Mode")
    translation_mode = st.radio(
        "",
        ["Standard Translation", "Interactive Word-by-Word"],
        help="Standard Translation: Full sentence translation with pinyin\nInteractive Word-by-Word: Click on individual words to see translations and hear pronunciation"
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        include_english = st.checkbox(
            "Include English Translation", 
            value=True,
            help="Include English translation alongside the second language"
        )

    with col2:
        languages = {
            "Arabic": "ar",
            "English": "en",
            "French": "fr",
            "Indonesian": "id",
            "Italian": "it",
            "Japanese": "ja",
            "Korean": "ko",
            "Persian": "fa",
            "Portuguese": "pt",
            "Russian": "ru",
            "Spanish": "es",
            "Thai": "th",
            "Vietnamese": "vi"
        }

        second_language = st.selectbox(
            "Select Second Language (Required)",
            options=list(languages.keys()),
            index=None,
            placeholder="Choose a language..."
        )

    with col3:
        pinyin_style = st.selectbox(
            'Pinyin Style',
            ['tone_marks', 'tone_numbers'],
            index=0,
            format_func=lambda x: 'Tone Marks (nǐ hǎo)' if x == 'tone_marks' else 'Tone Numbers (ni3 hao3)'
        )
        
    if second_language == "English" and include_english:
        st.warning("English translation is already enabled via checkbox")
        second_language = None

    # Input Options
    input_method = st.radio("Choose input method:", [
                            "Paste Text", "Upload File", "Try Example"], key="input_method")

    # Initialize text_input outside the if blocks
    text_input = ""

    if input_method == "Paste Text":
        # Create a container for text input
        text_container = st.container()
        with text_container:
            # Simple text area with reduced height from 800 to 500
            text_input = st.text_area(
                "Paste Chinese text here",
                value="",
                height=500,
                key="simple_text_input",
                help="Paste your Chinese text here. The text will be split into sentences automatically."
            )

    elif input_method == "Upload File":
        uploaded_file = st.file_uploader(
            "Upload Chinese text file",
            type=['txt'],
            key="file_uploader",
            help="Upload a .txt file containing Chinese text"
        )
        if uploaded_file:
            try:
                text_input = uploaded_file.getvalue().decode('utf-8')
                # Show the uploaded text in a text area that can be edited
                text_input = st.text_area(
                    "Edit uploaded text if needed:",
                    value=text_input,
                    height=300,
                    key="uploaded_text_area"
                )
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

    else:  # Try Example
        example_text = """第37届中国电影金鸡奖是2024年11月16日在中国厦门举行的中国电影颁奖礼[2]，该届颁奖礼由中国文学艺术界联合会、中国电影家协会与厦门市人民政府共同主办。2024年10月27日公布评委会名名单[3][4]，颁奖典礼主持人由电影频道主持人蓝羽与演员佟大为担任[5]。

张艺执导的《第二十条》获最佳故事片奖，陈凯歌凭借《志愿军：雄兵出击》获得最佳导演，雷佳音、李庚希分别凭借《第二十条》和《我们一起太阳》获得最佳男主角奖[6]，李庚希亦成为中电影金鸡奖的第一位"00后"影后[7]。
"""
        text_input = st.text_area(
            "Example text (you can edit):",
            value=example_text,
            height=300,
            key="example_text_area"
        )

    # Translation Button
    if st.button("Translate", key="translate_button"):
        if not second_language:
            st.error("Please select a second language before translating!")
            return

        if not text_input.strip():
            st.error("Please enter or upload some text first!")
            return

        try:
            # 创建进度条
            progress_bar = st.progress(0)
            status_text = st.empty()

            if translation_mode == "Interactive Word-by-Word":
                # 使用正确的语言代码
                processed_words = st.session_state.translator.process_chinese_text(
                    text_input, 
                    languages[second_language]
                )
                if processed_words:
                    html_content = create_interactive_html(processed_words, include_english)
                    # 显示翻译结果
                    st.success("Translation completed!")
                    components.html(html_content, height=800, scrolling=True)
                    
                    # 添加下载按钮
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.download_button(
                            label="Download HTML",
                            data=html_content,
                            file_name="translation.html",
                            mime="text/html",
                            help="Download the translation as an HTML file"
                        )
            else:
                # 使用标准翻译模式
                html_content = translate_file(
                    text_input,
                    lambda p: update_progress(p, progress_bar, status_text),
                    include_english,
                    languages[second_language],
                    pinyin_style,
                    translation_mode
                )
                # 显示翻译结果
                st.success("Translation completed!")
                components.html(html_content, height=800, scrolling=True)
                
                # 添加下载按钮
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.download_button(
                        label="Download HTML",
                        data=html_content,
                        file_name="translation.html",
                        mime="text/html",
                        help="Download the translation as an HTML file"
                    )
        except Exception as e:
            st.error(f"Translation error: {str(e)}")


def update_progress(progress, progress_bar, status_text):
    """Update the progress bar and status text"""
    progress_bar.progress(progress/100)  # Convert percentage to 0-1 range
    status_text.text(f"Processing... {progress:.1f}% completed")
    st.session_state.translation_progress = progress


def init_session():
    if 'client_ip' not in st.session_state:
        # Check if IP tracking is enabled in settings
        if st.secrets.get("enable_ip_tracking", False):
            try:
                # Get IP from Streamlit's request headers
                client_ip = None

                # Try to get the IP from X-Forwarded-For header first
                forwarded_for = st.request_header('X-Forwarded-For')
                if forwarded_for:
                    # X-Forwarded-For can contain multiple IPs, take the first one
                    client_ip = forwarded_for.split(',')[0].strip()

                # If no X-Forwarded-For, try X-Real-IP
                if not client_ip:
                    client_ip = st.request_header('X-Real-IP')

                # If still no IP, use a default
                st.session_state.client_ip = client_ip or '127.0.0.1'

            except Exception as e:
                print(f"Error getting IP: {e}")
                st.session_state.client_ip = '127.0.0.1'
        else:
            # If IP tracking is disabled, use a default value
            st.session_state.client_ip = '127.0.0.1'


def check_admin_password(password_attempt):
    return password_attempt == st.secrets["admin_password"]


def create_word_tooltip_html(processed_words, target_lang):
    """Create HTML with hover tooltips for each word"""
    # 添加类型检查
    if not processed_words or not isinstance(processed_words, (list, tuple)):
        raise ValueError("processed_words must be a non-empty list or tuple")
        
    with open('template.html', 'r', encoding='utf-8') as template_file:
        template_content = template_file.read()
    
    is_dark_theme = 'dark' in st.config.get_option('theme.base')
    
    content_html = f"""
    <div class="interactive-text" data-theme="{is_dark_theme}">
    """
    
    current_paragraph = []
    paragraphs = []
    
    # 添加错误处理
    try:
        # 按段落分组
        for word_data in processed_words:
            if not isinstance(word_data, dict):
                continue
                
            if word_data.get('word') == '\n':
                if current_paragraph:
                    paragraphs.append(current_paragraph)
                    current_paragraph = []
            else:
                current_paragraph.append(word_data)
        
        # 添加最后一个段落
        if current_paragraph:
            paragraphs.append(current_paragraph)
        
        # 生成 HTML
        for paragraph in paragraphs:
            content_html += "<p>"
            for word_data in paragraph:
                # 检查是否是标点符号
                is_punctuation = len(word_data.get('word', '')) == 1 and not word_data.get('pinyin')
                
                if is_punctuation:
                    content_html += f"""
                    <span class="non-chinese">{word_data['word']}</span>
                    """
                else:
                    content_html += f"""
                    <span class="interactive-word" 
                          onclick="speak('{word_data.get('word', '')}')"
                          data-tooltip="{word_data.get('pinyin', '')}&#10;{word_data.get('translation', '...')}">
                        {word_data.get('word', '')}
                    </span>
                    """
            content_html += "</p>"
        
    except Exception as e:
        st.error(f"Error processing text: {str(e)}")
        return None
    
    content_html += "</div>"
    
    final_html = template_content.replace('{{content}}', content_html)
    return final_html


def display_interactive_chinese(text, password_manager, target_lang):
    """Display interactive Chinese text with tooltips"""
    # Process the text with the target language
    processed_words = st.session_state.translator.process_chinese_text(text, target_lang)
    
    # 添加错误检查
    if not processed_words:
        st.error("Error processing text. No words were processed.")
        return
    
    # Create HTML content
    html_content = create_word_tooltip_html(processed_words, target_lang)
    
    # Show preview
    components.html(html_content, height=800, scrolling=True)
    
    # Add download button
    st.download_button(
        label="Download HTML",
        data=html_content,
        file_name="translation.html",
        mime="text/html"
    )


def create_interactive_html(processed_words, include_english):
    """Create HTML content for interactive translation"""
    with open('template.html', 'r', encoding='utf-8') as template_file:
        html_content = template_file.read()
    
    # 使用从 translate_book.py 导入的函数
    translation_content = create_interactive_html_block(
        (None, processed_words),  # 传入 None 作为 chunk，因为我们已经有了处理好的词
        include_english
    )
    
    return html_content.replace('{{content}}', translation_content)


def main():
    st.set_page_config(page_title="Translator App", layout="centered")

    # 保持文本区域的样式
    st.markdown("""
    <style>
    .stTextArea textarea {
        cursor: text !important;
        caret-color: #1E90FF !important;
        color: inherit !important;
        background-color: transparent !important;
        font-size: 16px !important;
        line-height: 1.5 !important;
        border-radius: 4px !important;
        border: 1px solid rgba(128, 128, 128, 0.4) !important;
    }
    .stTextArea textarea:focus {
        border-color: #1E90FF !important;
        box-shadow: 0 0 0 1px #1E90FF !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # 初始化 translator
    if 'translator' not in st.session_state:
        from translator import Translator
        st.session_state.translator = Translator()

    # 简化登录逻辑
    if not st.session_state.get('user_logged_in', False):
        user_password = st.text_input("Enter your access key", type="password")
        if st.button("Login"):
            if init_password_manager():
                if pm.check_password(user_password):
                    st.session_state.user_logged_in = True
                    st.session_state.current_user = user_password
                    st.rerun()
                else:
                    st.error("Invalid access key")
    else:
        col1, col2 = st.columns([10, 1])
        with col2:
            if st.button("Logout"):
                st.session_state.user_logged_in = False
                st.session_state.current_user = None
                st.rerun()
        show_user_interface(st.session_state.current_user)


if __name__ == "__main__":
    main()

