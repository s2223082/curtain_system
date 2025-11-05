# -*- coding: utf-8 -*-
"""
スマートホーム管理サーバーメインプログラム
Raspberry Pi上で動作し、各種センサー(BME280, BH1750)の読み取り、
デバイス(Tuyaカーテン, SwitchBotカーテン, CEC対応プロジェクター)の制御、
キーパッド入力の処理、およびWeb UI (Flask) の提供を行います。
AIによる自動制御機能も含まれます。
"""

# --- 1. 標準ライブラリ・外部ライブラリのインポート ---
import time
import smbus2
import os
from datetime import datetime
import requests
import json
import subprocess
import sys
import threading # スレッド（並行処理）のために必要
import logging
import csv
import re # 正規表現（天気情報の整形）のために必要

# GPIO (キーパッド、LED、ブザー)
import RPi.GPIO as GPIO
# I2C LCD (液晶ディスプレイ)
from RPLCD.i2c import CharLCD
# Flask (Webサーバー)
from flask import Flask, jsonify, render_template_string, request, Response, render_template
from flask_cors import CORS
# Tuya (カーテン制御)
from tuya_connector import TuyaOpenAPI
# gTTS (Google Text-to-Speech)
from gtts import gTTS
# pandas (ログ表示用)
import pandas as pd
# OpenCV & Pillow (カメラ映像処理・描画)
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
# BeautifulSoup (天気情報スクレイピング)
from bs4 import BeautifulSoup


# ==============================================================================
# 2. ユーザー設定・定数定義
# ==============================================================================

# --- I2Cデバイスのアドレス ---
I2C_BUS = 1             # Raspberry PiのI2Cバス番号 (通常は1)
BME280_ADDRESS = 0x76   # BME280 (温湿度・気圧センサー) のアドレス
BH1750_ADDRESS = 0x23   # BH1750 (照度センサー) のアドレス
LCD_ADDRESS = 0x3f      # I2C LCD (16x2) のアドレス

# --- GPIOピン設定 (BCMモード) ---
# 4x4 キーパッド
KEYPAD_ROW_PINS = [26, 19, 13, 6] # 行 (入力ピン)
KEYPAD_COL_PINS = [21, 20, 16, 12] # 列 (出力ピン)
# キーと押されたキーのマッピング
KEYPAD_MAP = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"]
]
# その他
BUZZER_PIN = 5      # ブザー
RED_PIN = 17        # 赤色LED (ログ記録OFF時)
GREEN_PIN = 27      # 緑色LED (ログ記録ON時)
BLUE_LED_PIN = 24   # 青色LED (自動モード時)

# --- 外部API・デバイスID (ご自身の値に書き換えてください) ---
# SwitchBot (API v1.0)
SWITCHBOT_BASE_URL = "http://itap.watalab.info:8081/itap/v1"         # SwitchBot APIのエンドポイントURL
SWITCHBOT_ITAP_TOKEN = "FEIGlhOoslxo31VzC304xmOtgKEI30wmOheuWEZlwEh6cx+M4UUtrpjpkO7fUHOAzgUuUXX/xBUfpfD5noeAjzNpF1ig/CcBHa2H1cpg+NJhIHNaQ7GcklTpnU+cKVxDzxxLIuxbxyucmKoHL2FbkwSLCV7UYDVbEgi5yO6e2Brq+l93zSqOLYrQ3H8ikoIpWhxMt3T1SKdCwbe7hiMsV66SKRaur0CQtBXuJE1CFNcIsHlPR1KnjVJbdtuuPxMZSzpeOp/o5bXlW8yD+zaK3Yh2IXlyXZjuhfl7BOQCbjDm7DxB/DQYnOQsnxl+2r8iX0JBUP0bLRG1YgpSgDyDwv/vk0qb4Q1s1rmTzn8j5hq7SKLJ1bFqp1IY5WO8+KE6n20FHxG0Df0eSAoplVTcIFc5UomzxP4xZ1O932pQt1cqJXtQqSxgF0JMRWkxH4K4il8x1eHn6lD51d871sde6d9ey4kn+a9eIQH8TAnMsDqqfU7cAuMatUrDCdtxN6hQ0nsLLTg3uPuHTVSQN+Tog/d1tuktpovcqJ8qBAZUsMNlH9b//23NDyGGMZHqXpZf5PLrKUJBpUXf5uf6c/ZkzhUow7f6UHoI4t56XbHHEx6uol5xcdiVkOE9tdrNrB/12an2/Zj8YzaWI8vpbjVmEIgv4KymIlYCuhvQoTHnYM8b7lXwrsFsOAczOCnwWj8V1KGV1jN6fCxpQhcMnW6WzDObucpoJ5IvDX+mHmhzclGNSobpV+aWgv2IRvcfL11LgnDxE5TUOXT9RoaFCzz+uI7D04B3jHfK5OK8NCScvbVhy3KOLCAqVcxByPH0naLgvZNY8odmVtTDehspuqhfWlHWe4axT11UlhwT83alKc8XjDdIao3VVlJ/PWA4Fa1nDF7eSt3tKfVmEjxn+KzD7pvYshakOCSOdhA6PzZukL5u2W5jmwbWbGyvQIxVP4428qsnp/XWMG3kYkt/J2PffOnV2h6udUi6aOIJkPVd8maiGlE3g4EX4MLvdHoA1fi8lADVeDHugjNTzTU15U0vDcxQAWFSEPEAq0pfqMsGgvPMR2AOLeSxdeq16GNJQLqaNIk2RJj0OaXVbIStGI9TsQ=="       # 開発者トークン
SWITCHBOT_OWNER_PASSWORD = "kait1104"   # パスワード
HUB_DEVICE_ID = "B0E9FEAC62FC"              # SwitchBotハブミニのデバイスID
SWITCHBOT_CURTAIN_DEVICE_ID = "B0E9FE7153C8" # SwitchBotカーテンのデバイスID

# Tuya Cloud (API)
TUYA_ACCESS_ID = "gavwxscwwncxv895ugcx"             # Tuya Cloud API Access ID
TUYA_ACCESS_KEY = "5b1b44c9155d4b38beefd39c1ec1e350"            # Tuya Cloud API Access Key
TUYA_API_ENDPOINT = "https://openapi.tuyaus.com"          # APIエンドポイント (例: "https://openapi.tuyaus.com")
TUYA_DEVICE_ID = "eb92b0bef13d30360ehncv"             # TuyaカーテンのデバイスID

# TuyaデバイスのDPS (Data Point) Index
# (Tuya IoT Platformで確認した "code" を指定)
TUYA_DPS_INDEX_CONTROL = 'percent_control' # カーテン位置制御用のDPS

# HDMI-CEC (プロジェクター制御)
PROJECTOR_CEC_DEVICE = 0 # プロジェクターのCECデバイス番号 (通常は0)

# --- センサーログ設定 ---
CSV_FILE_PATH = "combined_sensor_log.csv" # センサーデータ記録用CSV
LOG_INTERVAL_SECONDS = 300 # 300秒 (5分) ごとに記録
is_curtain_logging_paused = True # 起動時はモデル学習データ記録をOFFにする

# --- 操作ログ設定 ---
LOG_CSV_FILE = 'smart_home_actions.log.csv' # 操作履歴用CSV

# --- AI自動制御 ---
# ★★★必ずご自身のPCのIPアドレスに変更してください★★★
PC_AI_SERVER_URL = "http://192.168.113.10:10820/predict" 
# 300秒 (5分) ごとにAI制御を実行
AUTO_CONTROL_INTERVAL_SECONDS = 300  


# ==============================================================================
# 3. グローバル変数 (プログラム全体で共有する状態)
# ==============================================================================
bus = None              # I2Cバスのインスタンス
lcd = None              # LCDのインスタンス
camera = None           # OpenCVのカメラインスタンス
openapi = None          # Tuya APIのインスタンス
app = Flask(__name__)   # Flaskアプリケーションのインスタンス
CORS(app)               # FlaskでCORS (クロスオリジンリクエスト) を許可

# --- センサー・デバイスの状態 ---
bme280_found = False    # BME280がI2Cバス上で見つかったか
bh1750_found = False    # BH1750がI2Cバス上で見つかったか
latest_sensor_data = {} # Web API配信用に最新のセンサーデータを保持
weather_data = {        # 天気情報
    'text': '---',
    'high': '--',
    'low': '--'
}
current_curtain_state = {"state": "unknown", "position": "N/A"} # Tuyaカーテンの現在の状態
current_projector_status = "不明" # プロジェクターの電源状態
current_hdmi_input = "不明"     # プロジェクターのHDMI入力状態

# --- プログラムの内部状態 ---
is_auto_mode = False        # AI自動制御がONか
is_ai_connected = False     # AIサーバー(PC)と通信可能か
last_curtain_position_command = None # 最後に実行したカーテンシーン名 (AI制御のスキップ用)
connected_ips = set()       # Web UIに接続したクライアントIPのセット (ログ用)

# --- スレッド制御フラグ ---
stop_blinking_flag = threading.Event()      # 赤色LEDの点滅停止用
stop_blue_blinking_flag = threading.Event() # 青色LEDの点滅停止用

