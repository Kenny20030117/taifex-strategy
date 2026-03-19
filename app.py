import streamlit as st
import pandas as pd
import requests
import io
import urllib3
from datetime import datetime, timedelta
import ssl

# Suppress insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="台指期多空策略", layout="centered")

st.markdown("""
<style>
.big-font {
    font-size: 26px !important;
    font-weight: bold;
}
.red-font {
    color: #d32f2f !important;
    font-size: 28px !important;
    font-weight: bold;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}
.green-font {
    color: #2e7d32 !important;
    font-size: 28px !important;
    font-weight: bold;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}
.yellow-font {
    color: #f57f17 !important;
    font-size: 28px !important;
    font-weight: bold;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
}
.card {
    background-color: #ffffff;
    border: 1px solid #444444;
    margin-bottom: 20px;
    color: #000000;
    font-family: "Microsoft JhengHei", "PingFang TC", sans-serif;
}
.metrics-table {
    width: 100%;
    text-align: left;
    border-collapse: collapse;
    font-size: 22px;
}
.metrics-table td {
    padding: 12px 15px;
    border: 1px solid #e0e0e0;
    border-bottom: 1px solid #444444;
}
.metrics-table tr:first-child td {
    border-top: 1px solid #444444;
}
.metrics-table .highlight {
    background-color: #ffff00;
    color: #000000;
    font-weight: bold;
}
.metrics-table .col-val {
    text-align: right;
    font-family: Arial, sans-serif;
    letter-spacing: 1px;
}
.metrics-table .col-unit {
    width: 50px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=900)
def get_taifex_data(date_str, session='day'):
    url = 'https://www.taifex.com.tw/cht/3/futContractsDate' if session == 'day' else 'https://www.taifex.com.tw/cht/3/futContractsDateAh'
    try:
        resp = requests.post(url, data={'queryDate': date_str, 'queryType': '1'}, timeout=10)
        dfs = pd.read_html(io.StringIO(resp.text))
        for df in dfs:
            if len(df) > 10:
                tx, mtx, tmf = 0, 0, 0
                val_col = 13 if session == 'day' else 7
                for i in range(min(100, len(df))):
                    try:
                        col1 = str(df.iloc[i, 1]).strip()
                        col2 = str(df.iloc[i, 2]).strip()
                        val_str = str(df.iloc[i, val_col]).replace(',', '')
                        
                        if '外資' in col2:
                            val = int(val_str)
                            if '臺股期貨' in col1: tx = val
                            elif '小型臺指' in col1: mtx = val
                            elif '微型臺指' in col1: tmf = val
                    except:
                        pass
                
                if tx != 0 or mtx != 0 or tmf != 0:
                    return {'tx': tx, 'mtx': mtx, 'tmf': tmf}
    except Exception as e:
        print(f'Error TAIFEX {session} on {date_str}:', e)
    return None

@st.cache_data(ttl=900)
def get_twse_spot(date_str_no_slash):
    url = f'https://www.twse.com.tw/rwd/zh/fund/BFI82U?date={date_str_no_slash}&response=json'
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, verify=False, timeout=10)
        data = resp.json()
        if data.get('stat') == 'OK' and 'data' in data:
            for row in data['data']:
                if '外資' in row[0] and '不含' in row[0]:
                    return int(row[3].replace(',', ''))
    except Exception as e:
        print(f'Error TWSE on {date_str_no_slash}:', e)
    return None

def calc_signal(futures_net, spot_net):
    if futures_net is None or spot_net is None:
        return 'UNKNOWN', ''

    if futures_net > 0 and spot_net > 0:
        return 'LONG', '偏多看待，逢低買進'
    elif futures_net < 0 and spot_net < 0:
        return 'SHORT', '偏空看待，逢低買進'
    else:
        return 'NEUTRAL', '多空不明'

st.title("📊 台指期外資籌碼策略")

# Date selection
default_date = datetime.now()
selected_date = st.date_input("選擇日期", default_date)
date_str = selected_date.strftime("%Y/%m/%d")
date_str_no_slash = selected_date.strftime("%Y%m%d")

st.markdown(f"### {selected_date.strftime('%Y/%m/%d')} 籌碼數據")

with st.spinner("獲取數據中..."):
    # Fetch Data
    day_data = get_taifex_data(date_str, 'day')
    night_data = get_taifex_data(date_str, 'night')
    spot_amount = get_twse_spot(date_str_no_slash)

    # Calculate values
    day_total = 0
    if day_data:
        day_total = day_data['tx'] + (day_data['mtx'] / 4) + (day_data['tmf'] / 20)
    
    night_total = 0
    if night_data:
        night_total = night_data['tx'] + (night_data['mtx'] / 4) + (night_data['tmf'] / 20)
        
    day_session_only = 0
    if day_data and night_data:
        day_session_only = day_total - night_total

    spot_billion = 0
    if spot_amount is not None:
        spot_billion = spot_amount / 100000000 # 換算成「億」

    # Display Metrics in Table
    if day_data and night_data:
        html_table = f"""
        <div class="card">
        <table class="metrics-table">
            <tr>
                <td>外資期貨當日買賣超</td>
                <td class="col-val">{int(day_total)}</td>
                <td class="col-unit">口</td>
            </tr>
            <tr>
                <td>外資期貨夜盤買賣超</td>
                <td class="col-val">{int(night_total)}</td>
                <td class="col-unit">口</td>
            </tr>
            <tr class="highlight">
                <td>日盤期貨多空單數據</td>
                <td class="col-val">{int(day_session_only)}</td>
                <td class="col-unit">口</td>
            </tr>
            <tr>
                <td>外資現貨當日買賣超</td>
                <td class="col-val">{spot_billion:.1f}</td>
                <td class="col-unit">億</td>
            </tr>
        </table>
        <div style="text-align: right; padding: 10px 15px; font-size: 15px; background-color: #f7f7f7; border-top: 1px solid #e0e0e0; font-family: sans-serif;">
            <span style="color: #666; margin-right: 5px;">🔗 資料查詢來源:</span>
            <a href="https://www.taifex.com.tw/cht/3/futContractsDate" target="_blank" style="color: #0d47a1; text-decoration: none; font-weight: bold; margin-left: 5px;">期交所日盤</a>
            <span style="color: #ccc; margin: 0 5px;">|</span>
            <a href="https://www.taifex.com.tw/cht/3/futContractsDateAh" target="_blank" style="color: #0d47a1; text-decoration: none; font-weight: bold;">期交所夜盤</a>
            <span style="color: #ccc; margin: 0 5px;">|</span>
            <a href="https://www.twse.com.tw/zh/trading/foreign/bfi82u.html" target="_blank" style="color: #0d47a1; text-decoration: none; font-weight: bold;">證交所現貨</a>
        </div>
        </div>
        """
        st.markdown(html_table, unsafe_allow_html=True)
        
        # Determine Signal
        signal_type, signal_msg = calc_signal(day_session_only, spot_amount)
        
        # To determine "first time direction change", we need the previous day value
        # Let's find the previous trading day (ignoring weekends)
        prev_date = selected_date - timedelta(days=1)
        while prev_date.weekday() >= 5: # 5=Sat, 6=Sun
            prev_date -= timedelta(days=1)
            
        prev_date_str = prev_date.strftime("%Y/%m/%d")
        prev_date_no_slash = prev_date.strftime("%Y%m%d")
        
        pd_day = get_taifex_data(prev_date_str, 'day')
        pd_night = get_taifex_data(prev_date_str, 'night')
        pd_spot = get_twse_spot(prev_date_no_slash)
        
        prev_signal = 'UNKNOWN'
        if pd_day and pd_night:
            p_day_tot = pd_day['tx'] + (pd_day['mtx'] / 4) + (pd_day['tmf'] / 20)
            p_night_tot = pd_night['tx'] + (pd_night['mtx'] / 4) + (pd_night['tmf'] / 20)
            p_day_only = p_day_tot - p_night_tot
            prev_signal, _ = calc_signal(p_day_only, pd_spot)
            
        direction_changed = False
        if prev_signal in ['LONG', 'SHORT'] and signal_type in ['LONG', 'SHORT'] and prev_signal != signal_type:
            direction_changed = True
        elif prev_signal == 'NEUTRAL' and signal_type in ['LONG', 'SHORT']:
            direction_changed = True # also could be a changed state
            
        # Display Signal
        custom_class = 'yellow-font'
        if signal_type == 'LONG':
            custom_class = 'red-font'
        elif signal_type == 'SHORT':
            custom_class = 'green-font'
            
        if direction_changed:
            st.warning("⚠️ 第一次轉向，須加重提醒！")
            
        st.markdown(f'<div class="{custom_class}" style="text-align: center; margin-top: 20px;">{signal_msg}</div>', unsafe_allow_html=True)

    else:
        st.error("未能獲取該日完整資料，可能為非交易日。")
