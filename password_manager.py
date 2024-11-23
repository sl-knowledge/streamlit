import json
from datetime import datetime, timedelta
import secrets
import string
import hashlib
import uuid
import streamlit as st
import base64
import psutil
import time
import plotly.graph_objects as go
import pandas as pd
from collections import defaultdict
import jieba
from pypinyin import pinyin, Style
import requests


class PasswordManager:
    def __init__(self):
        # Get API keys and their metadata from secrets
        self.api_keys = st.secrets.get("api_keys", {})
        self.api_metadata = st.secrets.get("api_metadata", {})

    def check_password(self, password):
        """Check if password is valid"""
        return password in self.api_keys.values()