# --- BME280用キャリブレーションデータ (起動時に読み込む) ---
dig_T1, dig_T2, dig_T3 = 0, 0, 0
dig_P1, dig_P2, dig_P3, dig_P4, dig_P5, dig_P6, dig_P7, dig_P8, dig_P9 = 0,0,0,0,0,0,0,0,0
dig_H1, dig_H2, dig_H3, dig_H4, dig_H5, dig_H6 = 0,0,0,0,0,0
t_fine = 0.0 # BME280の内部計算用


# ==============================================================================
# 4. ログ・音声案内 関数
# ==============================================================================
def log_action(source, action_type, details, ip_addr='--'):
    """
    操作ログをCSVファイル(LOG_CSV_FILE)に追記する関数
    
    Args:
        source (str): 操作元 (例: "Web UI", "Keypad", "AI")
        action_type (str): 操作種別 (例: "シーン実行", "モード切替")
        details (str): 詳細 (例: "シーン'set0'を実行")
        ip_addr (str, optional): 操作元のIPアドレス
    """
    now = datetime.now()
    log_entry = [
        now.strftime('%Y/%m/%d'),   # 日付
        now.strftime('%H:%M:%S'),   # 時刻
        source,                     # 操作元
        action_type,                # 種別
        details,                    # 詳細
        ip_addr                     # IPアドレス
    ]
    
    # ファイルが存在しない場合は、ヘッダー行を先に書き込む
    if not os.path.exists(LOG_CSV_FILE):
        with open(LOG_CSV_FILE, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['日付', '時刻', '操作元', '種別', '詳細', 'IPアドレス'])
    
    # ログエントリーを追記モード ('a') で書き込む
    with open(LOG_CSV_FILE, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(log_entry)

def speak_message(text):
    """
    指定されたテキストをgTTSとmpg123を使って音声で読み上げる関数
    
    Args:
        text (str): 読み上げる日本語テキスト
    """
    try:
        # 読み上げる内容をコンソールにも表示
        print(f"[音声案内] アナウンス内容: '{text}'")
        
        # gTTSオブジェクトを作成 (lang='ja'で日本語に設定)
        tts = gTTS(text=text, lang='ja')
        
        # 音声データを一時ファイル (temp_speech.mp3) として保存
        temp_file = "temp_speech.mp3"
        tts.save(temp_file)
        
        # mpg123コマンドを使って再生 (-q オプションで余計な情報を非表示に)
        # check=Trueでコマンドが失敗したら例外を発生させる
        subprocess.run(["mpg123", "-q", temp_file], check=True)
        
        # 再生が終わったら一時ファイルを削除
        os.remove(temp_file)
        
    except Exception as e:
        # gTTS APIエラーやmpg123コマンドが見つからない場合など
        print(f"[エラー] 音声の読み上げに失敗しました: {e}")


# ==============================================================================
# 5. 初期化関数 (I2C, GPIO, API, センサー)
# ==============================================================================
def init_tuya_api():
    """Tuya Cloud APIへの接続を初期化する"""
    global openapi # グローバル変数のopenapiインスタンスを更新
    try:
        # TuyaOpenAPIオブジェクトを生成
        openapi = TuyaOpenAPI(TUYA_API_ENDPOINT, TUYA_ACCESS_ID, TUYA_ACCESS_KEY)
        # 接続（認証）を実行
        response = openapi.connect()
        
        # 応答に 'success': True が含まれていれば成功
        if response.get("success"):
            print("[Init] Tuya Cloud API connected successfully.")
            return True
        else:
            # 認証失敗 (ID/Key間違いなど)
            print(f"[ERROR] Failed to connect to Tuya Cloud API: {response}")
            return False
    except Exception as e:
        # ネットワークエラーなど
        print(f"[ERROR] Exception during Tuya Cloud API connection: {e}")
        return False

def init_i2c():
    """I2CバスとLCD(液晶ディスプレイ)、BH1750(照度)を初期化する"""
    global bus, lcd, bh1750_found # グローバル変数を更新
    try:
        # I2Cバスを開く
        bus = smbus2.SMBus(I2C_BUS)
        
        # LCDを初期化 (charmap='A00'は日本語フォントマップ)
        lcd = CharLCD(i2c_expander='PCF8574', address=LCD_ADDRESS, port=I2C_BUS,
                      cols=16, rows=2, dotsize=8,
                      charmap='A00')
        lcd.clear()
        lcd.write_string("System Starting...")
        print("[Init] I2C LCD initialized.")
        
        # BH1750が接続されているか確認 (ダミーの読み取りを試行)
        try:
            bus.read_byte(BH1750_ADDRESS)
            bh1750_found = True # 成功したらフラグをTrueに
            print(f"[Init] BH1750 light sensor found at {hex(BH1750_ADDRESS)}.")
        except Exception:
            bh1750_found = False # 失敗したらFalseに
            print("[Warning] BH1750 light sensor not found.")
            
        return True # I2C初期化成功
    except Exception as e:
        # LCDやI2Cバスの初期化失敗
        print(f"[Error] Failed to initialize I2C devices: {e}")
        return False

def init_gpio():
    """GPIOピン (キーパッド, LED, ブザー) を初期化する"""
    try:
        GPIO.setwarnings(False) # GPIOの警告を非表示
        GPIO.setmode(GPIO.BCM)  # ピン番号の指定方法をBCMモードに設定
        
        # 出力ピンの設定
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        GPIO.setup(RED_PIN, GPIO.OUT)
        GPIO.setup(GREEN_PIN, GPIO.OUT)
        GPIO.setup(BLUE_LED_PIN, GPIO.OUT)
        
        # キーパッド: 行(ROW)を入力、列(COL)を出力に設定
        for row_pin in KEYPAD_ROW_PINS:
            GPIO.setup(row_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # プルダウン抵抗有効
        for col_pin in KEYPAD_COL_PINS:
            GPIO.setup(col_pin, GPIO.OUT)
            GPIO.output(col_pin, GPIO.LOW) # 初期状態はLOW

        print("[Init] GPIO initialized.")
        return True
    except Exception as e:
        print(f"[Error] Failed to initialize GPIO: {e}")
        return False

def setup_bme280():
    """BME280センサーからキャリブレーションデータを読み込み、設定を行う"""
    global bme280_found, dig_T1, dig_T2, dig_T3, dig_P1, dig_P2, dig_P3, dig_P4, dig_P5, dig_P6, dig_P7, dig_P8, dig_P9, dig_H1, dig_H2, dig_H3, dig_H4, dig_H5, dig_H6
    try:
        # BME280のキャリブレーションレジスタからデータを一括読み取り
        cal1 = bus.read_i2c_block_data(BME280_ADDRESS, 0x88, 26)
        cal2 = bus.read_i2c_block_data(BME280_ADDRESS, 0xA1, 1)
        cal3 = bus.read_i2c_block_data(BME280_ADDRESS, 0xE1, 7)

        # 読み取ったデータを結合して、温度(T), 気圧(P), 湿度(H) の補正値に変換
        # (詳細はBME280データシート参照)
        dig_T1 = (cal1[1] << 8) | cal1[0]
        dig_T2 = (cal1[3] << 8) | cal1[2]; 
        if dig_T2 > 32767: dig_T2 -= 65536
        dig_T3 = (cal1[5] << 8) | cal1[4]; 
        if dig_T3 > 32767: dig_T3 -= 65536

        # --- ★★★ ここからが抜け落ちていた部分 ★★★ ---
        dig_P1 = (cal1[7] << 8) | cal1[6]
        dig_P2 = (cal1[9] << 8) | cal1[8]; 
        if dig_P2 > 32767: dig_P2 -= 65536
        dig_P3 = (cal1[11] << 8) | cal1[10];
        if dig_P3 > 32767: dig_P3 -= 65536
        dig_P4 = (cal1[13] << 8) | cal1[12];
        if dig_P4 > 32767: dig_P4 -= 65536
        dig_P5 = (cal1[15] << 8) | cal1[14];
        if dig_P5 > 32767: dig_P5 -= 65536
        dig_P6 = (cal1[17] << 8) | cal1[16];
        if dig_P6 > 32767: dig_P6 -= 65536
        dig_P7 = (cal1[19] << 8) | cal1[18];
        if dig_P7 > 32767: dig_P7 -= 65536
        dig_P8 = (cal1[21] << 8) | cal1[20];
        if dig_P8 > 32767: dig_P8 -= 65536
        dig_P9 = (cal1[23] << 8) | cal1[22];
        if dig_P9 > 32767: dig_P9 -= 65536

        dig_H1 = cal2[0]
        dig_H2 = (cal3[1] << 8) | cal3[0]; 
        if dig_H2 > 32767: dig_H2 -= 65536
        dig_H3 = cal3[2]
        dig_H4 = (cal3[3] << 4) | (cal3[4] & 0x0F);
        if dig_H4 > 2047: dig_H4 -= 4096
        dig_H5 = (cal3[5] << 4) | ((cal3[4] >> 4) & 0x0F);
        if dig_H5 > 2047: dig_H5 -= 4096
        dig_H6 = cal3[6];
        if dig_H6 > 127: dig_H6 -= 256
        # --- ★★★ 抜け落ちていた部分はここまで ★★★ ---

        # センサーの動作モードを設定 (湿度x1, スタンバイ時間, 温度x1, 気圧x1, ノーマルモード)
        bus.write_byte_data(BME280_ADDRESS, 0xF2, 1)    # 湿度オーバーサンプリング x1
        bus.write_byte_data(BME280_ADDRESS, 0xF4, 0x27) # 温度・気圧x1, ノーマルモード
        bme280_found = True
        print(f"[Init] BME280 sensor initialized at {hex(BME280_ADDRESS)}.")
    except Exception as e:
        # I2C通信エラー (BME280が見つからない場合)
        bme280_found = False
        print(f"[Warning] BME280 sensor not found or failed to initialize: {e}")


# ==============================================================================
# 6. センサー・デバイス読み取り関数
# ==============================================================================
def read_bme280():
    """
    BME280から温湿度・気圧を読み取り、補正計算して返す
    
    Returns:
        (float, float, float) or (None, None, None): (温度, 湿度, 気圧)
    """
    global t_fine
    if not bme280_found: return None, None, None # センサーが見つからなければNone
    try:
        # センサーデータレジスタ (0xF7〜0xFE) から8バイト一括読み取り
        data = bus.read_i2c_block_data(BME280_ADDRESS, 0xF7, 8)
        
        # 8バイトのデータを気圧・温度・湿度のADC(生)値に分割
        adc_P = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        adc_T = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        adc_H = (data[6] << 8) | data[7]

        # --- 温度の補正計算 (データシート参照) ---
        v1 = (adc_T / 16384.0 - dig_T1 / 1024.0) * dig_T2
        v2 = ((adc_T / 131072.0 - dig_T1 / 8192.0) ** 2) * dig_T3
        t_fine = v1 + v2 # t_fineは気圧と湿度の計算にも使われる
        temperature = t_fine / 5120.0

        # --- 気圧の補正計算 (データシート参照) ---
        # --- ★★★ ここからが抜け落ちていた部分 ★★★ ---
        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * dig_P6 / 32768.0
        var2 = var2 + var1 * dig_P5 * 2.0
        var2 = (var2 / 4.0) + (dig_P4 * 65536.0)
        var1 = (dig_P3 * var1 * var1 / 524288.0 + dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * dig_P1
        pressure = 0
        if var1 != 0:
            p = 1048576.0 - adc_P
            p = (p - (var2 / 4096.0)) * 6250.0 / var1
            var1 = dig_P9 * p * p / 2147483648.0
            var2 = p * dig_P8 / 32768.0
            p = p + (var1 + var2 + dig_P7) / 16.0
            pressure = p / 100 # hPaに変換
        # --- ★★★ 抜け落ちていた部分はここまで ★★★ ---

        # --- 湿度の補正計算 (データシート参照) ---
        # --- ★★★ ここからが抜け落ちていた部分 ★★★ ---
        h = t_fine - 76800.0
        h = (adc_H - (dig_H4 * 64.0 + dig_H5 / 16384.0 * h)) * \
            (dig_H2 / 65536.0 * (1.0 + dig_H6 / 67108864.0 * h * \
            (1.0 + dig_H3 / 67108864.0 * h)))
        h = h * (1.0 - dig_H1 * h / 524288.0)
        # --- ★★★ 抜け落ちていた部分はここまで ★★★ ---
        if h > 100: h = 100 # 0-100%の範囲に丸める
        elif h < 0: h = 0
        humidity = h

        return temperature, humidity, pressure
    
    except Exception as e:
        # 読み取り中のI2Cエラー
        print(f"[Error] Failed to read from BME280: {e}")
        return None, None, None

def read_bh1750():
    """
    BH1750から照度(lux)を読み取って返す
    
    Returns:
        float or None: 照度(lux)
    """
    if not bh1750_found: return None # センサーが見つからなければNone
    try:
        # 高解像度モード (0x20) で2バイト読み取り
        data = bus.read_i2c_block_data(BH1750_ADDRESS, 0x20, 2)
        # 2バイトを結合し、係数(1.2)で割ってluxに変換
        return (data[0] << 8 | data[1]) / 1.2
    except Exception as e:
        print(f"[Error] Failed to read from BH1750: {e}")
        return None

def get_hub_status():
    """SwitchBot API (v1.0) にアクセスし、ハブミニの温湿度・照度を取得"""
    url = f"{SWITCHBOT_BASE_URL}/vendor/switchbot/devices/status"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "itapToken": SWITCHBOT_ITAP_TOKEN, 
        "ownerPassword": SWITCHBOT_OWNER_PASSWORD, 
        "deviceId": HUB_DEVICE_ID
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status() # 200 OK 以外は例外を発生
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Error] Request to SwitchBot API failed: {e}")
        return None
    
def get_tuya_curtain_status():
    """
    Tuyaカーテンの状態を返す (内部で記憶している状態を返すのみ)
    ※API制限を避けるため、実際のAPIアクセスは制御時にのみ行う
    """
    return current_curtain_state

def get_projector_status():
    """
    HDMI-CEC (cec-client) を使ってプロジェクターの電源状態を取得
    
    Returns:
        str: "ON", "OFF", "Error", "N/A"
    """
    # cec-clientコマンドを実行し、電源状態(pow)を問い合わせる
    full_command = f'echo "pow {PROJECTOR_CEC_DEVICE}" | cec-client -s -d 1'
    try:
        # タイムアウト10秒でコマンド実行
        process = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=10)
        # 標準出力に "power status: on" があればON
        if "power status: on" in process.stdout: return "ON"
        # "power status: standby" があればOFF
        elif "power status: standby" in process.stdout: return "OFF"
    except Exception as e:
        # タイムアウトやコマンドエラー
        print(f"[Error] Failed to get projector status: {e}")
        return "Error"
    return "N/A" # "on" "standby" どちらでもない場合

def get_all_sensor_data():
    """
    すべてのセンサー(ローカル・ハブ)とカーテンの状態を一度に取得し、辞書で返す
    (ログ記録とAPI配信用)
    """
    local_temp, local_hum, local_pres = read_bme280()
    local_lux = read_bh1750()
    hub_status = get_hub_status()
    hub_temp, hub_hum, hub_lux = (None, None, None)
    
    # ハブのステータスが辞書として正しく取得できた場合のみ値を展開
    if hub_status and isinstance(hub_status, dict):
        hub_temp = hub_status.get("temperature")
        hub_hum = hub_status.get("humidity")
        hub_lux = hub_status.get("lightLevel")
        
    curtain_status = get_tuya_curtain_status()
    
    return {
        "local_temp": local_temp, 
        "local_hum": local_hum, 
        "local_pres": local_pres, 
        "local_lux": local_lux,
        "hub_temp": hub_temp, 
        "hub_hum": hub_hum, 
        "hub_lux": hub_lux,
        "tuya_curtain_percent": curtain_status['position']
    }


# ==============================================================================
# 7. デバイス制御関数
# ==============================================================================
def control_tuya_device(commands):
    """
    Tuya Cloud API (tuya-connector) を使ってデバイスを操作し、内部状態を更新する
    
    Args:
        commands (list): Tuya API形式のコマンドリスト (例: [{'code': 'percent_control', 'value': 0}])
    """
    global current_curtain_state
    
    # APIに送信するコマンドを整形
    api_commands = []
    target_value = None # 操作後の位置を記憶するため
    for command in commands:
        if command.get('code') == 'percent_control':
            target_value = command.get('value')
            # ユーザー設定のDPS Index (code) を使う
            api_commands.append({'code': TUYA_DPS_INDEX_CONTROL, 'value': target_value})

    if not api_commands: # 送信すべき有効なコマンドがなければ終了
        print("[Tuya Cloud] No valid commands to send.")
        return

    print(f"-> [Tuya Cloud] Sending commands: {api_commands}")
    try:
        # Tuya APIのエンドポイント (v1.0/devices/{id}/commands) にPOSTリクエスト
        response = openapi.post(f'/v1.0/devices/{TUYA_DEVICE_ID}/commands', {'commands': api_commands})
        print(f"   [Tuya Cloud] API Response: {response}")
        
        # コマンド送信が成功したら、内部の状態 (current_curtain_state) を更新
        if response.get("success"):
            print("   [Tuya Cloud] Command sent successfully.")
            # 実際のデバイスは位置が逆 (0=全開, 100=全閉) なので、100から引いた値を「開度(%)」として記憶
            final_position = 100 - target_value if target_value is not None else "N/A"
            current_curtain_state = {"state": "stopped", "position": final_position}
        else:
            # 失敗した場合は状態をエラーに
            current_curtain_state = {"state": "error", "position": "CmdFail"}

    except Exception as e:
        # API通信例外
        print(f"   [Tuya Cloud] Failed to send command: {e}")
        current_curtain_state = {"state": "error", "position": "Exception"}

def control_switchbot_device(device_id, parameter):
    """SwitchBot API (v1.0) を使ってデバイス (カーテン) を操作する"""
    url = f"{SWITCHBOT_BASE_URL}/vendor/switchbot/devices/commands"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    payload = {
        "itapToken": SWITCHBOT_ITAP_TOKEN, 
        "ownerPassword": SWITCHBOT_OWNER_PASSWORD, 
        "deviceId": device_id,
        "command": {
            "command": "setPosition", # setPosition コマンド
            "parameter": parameter,   # パラメータ (例: 0 or 40)
            "commandType": "command"
        }
    }
    try:
        print(f"-> [SwitchBot] Sending setPosition={parameter} to '{device_id}'...")
        requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        print("   [SwitchBot] Command sent successfully.")
    except Exception as e:
        print(f"   [SwitchBot] Failed to send command: {e}")

def run_cec_command(command_str):
    """cec-clientコマンドを非同期で実行する (プロジェクター制御用)"""
    full_command = f'echo "{command_str}" | cec-client -s -d 1'
    print(f"-> [CEC] Executing: {command_str}")
    # Popenを使い、コマンドの終了を待たずにバックグラウンドで実行
    subprocess.Popen(full_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def control_projector_activate():
    """プロジェクターの電源をONにし、入力をアクティブソースに設定"""
    run_cec_command("on 0") # デバイス0 (TV/プロジェクター) の電源ON
    time.sleep(0.5)
    run_cec_command("as")   # このラズパイをアクティブソース (入力切替) にする

def control_projector_off():
    """プロジェクターの電源をOFF (スタンバイ) にする"""
    run_cec_command(f"standby {PROJECTOR_CEC_DEVICE}")

def switch_hdmi_input(port):
    """
    プロジェクターのHDMI入力を切り替える（リトライ機能付き）
    Args:
        port (int): HDMIポート番号 (1 or 2)
    """
    # 物理アドレスを指定 (10:00 or 20:00)
    target_physical_address = f"{port}0:00"
    # "tx 1F:82:XX:XX" は「Set Stream Path」コマンド
    command = f"tx 1F:82:{target_physical_address}"
    
    logging.info(f"【プロジェクター】HDMI{port}への入力切替を試行...")
    
    # 成功率を上げるために、間隔をあけて3回コマンドを送信する
    for i in range(3):
        print(f"-> [CEC] Sending command (Attempt {i+1}/3): {command}")
        run_cec_command(command)
        time.sleep(1) # コマンド間に1秒待つ

def beep(duration=0.05):
    """ブザーを短く鳴らす"""
    try:
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
    except Exception as e:
        print(f"[Error] Buzzer failed: {e}")


# ==============================================================================
# 8. シーン実行関数
# ==============================================================================

def execute_scene(scene_name, triggered_by='manual', ip_addr=None):
    """
    指定されたシーン名に対応するアクションを実行し、ログを記録する
    
    Args:
        scene_name (str): 実行するシーン名 (例: "set0", "set100")
        triggered_by (str, optional): トリガー ( "manual" or "ai" )
        ip_addr (str, optional): 手動操作時のIPアドレス
    """
    global is_auto_mode, last_curtain_position_command

    if triggered_by == 'manual':
        # 手動操作の場合
        source = "Web UI" if ip_addr else "Keypad"
        log_action(source, 'シーン実行', f"シーン'{scene_name}'を実行", ip_addr=ip_addr or '--')
        
        # 手動操作が実行されたら、自動モードを強制的にOFFにする
        if is_auto_mode:
            is_auto_mode = False
            update_auto_mode_led()
            log_action(source, 'モード切替', '「手動モード」に切替', ip_addr=ip_addr or '--')
        
        # ★★★ 変更点 ★★★
        # 手動で実行したシーンを「最後に実行したシーン」として記憶する
        # (これにより、AIが同じ操作をしようとした時にスキップされる)
        last_curtain_position_command = scene_name

    else: # triggered_by == 'ai'
        # AIによる操作の場合
        log_action('AI', 'シーン実行', f"シーン'{scene_name}'を実行")

    # 手動操作時のみLCDにシーン名を表示
    if lcd and triggered_by == 'manual':
        lcd.clear()
        lcd.write_string(f"Scene:\n{scene_name}")
    
    # シーン名と実行する関数のマッピング
    scene_actions = {
        "set100": scene_set100, 
        "set0": scene_set0, 
        "set25": scene_set25,
        "set50": scene_set50, 
        "set75": scene_set75,
    }
    
    # 対応する関数を取得
    action = scene_actions.get(scene_name)
    
    if action:
        # アクションの実行（重い処理を含むため別スレッドで実行）
        threading.Thread(target=action, daemon=True).start()
    else:
        log_action('System', 'エラー', f"不明なシーン名: '{scene_name}'")

# --- HDMI切替シーン ---
def scene_set_hdmi1():
    """HDMI 1 (ChromeCast) に切り替える"""
    global current_hdmi_input
    print("Switching to HDMI 1")
    switch_hdmi_input(1)
    current_hdmi_input = "HDMI 1" # 内部状態を更新

def scene_set_hdmi2():
    """HDMI 2 (RaspberryPi) に切り替える"""
    global current_hdmi_input
    print("Switching to HDMI 2")
    switch_hdmi_input(2)
    current_hdmi_input = "HDMI 2" # 内部状態を更新

# --- カーテン・プロジェクター連動シーン ---
def scene_set100():
    """シーン 100% (全閉) & プロジェクターON & HDMI 2"""
    print("\n--- Activating Scene: set100 (Close & Projector ON) ---")
    global current_hdmi_input
    current_hdmi_input = "HDMI 2"   # 先に内部状態を変更
    control_projector_activate()    # プロジェクターON (非同期)
    control_tuya_device([{'code': 'percent_control', 'value': 0}]) # Tuya 0% (全閉)
    time.sleep(1)
    control_switchbot_device(SWITCHBOT_CURTAIN_DEVICE_ID, 40) # SwitchBot 40% (遮光)
    print("[CEC] プロジェクターの起動を待機しています... (60秒)")
    time.sleep(60) # プロジェクターが起動するまで待つ
    switch_hdmi_input(2) # HDMI 2 に切り替え (リトライ付き)

def scene_set0():
    """シーン 0% (全開) & プロジェクターOFF"""
    print("\n--- Activating Scene: set0 (Open & Projector OFF) ---")
    control_tuya_device([{'code': 'percent_control', 'value': 100}]) # Tuya 100% (全開)
    control_switchbot_device(SWITCHBOT_CURTAIN_DEVICE_ID, 0) # SwitchBot 0% (開放)
    time.sleep(1)
    control_projector_off() # プロジェクターOFF (非同期)

def scene_set25():
    """シーン 25% (25%開) & プロジェクターOFF"""
    print("\n--- Activating Scene: set25 (25% Open) ---")
    control_tuya_device([{'code': 'percent_control', 'value': 75}]) # Tuya 75% (25%開)
    control_switchbot_device(SWITCHBOT_CURTAIN_DEVICE_ID, 0) # SwitchBot 0% (開放)
    control_projector_off() # プロジェクターOFF (非同期)

def scene_set50():
    """シーン 50% (半開) & プロジェクターON & HDMI 2"""
    print("\n--- Activating Scene: set50 (Half Open & Projector ON) ---")
    global current_hdmi_input
    current_hdmi_input = "HDMI 2"
    control_projector_activate()
    control_tuya_device([{'code': 'percent_control', 'value': 50}]) # Tuya 50% (半開)
    time.sleep(1)
    control_switchbot_device(SWITCHBOT_CURTAIN_DEVICE_ID, 40) # SwitchBot 40% (遮光)
    print("[CEC] プロジェクターの起動を待機しています... (60秒)")
    time.sleep(60)
    switch_hdmi_input(2)

def scene_set75():
    """シーン 75% (75%閉) & プロジェクターON & HDMI 2"""
    print("\n--- Activating Scene: set75 (75% Closed & Projector ON) ---")
    global current_hdmi_input
    current_hdmi_input = "HDMI 2"
    control_projector_activate()
    control_tuya_device([{'code': 'percent_control', 'value': 25}]) # Tuya 25% (75%閉)
    time.sleep(1)
    control_switchbot_device(SWITCHBOT_CURTAIN_DEVICE_ID, 40) # SwitchBot 40% (遮光)
    print("[CEC] プロジェクターの起動を待機しています... (60秒)")
    time.sleep(60)
    switch_hdmi_input(2)
    

# ==============================================================================
# 9. LED・ステータス表示関数
# ==============================================================================
def blink_red_led():
    """赤色LEDを点滅させる (別スレッドで実行)"""
    while not stop_blinking_flag.is_set(): # 停止フラグが立つまでループ
        GPIO.output(RED_PIN, GPIO.HIGH)
        time.sleep(0.5)
        if stop_blinking_flag.is_set(): break # 待機後にもう一度チェック
        GPIO.output(RED_PIN, GPIO.LOW)
        time.sleep(0.5)

def update_led_status():
    """データ記録モード(is_curtain_logging_paused)に応じてLEDを更新"""
    global stop_blinking_flag
    stop_blinking_flag.set() # 既存の点滅スレッドを停止
    time.sleep(0.1) # スレッドが停止するのを待つ
    GPIO.output(RED_PIN, GPIO.LOW) # LEDを一旦消灯
    GPIO.output(GREEN_PIN, GPIO.LOW)

    if is_curtain_logging_paused:
        # 記録OFF (一時停止中) -> 赤色LEDを点滅
        print("[Status] Logging is PAUSED. LED: Red (Blinking)")
        stop_blinking_flag.clear() # 停止フラグをリセット
        threading.Thread(target=blink_red_led, daemon=True).start() # 点滅スレッド開始
    else:
        # 記録ON (アクティブ) -> 緑色LEDを点灯
        print("[Status] Logging is ACTIVE. LED: Green (Solid)")
        GPIO.output(GREEN_PIN, GPIO.HIGH)

def update_auto_mode_led():
    """自動モード(is_auto_mode)とAI接続状態(is_ai_connected)に応じて青色LEDを制御"""
    global stop_blue_blinking_flag
    stop_blue_blinking_flag.set() # 既存の点滅スレッドを停止
    time.sleep(0.1) # スレッドが停止するのを待つ
    GPIO.output(BLUE_LED_PIN, GPIO.LOW) # 一旦消灯

    if is_auto_mode:
        if is_ai_connected:
            # 自動モードON & AI接続OK -> 青色LED 点灯
            GPIO.output(BLUE_LED_PIN, GPIO.HIGH)
        else:
            # 自動モードON & AI接続NG -> 青色LED 点滅
            stop_blue_blinking_flag.clear() # 停止フラグをリセット
            threading.Thread(target=blink_blue_led, daemon=True).start() # 点滅スレッド開始
    else:
        # 自動モードOFF -> 青色LED 消灯
        GPIO.output(BLUE_LED_PIN, GPIO.LOW)

def blink_blue_led():
    """青色LEDを点滅させる (別スレッドで実行)"""
    while not stop_blue_blinking_flag.is_set(): # 停止フラグが立つまでループ
        GPIO.output(BLUE_LED_PIN, GPIO.HIGH)
        time.sleep(0.5)
        if stop_blue_blinking_flag.is_set(): break
        GPIO.output(BLUE_LED_PIN, GPIO.LOW)
        time.sleep(0.5)


# ==============================================================================
# 10. AI制御・データ送信 関数
# ==============================================================================
def write_log(timestamp, data):
    """センサーデータをローカルのCSVファイルに追記する"""
    header = "timestamp,local_temp_c,local_humidity_percent,local_pressure_hpa,local_light_lux,hub_temp_c,hub_humidity_percent,hub_light_level,tuya_curtain_percent\n"
    # ファイルがなければヘッダーを書き込む
    if not os.path.exists(CSV_FILE_PATH):
        with open(CSV_FILE_PATH, "w") as f:
            f.write(header)
            
    # データをCSV形式で追記
    with open(CSV_FILE_PATH, "a") as f:
        # データがNoneの場合は空文字にするヘルパー
        def get_val(key, format_str="{:.2f}"):
            val = data.get(key)
            if val is None: return ""
            if isinstance(val, str): return val
            return format_str.format(val)
        
        # ログエントリーの文字列を作成
        log_entry = (
            f"{timestamp},"
            f"{get_val('local_temp')},"
            f"{get_val('local_hum')},"
            f"{get_val('local_pres')},"
            f"{get_val('local_lux')},"
            f"{get_val('hub_temp')},"
            f"{get_val('hub_hum')},"
            f"{data.get('hub_lux', '')},"
            f"{data.get('tuya_curtain_percent', '')}\n"
        )
        f.write(log_entry)

def send_data_to_pc_for_training(log_data):
    """(ログ記録ONの時) 学習用データをPCのAIサーバーに送信する"""
    try:
        training_data = log_data.copy()
        
        # 特徴量エンジニアリング: 室内と窓際の温度差を追加
        if 'local_temp_c' in training_data and 'hub_temp_c' in training_data:
            training_data['temp_diff'] = round(training_data['local_temp_c'] - training_data['hub_temp_c'], 1)
        
        # 不要なキーを削除
        training_data.pop("tuya_curtain_position", None)
        
        # PCサーバーの学習用エンドポイントURL (/add_training_data) を生成
        base_url = PC_AI_SERVER_URL.rsplit('/', 1)[0]
        training_url = f"{base_url}/add_training_data"
        
        print(f"[AI Training] Sending data to {training_url}")
        # データをJSON形式でPOST送信
        response = requests.post(training_url, json=training_data, timeout=10)
        response.raise_for_status() # エラーチェック
        
    except Exception as e:
        # PCへの送信失敗
        log_action('System', 'AI学習', f'PCへのデータ送信に失敗: {e}')

def show_ai_indicator_on_lcd():
    """LCDの右上に'*AI*'と2秒間だけ表示して、AIの動作を通知する (未使用)"""
    if lcd:
        try:
            original_pos = lcd.cursor_pos # 元のカーソル位置を保存
            lcd.cursor_pos = (1, 12)
            lcd.write_string("*AI*")
            time.sleep(2)
            lcd.cursor_pos = (1, 12) # 同じ位置に
            lcd.write_string("    ") # スペースを書いて消す
            lcd.cursor_pos = original_pos # カーソル位置を戻す
        except Exception as e:
            print(f"[LCD] AIインジケーターの表示に失敗: {e}")

def get_data_for_ai():
    """
    AI制御に必要な形式でセンサーデータを取得・整形する
    
    Returns:
        dict or None: AIサーバーの入力形式に合わせたセンサーデータ
    """
    local_temp, local_hum, local_pres = read_bme280()
    local_lux = read_bh1750()
    hub_status = get_hub_status()
    hub_temp = hub_status.get("temperature") if hub_status else None
    hub_hum = hub_status.get("humidity") if hub_status else None
    hub_lux = hub_status.get("lightLevel") if hub_status else None
    now = datetime.now()
    
    sensor_data = {
        'hour': now.hour, 
        'month': now.month, 
        'local_temp_c': local_temp,
        'local_humidity_percent': local_hum, 
        'local_pressure_hpa': local_pres,
        'local_light_lux': local_lux, 
        'hub_temp_c': hub_temp,
        'hub_humidity_percent': hub_hum, 
        'hub_light_level': hub_lux
    }
    
    # 必須のセンサーデータが1つでもNone (取得失敗) だったら、制御は実行しない
    if any(v is None for v in sensor_data.values()):
        print("[AI] センサーデータの一部が取得できませんでした。")
        return None
    
    # データを丸めて (小数点第1位) 送信
    for key, value in sensor_data.items():
        if isinstance(value, float):
            sensor_data[key] = round(value, 1)

    return sensor_data

def operate_curtain_from_ai(predicted_label):
    """
    AIの制御ラベル (0-4) に応じて、対応するシーンを実行する
    
    Args:
        predicted_label (int): AIサーバーが返した制御ラベル (0:set0, 1:set25, ...)
    """
    global last_curtain_position_command

    # AIのラベル (0-4) とシーン名のマッピング
    label_to_scene = {
        0: 'set0', 1: 'set25', 2: 'set50', 3: 'set75', 4: 'set100'
    }
    # AIのラベルとパーセント値 (音声案内用) のマッピング
    label_to_percent = {
        0: 0, 1: 25, 2: 50, 3: 75, 4: 100
    }

    # ラベルに対応するシーン名を取得
    target_scene = label_to_scene.get(predicted_label)
    
    if target_scene is None:
        print(f"[AI] 不明な制御ラベルです: {predicted_label}")
        return

    # ★★★ 制御スキップ処理 ★★★
    # 最後に実行したシーン (手動またはAI) と同じであれば、操作をスキップする
    if target_scene == last_curtain_position_command:
        print(f"[AI] シーン '{target_scene}' は既に実行済みのためスキップします。")
        return

    print(f"[AI] 制御に基づき、シーン '{target_scene}' を実行します。")
    
    # --- 音声案内処理 ---
    target_percent = label_to_percent.get(predicted_label)
    if target_percent is not None:
        message = f"カーテンを{target_percent}パーセントの位置に自動制御します"
        # 音声再生は時間がかかるため、別スレッドで実行 (daemon=True)
        threading.Thread(target=speak_message, args=(message,), daemon=True).start()
        # 音声が少し先に始まってからカーテンが動き出すように、0.5秒待つ
        time.sleep(0.5) 
    
    # シーンを実行 (triggered_by='ai' を指定)
    execute_scene(target_scene, triggered_by='ai')
    
    # 最後に実行したシーンを記録
    last_curtain_position_command = target_scene


# ==============================================================================
# 11. バックグラウンドスレッド (ループ処理)
# ==============================================================================
def auto_control_loop():
    """
    バックグラウンドでAIによる自動制御を定期実行するスレッド
    (AUTO_CONTROL_INTERVAL_SECONDS ごとに実行)
    """
    print("[AI] 自動制御ループを開始します。")
    while True:
        # 自動モードがONの時だけ実行
        if is_auto_mode:
            print("[AI] 自動モードON。センサーデータを取得し制御を実行します。")
            sensor_data = get_data_for_ai() # AI用のデータを取得
            
            if sensor_data:
                try:
                    # PCのAIサーバーにデータをPOST送信
                    response = requests.post(PC_AI_SERVER_URL, json=sensor_data, timeout=15)
                    response.raise_for_status() # エラーチェック
                    result = response.json()
                    print(f"[AI] PCから制御位置を受信: {result}")
                    
                    # 'predicted_label' キーがあれば制御を実行
                    predicted_label = result.get('predicted_label')
                    if predicted_label is not None:
                        operate_curtain_from_ai(predicted_label)
                        
                except requests.exceptions.RequestException as e:
                    # AIサーバーへの接続失敗 (LED点滅処理は check_ai_connection_loop が担当)
                    logging.error(f"Failed to connect to PC AI server: {e}")
                    
        # 次の制御実行まで待機
        time.sleep(AUTO_CONTROL_INTERVAL_SECONDS)

def projector_status_loop():
    """
    バックグラウンドでプロジェクターの状態を定期的に取得・更新するスレッド
    (30秒ごとに実行)
    """
    global current_projector_status
    while True:
        status = get_projector_status()
        # 取得に失敗('Error')した場合のみ、2秒後にもう一度だけ再試行
        if status == 'Error':
            time.sleep(2)
            status = get_projector_status()
        
        current_projector_status = status # グローバル変数を更新
        time.sleep(30) # 30秒待機

def check_ai_connection_loop():
    """
    バックグラウンドでAIサーバーへの接続を定期的に確認するスレッド
    (60秒ごとに実行)
    """
    global is_ai_connected
    while True:
        previous_status = is_ai_connected # 前回の接続状態
        try:
            # PCサーバーの/pingエンドポイントに接続試行
            ping_url = PC_AI_SERVER_URL.replace('/predict', '/ping')
            response = requests.get(ping_url, timeout=5)
            is_ai_connected = (response.status_code == 200) # 200 OK なら接続成功
        except requests.exceptions.RequestException:
            is_ai_connected = False # タイムアウト等は接続失敗
        
        # 状態が変化した瞬間にログを記録
        if is_ai_connected != previous_status:
            status_text = "接続" if is_ai_connected else "切断"
            log_action('AI', '接続', f'AIサーバー{status_text}')
        
        # LEDの状態を更新 (自動モードONかつ接続NGなら点滅)
        update_auto_mode_led()
        
        time.sleep(60) # 60秒待機

def background_tasks_loop():
    """
    メインのバックグラウンドタスク (キーパッド監視, LCD更新, ログ記録)
    このスレッドはビジーループ (time.sleep(0.05)) で高速に回り、キー入力を検知する
    """
    global is_curtain_logging_paused, is_auto_mode, latest_sensor_data
    
    last_lcd_update = 0 # 最後のLCD更新時刻
    last_log_time = 0   # 最後のセンサーログ記録時刻
    
    print("\n[Main] Background task loop started. Ready for input.")
    update_led_status() # LEDの初期状態を更新

    while True:
        # --- 1. キーパッドのスキャン ---
        key_pressed = None
        # 列(COL)ピンを順番にHIGHにする
        for c, col_pin in enumerate(KEYPAD_COL_PINS):
            GPIO.output(col_pin, GPIO.HIGH)
            # 行(ROW)ピンの入力をチェック
            for r, row_pin in enumerate(KEYPAD_ROW_PINS):
                if GPIO.input(row_pin) == GPIO.HIGH: # 押された！
                    key_pressed = KEYPAD_MAP[r][c] # 押されたキーを特定
                    # キーが離されるまで待つ (チャタリング防止)
                    while GPIO.input(row_pin) == GPIO.HIGH:
                        time.sleep(0.1)
                    break
            GPIO.output(col_pin, GPIO.LOW) # 次の列のスキャンのためLOWに戻す
            if key_pressed:
                break # 1ループで1キーのみ処理
        
        # --- 2. キー入力の処理 ---
        if key_pressed:
            # シーン実行キー
            scene_map = {"1":"set0", "2":"set25", "3":"set50", "4":"set75", "5":"set100"}
            # その他機能キー
            assigned_keys = list(scene_map.keys()) + ['*', '0', '7', '8', '9', 'C', '#', 'D']
            
            if key_pressed in assigned_keys:
                beep() # キー入力音
                scene_to_run = scene_map.get(key_pressed)

                if scene_to_run:
                    execute_scene(scene_to_run) # シーン実行 (ログは関数内)
                elif key_pressed == '7':
                    log_action('Keypad', 'HDMI切替', 'HDMI 1 に切替')
                    scene_set_hdmi1()
                elif key_pressed == '8':
                    log_action('Keypad', 'HDMI切替', 'HDMI 2 に切替')
                    scene_set_hdmi2()
                elif key_pressed == '*':
                    log_action('Keypad', 'プロジェクター', 'OFFを実行')
                    control_projector_off()
                elif key_pressed == '0':
                    log_action('Keypad', 'プロジェクター', 'ONを実行')
                    control_projector_activate()
                elif key_pressed == '9':
                    is_auto_mode = True
                    log_action('Keypad', 'モード切替', '「自動モード」に切替')
                    update_auto_mode_led()
                elif key_pressed == 'C':
                    is_auto_mode = False
                    log_action('Keypad', 'モード切替', '「手動モード」に切替')
                    update_auto_mode_led()
                elif key_pressed == '#':
                    is_curtain_logging_paused = True
                    log_action('Keypad', 'データ記録', '「OFF」に切替')
                    update_led_status()
                elif key_pressed == 'D':
                    is_curtain_logging_paused = False
                    log_action('Keypad', 'データ記録', '「ON」に切替')
                    update_led_status()
                
                last_lcd_update = 0 # キー操作後はすぐにLCDを更新させる

        # --- 3. LCDの更新 (5秒ごと) ---
        if time.time() - last_lcd_update > 5:
            if lcd:
                try:
                    curtain_status = get_tuya_curtain_status()
                    proj_status = get_projector_status() # プロジェクター状態はLCD更新のたびに取得
                    
                    lcd.clear()
                    lcd.cursor_pos = (0, 0) # 1行目
                    if curtain_status['state'] == 'active':
                        lcd.write_string("Curtain: Active   ")
                    else:
                        lcd.write_string(f"Curtain: {curtain_status['position']}% ")

                    lcd.cursor_pos = (1, 0) # 2行目
                    lcd.write_string(f"Projector: {proj_status}")
                except Exception as e:
                    print(f"[Error] Failed to update LCD: {e}")
            last_lcd_update = time.time() # 更新時刻を記録
        
        # --- 4. センサーログの記録 (LOG_INTERVAL_SECONDS ごと) ---
        if time.time() - last_log_time >= LOG_INTERVAL_SECONDS:
            current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{current_time_str}] Starting periodic data log...")
            
            # 1. すべてのセンサーデータを取得
            data_for_csv = get_all_sensor_data()

            # 2. 取得したデータをAPI配信用にグローバル変数へコピー
            latest_sensor_data = data_for_csv.copy()
            
            # 3. ローカルのCSVファイルに記録
            write_log(current_time_str, data_for_csv)
            
            # 4. (ログ記録ONの時のみ) PCへ学習データを送信
            if not is_curtain_logging_paused:
                data_for_ai = get_data_for_ai() # AI送信用の形式で再取得・整形
                curtain_pos = data_for_csv.get('tuya_curtain_percent')

                # データが正しく取れた場合のみ送信
                if data_for_ai and isinstance(curtain_pos, (int, float)):
                    log_for_pc = data_for_ai.copy()
                    log_for_pc['timestamp'] = current_time_str
                    log_for_pc['tuya_curtain_percent'] = curtain_pos
                    send_data_to_pc_for_training(log_for_pc)
            
            print(f"[{current_time_str}] Data logged.")
            last_log_time = time.time() # 更新時刻を記録

        # --- 5. メインループの待機 ---
        # 0.05秒待機 (CPU使用率を抑えつつ、キー入力に即座に反応できる程度)
        time.sleep(0.05)


# ==============================================================================
# 12. Flask Webサーバー (ルーティング)
# ==============================================================================
@app.route('/')
def index():
    """ 
    Web UIのメインページ (index.html) を表示 
    初回アクセス時にIPアドレスをログに記録
    """
    client_ip = request.remote_addr
    if client_ip not in connected_ips:
        log_action('Web UI', '接続', 'Web UIに接続', ip_addr=client_ip)
        connected_ips.add(client_ip)
    # templates/index.html をレンダリングして返す
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def get_status_for_app():
    """ Web UI (JavaScript) から非同期で呼び出され、最新の状態をJSONで返す """
    # プロジェクターがOFFの時は、HDMI入力状態を '---' にする
    hdmi_status = current_hdmi_input if current_projector_status == 'ON' else '---'
    
    curtain_status = get_tuya_curtain_status()
    
    # グローバル変数に保持されている最新の状態を返す
    return jsonify({
        'curtain_position': curtain_status['position'],
        'projector_status': current_projector_status,
        'hdmi_status': hdmi_status,
        'logging_paused': is_curtain_logging_paused,
        'auto_mode': is_auto_mode,
        'ai_connection_status': is_ai_connected
    })

@app.route('/api/sensor_data', methods=['GET'])
def get_sensor_data_api():
    """ 外部 (PCなど) から最新のセンサーデータを取得するためのAPIエンドポイント """
    if not latest_sensor_data:
        # 起動直後などでまだデータがない場合
        return jsonify({"error": "No data available yet."}), 404

    # 外部APIの仕様に合わせてキー名を変更して返す
    return jsonify({
        "outdoor_temp": latest_sensor_data.get('local_temp'),
        "outdoor_humidity": latest_sensor_data.get('local_hum'),
        "outdoor_pressure": latest_sensor_data.get('local_pres'),
        "outdoor_light": latest_sensor_data.get('local_lux'),
        "indoor_temp": latest_sensor_data.get('hub_temp'),
        "indoor_humidity": latest_sensor_data.get('hub_hum'),
        "window_light_level": latest_sensor_data.get('hub_lux'),
        "curtain_position": latest_sensor_data.get('tuya_curtain_percent')
    })

@app.route('/command/<scene_name>', methods=['POST'])
def handle_command_from_app(scene_name):
    """ Web UI からのシーン実行リクエスト ( /command/set0 など) """
    beep()
    execute_scene(scene_name, ip_addr=request.remote_addr) # IPアドレスを渡して実行
    return jsonify({'status': 'success', 'message': f'Scene {scene_name} activated.'})

@app.route('/logging/<action>', methods=['POST'])
def control_logging_from_app(action):
    """ Web UI からのデータ記録ON/OFFリクエスト ( /logging/on または /logging/off ) """
    global is_curtain_logging_paused
    beep()
    if action.lower() == 'on':
        is_curtain_logging_paused = False
        status_text = 'ON'
    elif action.lower() == 'off':
        is_curtain_logging_paused = True
        status_text = 'OFF'
    else:
        return jsonify({'status': 'error', 'message': 'Invalid action'}), 400
    
    log_action('Web UI', 'データ記録', f'「{status_text}」に切替', ip_addr=request.remote_addr)
    update_led_status() # LEDの状態を即時更新
    return jsonify({'status': 'success', 'logging_paused': is_curtain_logging_paused})

@app.route('/log')
def view_log():
    """ 操作ログ (log.html) を表示 """
    try:
        # CSVファイルをpandasで読み込む
        df = pd.read_csv(LOG_CSV_FILE, encoding='utf-8')
        # 新しいログが上に来るように逆順にする
        df = df.iloc[::-1]
        # DataFrameをHTMLテーブルに変換
        log_table = df.to_html(index=False, justify='left', classes='log-table')
    except FileNotFoundError:
        log_table = "<p>ログファイルがまだ作成されていません。</p>"
    except Exception as e:
        log_table = f"<p>ログの読み込みに失敗しました: {e}</p>"

    # templates/log.html をレンダリングし、log_table変数を渡す
    # (HTML側で {{ log_table|safe }} として展開される)
    return render_template('log.html', log_table=log_table)

@app.route('/mode/<new_mode>', methods=['POST'])
def set_control_mode(new_mode):
    """ Web UI からのモード切替リクエスト ( /mode/auto または /mode/manual ) """
    global is_auto_mode
    is_auto_mode = (new_mode == 'auto')
    mode_text = "自動" if is_auto_mode else "手動"
    
    log_action('Web UI', 'モード切替', f'「{mode_text}モード」に切替', ip_addr=request.remote_addr)
    update_auto_mode_led() # LEDの状態を即時更新
    beep()
    return jsonify({'status': 'success', 'auto_mode': is_auto_mode})

@app.route('/projector/<action>', methods=['POST'])
def handle_projector_command(action):
    """ Web UI からのプロジェクター電源操作 ( /projector/on または /projector/off ) """
    beep()
    if action == 'on':
        log_action('Web UI', 'プロジェクター', 'ONを実行', ip_addr=request.remote_addr)
        control_projector_activate()
    elif action == 'off':
        log_action('Web UI', 'プロジェクター', 'OFFを実行', ip_addr=request.remote_addr)
        control_projector_off()
    return jsonify({'status': 'success'})

@app.route('/hdmi/<port_name>', methods=['POST'])
def handle_hdmi_command(port_name):
    """ Web UI からのHDMI入力切替 ( /hdmi/hdmi1 または /hdmi/hdmi2 ) """
    beep()
    if port_name == 'hdmi1':
        scene_set_hdmi1()
        log_text = 'HDMI 1 に切替'
    elif port_name == 'hdmi2':
        scene_set_hdmi2()
        log_text = 'HDMI 2 に切替'
    else:
        return jsonify({'status': 'error', 'message': 'Invalid port'}), 400
    
    log_action('Web UI', 'HDMI切替', log_text, ip_addr=request.remote_addr)
    return jsonify({'status': 'success'})


# ==============================================================================
# 13. 天気情報 取得関数
# ==============================================================================
def get_weather_info():
    """
    Yahoo!天気から今日の天気(日本語テキスト)、最高・最低気温をスクレイピングする
    """
    # 神奈川県厚木市のURL (固定)
    WEATHER_URL = "https://weather.yahoo.co.jp/weather/jp/14/4610.html"
    # PCのブラウザを装うためのUser-Agent
    headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }

    try:
        response = requests.get(WEATHER_URL, headers=headers, timeout=10)
        response.encoding = 'utf-8' # 文字コードをUTF-8に
        response.raise_for_status() # エラーチェック
        
        # BeautifulSoupでHTMLをパース
        soup = BeautifulSoup(response.text, 'html.parser')

        # 「今日」の天気情報が含まれるエリアをCSSセレクタで特定
        today_weather_area = soup.select_one('#main > div.forecastCity > table > tr > td:nth-child(1)')
        if not today_weather_area:
            return {"text": "---", "high": "--", "low": "--"}

        # 天気テキスト (例: "曇り")
        weather_text = today_weather_area.select_one('p.pict').get_text(strip=True)
        # 最高気温 (例: "16℃[+2]")
        high_temp_raw = today_weather_area.select_one('ul.temp li.high').get_text(strip=True)
        # 最低気温 (例: "10℃[-1]")
        low_temp_raw = today_weather_area.select_one('ul.temp li.low').get_text(strip=True)

        # 正規表現 (re.sub) で [ ] の中身を削除
        high_temp = re.sub(r'\[.*\]', '', high_temp_raw).replace('[-]', '--')
        low_temp = re.sub(r'\[.*\]', '', low_temp_raw).replace('[-]', '--')

        return {
            "text": weather_text,
            "high": high_temp,
            "low": low_temp
        }
    except Exception as e:
        print(f"天気情報の取得エラー: {e}")
        log_action('Weather', '天気情報', f"取得エラー: {e}")
        return {"text": "---", "high": "--", "low": "--"}

