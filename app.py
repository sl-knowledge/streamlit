import streamlit as st
import os
from translate_book import translate_file
from io import BytesIO
from password_manager import PasswordManager
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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


def show_admin_dashboard():
    if not init_password_manager():
        return

    try:
        stats = pm.get_usage_stats()

        st.header("Admin Dashboard")

        # Password Management Section
        st.subheader("Password Management")
        col1, col2 = st.columns(2)

        with col1:
            days_valid = st.number_input("Days Valid", min_value=1, value=30)
            prefix = st.text_input("Password Prefix", value="tr")
            if st.button("Generate New Password"):
                new_password = pm.add_password(
                    days_valid=days_valid, prefix=prefix)
                st.success(f"New password generated: {new_password}")

        with col2:
            st.subheader("Extend Password")
            extend_password = st.text_input("Password to Extend")
            additional_days = st.number_input(
                "Additional Days", min_value=1, value=30)
            if st.button("Extend Password"):
                if pm.extend_password(extend_password, additional_days):
                    st.success("Password extended successfully")
                else:
                    st.error("Invalid password or error extending")

        # List all passwords
        st.subheader("Active Passwords")
        passwords = pm.list_all_passwords()
        if passwords:
            df = pd.DataFrame(passwords)
            st.dataframe(df)
        else:
            st.info("No passwords found")

        # Usage Statistics
        st.subheader("Usage Statistics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Passwords", stats['total_passwords'])
        with col2:
            st.metric("Active Passwords", stats['active_passwords'])
        with col3:
            st.metric("Last Modified", stats['last_modified'])

        # System Health
        st.subheader("System Health")
        health = pm.get_system_health()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("API Response Time", health['api_response_time'])
        with col2:
            st.metric("Success Rate", health['success_rate'])
        with col3:
            st.metric("Error Rate", health['error_rate'])

        # Recent Activity
        st.subheader("Recent Activity")
        activity = pm.get_recent_activity()
        if activity:
            df = pd.DataFrame(activity)
            st.dataframe(df)

    except Exception as e:
        st.error(f"Error displaying admin dashboard: {str(e)}")


def show_user_interface(user_password=None):
    if not init_password_manager():
        return

    if user_password is None:
        user_password = st.text_input("Enter your access key", type="password")
        if not user_password:
            st.warning("Please enter your access key to use the translator")
            return

        if not pm.verify_password(user_password):
            st.error("Invalid access key")
            return

    # Show usage statistics
    stats = pm.get_user_stats(user_password)
    if stats:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Today's Usage",
                      f"{stats['today_usage']}/{stats['daily_limit']}")
        with col2:
            st.metric("Remaining Today", stats['remaining_today'])
        with col3:
            st.metric("Total Usage", stats['total_usage'])

    # Translation Settings
    st.header("Translation Settings")
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        include_english = st.checkbox(
            "Include English Translation", value=True)

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
        example_text = """第37届中国电影金鸡奖是2024年11月16日在中国厦门举行的中国电影颁奖礼[2]，该届颁奖礼由中国文学艺术界联合会、中国电影家协会与厦门市人民政府共同主办。2024年10月27日公布评委会提名名单[3][4]，颁奖典礼主持人由电影频道主持人蓝羽与演员佟大为担任[5]。

张艺谋执导的《第二十条》获最佳故事片奖，陈凯歌凭借《志愿军：雄兵出击》获得最佳导演，雷佳音、李庚希分别凭借《第二十条》和《我们一起摇太阳》获得最佳男女主角奖[6]，李庚希亦成为中国电影金鸡奖的第一位"00后"影后[7]。

概要
中国电影家协会于2024年7月4日宣布该届颁奖礼评选工作开始，参评对象为2023年7月1日至2024年6月30日期间取得国家电影局核发的电影公映许可证的影片[8]，设有最佳故事片、评委会特别奖、最佳中小成本故事片及专业奖项共20个，共有251部影片报名参选。评选和终评三阶段，按种分为故事片、纪／科教片、美术片、戏曲片共4个评委会，评委会成员实名投票产生各奖项提名名单，金鸡百花电影节举行期间进行终评决定最终

云南地处中国西南，位于北纬21°8'32"－29°15'8"和东经97°31'39"－106°11'47"之间，全境东西最大横距864.9公里，南北最大纵距900公里，总面积39.4万平方千米，占中国国土面积的4.1%，居第8位。最低处位于河口县城西南，南溪河与红河交汇，高程为海拔76.4米，为云南最低处[22]；最高处位于德钦县的梅里雪山主峰卡瓦格博峰，海拔6,740米，为云南最高点[23]。云南全境，东与贵州、广西接壤，北与四川毗邻，西北与西藏交界，西与缅甸为邻，南同老挝、越南毗连。云南有长达4,060公里国境线，是中国连接东南亚各国的陆路通道，全省有出境公路20多条。北回归线穿越全境，全省分属热带、亚热带气候，兼具低纬气候、季风气候、山原气候的特点[24]。

云南处青藏高原南延部分和云贵高原，为高原山区省份。地貌上有五个特征，一是高原呈扫帚状，三江并流皱褶地区的横断山脉是扫帚柄部分，苍山、无量山、哀牢山组成扫帚部分，二是高山峡谷相间，三是地势自西北向东南分三大阶梯递降，四是断陷盆地星罗棋布，五是山川湖泊纵横。地形上河谷盆地、丘陵、山地、高原相间分布，各类地貌之间条件差异很大，类型多样复杂。全省依地形分类，山地约占84%，高原、丘陵约占10%，河谷盆地约占6%；平均海拔2,000米左右。全省127个县（市）区及东川市共128个行政区划单位中，除昆明市的五华、盘龙区两个城区外，山区比重都在70%以上，没有一个纯坝（河谷盆地）县（市）区。 其中山区面积占县域总面积70一79.9%的有4个，山区面积占80一89.9%的有13个，占90一95%的有5个县，其余的县（市）区均在95%以上，有18个县99%以上的土地全是山地。"""
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

        # Track usage with IP address
        if not pm.track_usage(user_password, len(text_input), st.session_state.client_ip):
            st.error("Daily usage limit exceeded")
            return

        try:
            # Create a progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()

            with st.spinner("Translating... This may take a few minutes."):
                # Save input text
                with open("temp_input.txt", "w", encoding="utf-8") as f:
                    f.write(text_input)

                # Initialize translation progress
                if 'translation_progress' not in st.session_state:
                    st.session_state.translation_progress = 0

                # Process translation
                translate_file(
                    "temp_input.txt",
                    progress_callback=lambda p: update_progress(
                        p, progress_bar, status_text),
                    include_english=include_english,
                    second_language=languages[second_language],
                    pinyin_style=pinyin_style
                )

                # Read the generated HTML
                with open("temp_input.html", "r", encoding="utf-8-sig") as f:
                    html_content = f.read()

                # Show success and download button
                progress_bar.progress(100)
                status_text.text("Translation completed!")
                st.success("Translation completed!")
                st.download_button(
                    label="Download HTML",
                    data=html_content,
                    file_name="translation.html",
                    mime="text/html"
                )

                # Show preview
                st.markdown("### Preview:")
                st.components.v1.html(html_content, height=600, scrolling=True)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.info("Try with a smaller text or try again later.")