def periodic_weather_updater():
    """
    天気を定期的に取得し、グローバル変数(weather_data)を更新するスレッド
    (30分ごとに実行)
    """
    global weather_data

    print("[Weather] 天気情報を更新します...")
    new_data = get_weather_info()
    weather_data = new_data # グローバル変数を更新
    print(f"[Weather] 更新完了: {weather_data}")
    log_action('Weather', '天気情報', f"取得: {weather_data['text']} {weather_data['high']}/{weather_data['low']}")

    # 30分 (1800秒) 後に再度この関数を実行する (Timerスレッド)
    threading.Timer(1800, periodic_weather_updater).start()


# ==============================================================================
# 14. カメラ映像生成 (ストリーミング)
# ==============================================================================
def generate_frames():
    """
    カメラからフレームを取得し、Pillowを使ってセンサー情報を描画して
    Motion JPEG形式でyield (生成) する
    """
    global latest_sensor_data, weather_data

    # --- 描画設定 ---
    try:
        # 日本語表示用のフォント (Noto Sans CJK)
        # (事前に sudo apt-get install fonts-noto-cjk でインストールが必要)
        font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
        font_time = ImageFont.truetype(font_path, 48)
        font_main_label = ImageFont.truetype(font_path, 32)
        font_main_value = ImageFont.truetype(font_path, 52)
        font_main_unit = ImageFont.truetype(font_path, 32)
        font_v_label = ImageFont.truetype(font_path, 40)
        font_weather_temp_max = ImageFont.truetype(font_path, 38)
        font_weather_temp_min = ImageFont.truetype(font_path, 38)
        font_weather_slash = ImageFont.truetype(font_path, 38)
        font_weather_text = ImageFont.truetype(font_path, 38)
    except IOError as e:
        # フォントが見つからない場合、デフォルトフォントで続行 (文字化けする)
        print(f"[CRITICAL ERROR] メインの日本語フォントが読み込めません: {e}")
        print("         (sudo apt-get install fonts-noto-cjk を確認してください)")
        font_time, font_main_label, font_main_value, font_main_unit, font_v_label = (ImageFont.load_default(),) * 5
        font_weather_temp_max, font_weather_temp_min, font_weather_slash, font_weather_text = (ImageFont.load_default(),) * 4

    # 色の設定
    COLOR_BG_INDOOR = (255, 165, 0) # 室内 (オレンジ)
    COLOR_BG_OUTDOOR = (30, 144, 255) # 窓際 (ブルー)
    COLOR_WHITE = (255, 255, 255)   # 基本テキスト
    COLOR_GREEN = (140, 195, 74)  # センサー値
    COLOR_ORANGE_TEMP = (255, 120, 0) # 最高気温
    COLOR_AQUA_TEMP = (0, 191, 255) # 最低気温
    COLOR_BLACK_OUTLINE = (0, 0, 0) # 枠線
    STROKE_WIDTH = 2 # 枠線の太さ

    while True:
        # --- 1. カメラフレームの取得 ---
        if camera is None or not camera.isOpened():
            # カメラが初期化失敗した場合、エラー画像を生成
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(frame, "Camera not found.", (400, 360), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        else:
            # カメラから1フレーム読み取り
            success, frame = camera.read()
            if not success:
                continue # 読み取り失敗時はスキップ

        # --- 2. 描画準備 ---
        # 最新のセンサーデータを取得
        s_data = latest_sensor_data
        
        # OpenCV (BGR) から Pillow (RGB) 形式に変換
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(pil_img)

        # --- 3. 描画ヘルパー関数 (枠線付きテキスト) ---
        def draw_text_with_outline(xy, text, font, fill_color, draw_outline=True, **kwargs):
            """指定された座標にテキストを描画する。draw_outline=Trueの場合に黒枠も描画"""
            if draw_outline:
                # 先に黒枠を描画
                draw.text(xy, text, font=font, fill=COLOR_BLACK_OUTLINE, stroke_width=STROKE_WIDTH, **kwargs)
            # 上からメインの色のテキストを描画
            draw.text(xy, text, font=font, fill=fill_color, **kwargs)

        # --- 4. 各種情報の描画 ---
        # 4-1. 日時
        now = datetime.now()
        dow = ['月', '火', '水', '木', '金', '土', '日'][now.weekday()]
        time_str = now.strftime(f"%m/%d({dow}) %H:%M")
        draw_text_with_outline((20, 10), time_str, font=font_time, fill_color=COLOR_WHITE)

        # 4-2. 天気情報
        weather_start_x = 20
        weather_start_y = 80
        # 天気テキスト (例: "曇り")
        weather_text_str = weather_data['text']
        draw_text_with_outline((weather_start_x + 10, weather_start_y), weather_text_str, font=font_weather_text, fill_color=COLOR_WHITE)
        
        # 天気テキストの幅に合わせて気温の開始位置を調整
        weather_text_width = draw.textlength(weather_text_str, font=font_weather_text)
        temp_start_x = weather_start_x + 10 + weather_text_width + 15
        
        # 最高気温
        max_temp_str = weather_data['high']
        max_temp_width = draw.textlength(max_temp_str, font=font_weather_temp_max)
        draw_text_with_outline((temp_start_x, weather_start_y), max_temp_str, font=font_weather_temp_max, fill_color=COLOR_ORANGE_TEMP)
        
        # スラッシュ
        slash_x = temp_start_x + max_temp_width + 5
        draw_text_with_outline((slash_x, weather_start_y), "/", font=font_weather_slash, fill_color=COLOR_WHITE)
        
        # 最低気温
        min_temp_str = weather_data['low']
        slash_width = draw.textlength("/", font=font_weather_slash)
        draw_text_with_outline((slash_x + slash_width + 5, weather_start_y), min_temp_str, font=font_weather_temp_min, fill_color=COLOR_AQUA_TEMP)

        # 4-3. センサー情報 (背景とラベル)
        indoor_bg_y_offset = 145
        indoor_rect = [20, indoor_bg_y_offset, 100, indoor_bg_y_offset + 215]
        draw.rectangle(indoor_rect, fill=COLOR_BG_INDOOR)
        # 「室内」ラベル (縦書き・中央揃え)
        indoor_text = "室\n\n内"
        rect_center_x = (indoor_rect[0] + indoor_rect[2]) / 2
        rect_center_y = (indoor_rect[1] + indoor_rect[3]) / 2
        draw_text_with_outline((rect_center_x, rect_center_y), indoor_text, font=font_v_label, fill_color=COLOR_WHITE, anchor="mm", align="center", draw_outline=False)

        outdoor_bg_y_offset = indoor_bg_y_offset + 215 + 25
        outdoor_rect = [20, outdoor_bg_y_offset, 100, outdoor_bg_y_offset + 290]
        draw.rectangle(outdoor_rect, fill=COLOR_BG_OUTDOOR)
        # 「窓際」ラベル
        outdoor_text = "窓\n\n際"
        rect_center_x = (outdoor_rect[0] + outdoor_rect[2]) / 2
        rect_center_y = (outdoor_rect[1] + outdoor_rect[3]) / 2
        draw_text_with_outline((rect_center_x, rect_center_y), outdoor_text, font=font_v_label, fill_color=COLOR_WHITE, anchor="mm", align="center", draw_outline=False)

        # 4-4. センサーデータ描画ヘルパー
        def draw_sensor_data(x, y_bottom, label, value, unit, digits=1):
            """ Y座標を下揃え基準線としてセンサーテキストを描画 """
            draw_text_with_outline((x, y_bottom), label, font=font_main_label, fill_color=COLOR_WHITE, anchor="lb")
            val_str = f"{value:.{digits}f}" if isinstance(value, (int, float)) else "--"
            draw_text_with_outline((x + 100, y_bottom), val_str, font=font_main_value, fill_color=COLOR_GREEN, anchor="lb")
            val_width = draw.textlength(val_str, font=font_main_value)
            draw_text_with_outline((x + 100 + val_width + 5, y_bottom), unit, font=font_main_unit, fill_color=COLOR_WHITE, anchor="lb")

        # 4-5. 各センサーデータを描画
        # 室内
        draw_sensor_data(120, indoor_bg_y_offset + 65, "温度", s_data.get('hub_temp'), "℃")
        draw_sensor_data(120, indoor_bg_y_offset + 140, "湿度", s_data.get('hub_hum'), "%", digits=0)
        draw_sensor_data(120, indoor_bg_y_offset + 215, "照度", s_data.get('hub_lux'), "レベル", digits=0)
        # 窓際
        draw_sensor_data(120, outdoor_bg_y_offset + 65, "温度", s_data.get('local_temp'), "℃")
        draw_sensor_data(120, outdoor_bg_y_offset + 140, "湿度", s_data.get('local_hum'), "%")
        draw_sensor_data(120, outdoor_bg_y_offset + 215, "照度", s_data.get('local_lux'), "Lux")
        draw_sensor_data(120, outdoor_bg_y_offset + 290, "気圧", s_data.get('local_pres'), "hPa", digits=0)

        # --- 5. JPEGにエンコード ---
        # Pillow (RGB) から OpenCV (BGR) 形式に戻す
        frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # メモリ上でJPEG形式 (品質90) にエンコード
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ret:
            continue

        # --- 6. Motion JPEG 形式で yield ---
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n' # フレームの境界
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

# --- ▼▼▼ 抜け落ちていた /monitor ルートをここに追加 ▼▼▼ ---
@app.route('/monitor')
def monitor_page():
    """ リアルタイムモニターページ (monitor.html) を表示 """
    # templates/monitor.html をレンダリングして返す
    return render_template('monitor.html')
# --- ▲▲▲ 追加完了 ▲▲▲ ---

@app.route('/video_feed')
def video_feed():
    """ 映像ストリーミング (/monitor で使われる) を配信するためのエンドポイント """
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# ==============================================================================
# 15. プログラム実行 (メイン)
# ==============================================================================
if __name__ == '__main__':
    try:
        log_action('System', 'システム', '起動')

        # --- カメラの初期化 ---
        print("[Init] Initializing Camera...")
        camera = cv2.VideoCapture(0) # デバイス0番のカメラを開く
        if not camera.isOpened():
            print("[CRITICAL] Failed to open camera.") # 開けなかった場合
        else:
            # カメラの解像度を16:9 (1280x720) に設定
            camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            print("[Init] Camera initialized successfully (1280x720).")
        
        # --- 各種初期化の実行 ---
        if init_i2c() and init_gpio() and init_tuya_api():
            # I2C, GPIO, Tuya APIすべて成功したらセンサーをセットアップ
            setup_bme280()
            
            # 天気情報の定期更新スレッドを開始
            threading.Thread(target=periodic_weather_updater, daemon=True).start()

            # --- 各種バックグラウンドスレッドを開始 ---
            # メインのバックグラウンドタスク（キーパッド監視、LCD更新、ログ記録）
            threading.Thread(target=background_tasks_loop, daemon=True).start()
            # AI自動制御ループ
            threading.Thread(target=auto_control_loop, daemon=True).start()
            # AIサーバー接続確認ループ
            threading.Thread(target=check_ai_connection_loop, daemon=True).start()
            # プロジェクター状態確認ループ
            threading.Thread(target=projector_status_loop, daemon=True).start()

            # LEDの初期状態を更新
            update_auto_mode_led()
            
            # --- Flask Webサーバーを起動 ---
            print("[Main] Starting Flask web server on http://0.0.0.0:5000")
            app.run(host='0.0.0.0', port=5000)
            
        else:
            # 初期化に失敗した場合
            print("\n[CRITICAL] System initialization failed.")
            if lcd: lcd.write_string("System Init FAIL")
            
    except KeyboardInterrupt:
        # Ctrl+C で終了した場合
        print("\nProgram terminated by user (Ctrl+C).")
    except Exception as e:
        # その他の予期せぬエラー
        print(f"[CRITICAL] An unexpected error occurred in main: {e}")
        
    finally:
        # --- 終了処理 ---
        log_action('System', 'システム', '終了')
        
        # カメラリソースを解放
        if camera and camera.isOpened():
            print("Releasing camera resource...")
            camera.release()
            
        # GPIOピンをクリーンアップ
        print("Cleaning up GPIO...")
        GPIO.cleanup()
        
        # LCDに終了メッセージを表示
        if lcd:
            lcd.clear()
            lcd.write_string("System Shutdown")