def update_progress(progress, progress_bar, status_text):
    """Update the progress bar and status text"""
    progress_bar.progress(int(progress))
    status_text.text(f"Translating... {progress:.1f}%")
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


def main():
    st.set_page_config(page_title="Translator App", layout="centered")

    # 只保留文本区域的样式，移除按钮样式
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

    # Clear connection attempt state on page load
    if 'db_connection_attempted' in st.session_state:
        del st.session_state.db_connection_attempted

    # Initialize session and IP tracking
    init_session()

    # Initialize session states
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False
    if 'user_logged_in' not in st.session_state:
        st.session_state.user_logged_in = False
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None

    # Create a small button in the top-right corner for admin access
    col1, col2 = st.columns([8, 1])
    with col2:
        if st.button("Admin"):
            st.session_state.show_admin = True

    # Handle admin login in a modal-like container
    if getattr(st.session_state, 'show_admin', False):
        with st.container():
            st.markdown("### Admin Login")
            admin_password = st.text_input(
                "Admin Password", type="password", key="admin_pwd")
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("Login", key="admin_login"):
                    if check_admin_password(admin_password):
                        if init_password_manager():
                            st.session_state.admin_logged_in = True
                            st.session_state.show_admin = False
                            st.rerun()
                    else:
                        st.error("Invalid admin password")
            with col2:
                if st.button("Cancel", key="admin_cancel"):
                    st.session_state.show_admin = False
                    st.rerun()

    # Show admin dashboard or user interface
    if st.session_state.admin_logged_in:
        col1, col2 = st.columns([10, 1])
        with col2:
            if st.button("Logout", key="admin_logout"):
                st.session_state.admin_logged_in = False
                st.rerun()
        show_admin_dashboard()
    else:
        # Handle user interface
        if not st.session_state.user_logged_in:
            user_password = st.text_input(
                "Enter your access key", type="password", key="user_pwd")
            if st.button("Login", key="user_login"):
                if init_password_manager():  # Initialize before verifying password
                    if pm.verify_password(user_password):
                        st.session_state.user_logged_in = True
                        st.session_state.current_user = user_password
                        st.rerun()
                    else:
                        st.error("Invalid access key")
        else:
            col1, col2 = st.columns([10, 1])
            with col2:
                if st.button("Logout", key="user_logout"):
                    st.session_state.user_logged_in = False
                    st.session_state.current_user = None
                    st.rerun()
            show_user_interface(st.session_state.current_user)


if __name__ == "__main__":
    main()
