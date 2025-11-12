import streamlit as st
import numpy as np
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ==============================================================================
# 設定與常數
# ==============================================================================
# 股票代號 (Yahoo Finance Tickers)
TICKER_631 = '00631L.TW'  # 元大台灣50正2
TICKER_TWII = '^TWII'      # 台指加權指數

# 00631 (元大台灣50正2) 的槓桿倍數
LEVERAGE_RATIO = 2.0
# 台指小台（MTX）每點價值
MTX_POINT_VALUE = 50

# 定義初始預設值，用於判斷是否為未載入數據的狀態
INITIAL_MA_TWII_DEFAULT = 19000
INITIAL_INDEX_TWII_DEFAULT = 19500
INITIAL_PRICE_631_DEFAULT = 50.0 # 新增 00631 預設值

st.set_page_config(
    page_title="📈 00631 大盤避險口數計算機",
    layout="wide"
)

st.title("🛡️ 00631 大盤均線避險口數計算機")
st.caption(f"避險訊號以 **大盤 ({TICKER_TWII}) 的均線** 為準，計算基於 **{TICKER_631} (兩倍槓桿)**。")


# ==============================================================================
# 數據抓取與 MA 計算函式
# ==============================================================================

@st.cache_data(ttl=600)
def fetch_data_for_exposure(ticker):
    """抓取資產最新價格 (僅用於計算風險敞口)"""
    try:
        # 使用 '1d' interval 和 '2d' period 來確保獲取當日收盤價（如果市場已收盤）
        data = yf.download(ticker, period='2d', interval='1d', progress=False)
        if not data.empty and 'Close' in data.columns:
            latest_price = data['Close'].iloc[-1]
            return round(float(latest_price), 2)
        return None
    except Exception as e:
        print(f"❌ 抓取 {ticker} 最新價失敗: {e}")
        return None

@st.cache_data(ttl=600)
def fetch_twii_and_calculate_ma(ma_days):
    """抓取台指數據並計算移動平均 (用於避險訊號)"""
    try:
        # 抓取足夠的數據來計算 MA
        data = yf.download(TICKER_TWII, period='6mo', interval='1d', progress=False)

        if data.empty or 'Close' not in data.columns:
            return None, None

        latest_price = data['Close'].iloc[-1]
        data['MA'] = data['Close'].rolling(window=ma_days).mean()
        ma_price = data['MA'].iloc[-1]

        # 指數點位取整數
        return int(round(latest_price, 0)), int(round(ma_price, 0))

    except Exception as e:
        print(f"❌ 抓取 {TICKER_TWII} 數據發生錯誤: {e}")
        return None, None

# ==============================================================================
# 側邊欄輸入：策略參數 (定義 ma_days)
# ==============================================================================
st.sidebar.header("📜 避險策略設定")

ma_days = st.sidebar.number_input(
    "大盤均線設定天數 (e.g., 13, 20, 60)",
    min_value=1,
    value=13,  # 預設值設定為 13
    step=1,
    help="設定您判斷大盤多空趨勢所使用的均線週期。"
)

# ==============================================================================
# 數據獲取與 MA 計算 (修正：MA 計算移出按鈕，00631 價格保留在按鈕中)
# ==============================================================================

# 設置初始狀態值 (確保在按鈕點擊前 session_state 存在)
if 'price_631_default' not in st.session_state:
    st.session_state['price_631_default'] = INITIAL_PRICE_631_DEFAULT
if 'index_twii_default' not in st.session_state:
    st.session_state['index_twii_default'] = INITIAL_INDEX_TWII_DEFAULT
if 'ma_price_twii' not in st.session_state:
    st.session_state['ma_price_twii'] = INITIAL_MA_TWII_DEFAULT # 初始預設 MA


# 1. 每次腳本重新運行時，都根據新的 ma_days 抓取並計算 MA
# 由於使用了 @st.cache_data，只要 ma_days 不變，就不會重新下載數據。
latest_index_twii, ma_price_twii = fetch_twii_and_calculate_ma(ma_days)

# 設置或更新 session_state 
if latest_index_twii is not None and ma_price_twii is not None:
    # 僅更新指數和 MA 點位
    st.session_state['index_twii_default'] = latest_index_twii
    st.session_state['ma_price_twii'] = ma_price_twii
    
    # 顯示狀態提示
    st.info(f"💡 **大盤 ({TICKER_TWII}) 數據已即時更新：** 最新價: {st.session_state['index_twii_default']:,.0f}, {ma_days}日 MA 點: {st.session_state['ma_price_twii']:,.0f}")
else:
    st.warning("⚠️ **大盤指數/均線數據載入失敗！** 使用預設值進行計算。")


# 2. 獲取 00631 價格的按鈕 (手動觸發)
if st.button("🚀 點擊獲取 00631 最新價格", type="primary"):
    latest_price_631 = fetch_data_for_exposure(TICKER_631)

    if latest_price_631 is not None:
        st.session_state['price_631_default'] = latest_price_631
        st.success(f"✅ **00631 價格更新成功！** 最新價: {latest_price_631:,.2f}")
    else:
        st.warning("⚠️ 00631 數據抓取失敗！請檢查 ticker 或稍後再試。")

st.markdown("---")

# ==============================================================================
# 側邊欄顯示 MA 計算結果 (現在會即時更新)
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.subheader(f"計算結果：大盤 ({ma_days} 日均線)")

# 判斷是否為初始預設值
is_default_ma = st.session_state['ma_price_twii'] == INITIAL_MA_TWII_DEFAULT

ma_display_label = f"{TICKER_TWII} MA 點"

if is_default_ma:
    # 顯示預設值提示
    st.sidebar.info("請等待數據載入或檢查網路連線。")
    ma_display_value = f"預設值: {INITIAL_MA_TWII_DEFAULT} 點"
    ma_display_delta = None
else:
    # 顯示實際計算出的點位
    ma_price_twii = st.session_state['ma_price_twii']
    ma_display_value = f"{ma_price_twii:,.0f} 點"
    ma_display_delta = None

# 顯示大盤的均線點
st.sidebar.metric(
    ma_display_label,
    ma_display_value,
    delta=ma_display_delta,
    help=f"最新的 {ma_days} 日移動平均點位。當您更改上方天數時，此數據會即時變動。"
)

st.sidebar.markdown("---")

# **重要修改：移除手動訊號選擇，保留部位狀態**
current_status = st.sidebar.selectbox(
    "2. 您目前的部位狀態",
    options=["目前持有 00631 多倉，未避險", "目前已避險 (持有 00631 多倉 + 小台空倉)"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.header("📊 持倉與市場數據")


# ==============================================================================
# 主頁面輸入：市場數據
# ==============================================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("持倉部位")
    holding_lots = st.number_input(
        "00631 持有張數 (張)",
        min_value=1,
        value=7,
        step=1,
    )
    # 00631 價格 (float)
    price_631 = st.number_input(
        f"00631 最新價格 (元/股) - 預設: {st.session_state['price_631_default']:,.2f}",
        min_value=10.0,
        value=st.session_state['price_631_default'],
        step=0.1,
        format="%.2f",
    )

with col2:
    st.subheader("市場資訊")
    # 台指加權指數 (int)
    current_index = st.number_input(
        f"台指加權指數 (點) - 預設: {st.session_state['index_twii_default']:,.0f}",
        min_value=5000,
        value=st.session_state['index_twii_default'],
        step=10,
    )

# ==============================================================================
# 計算邏輯 (風險敞口與避險口數)
# ==============================================================================
# 00631 名目價值 (1倍槓桿): 張數 * 1000股/張 * 價格
nominal_value_1x = holding_lots * 1000 * price_631
# 實際風險敞口 (2倍槓桿)
effective_exposure = nominal_value_1x * LEVERAGE_RATIO
# 小台合約價值: 指數點位 * 每點價值
mtx_contract_value = current_index * MTX_POINT_VALUE
# 理論避險口數 (浮點數)
required_lots_float = effective_exposure / mtx_contract_value
# 建議避險口數 (無條件進位)
required_lots_ceil = np.ceil(required_lots_float)


# ==============================================================================
# 策略判斷與結果展示 (根據您的策略自動判斷)
# ==============================================================================
st.markdown("---")
st.subheader("🎯 避險動作與口數建議")

action_required = ""
suggested_lots = 0
ma_price_twii = st.session_state.get('ma_price_twii', INITIAL_MA_TWII_DEFAULT) # 確保拿到 MA

# 1. 自動判斷均線訊號
if current_index > ma_price_twii:
    ma_signal_auto = "🟢 多頭 (指數在均線上方)"
    is_bullish = True
elif current_index <= ma_price_twii:
    ma_signal_auto = "🔴 空頭/避險 (指數在均線下方或相等)"
    is_bullish = False
else:
    ma_signal_auto = "🟡 無法判斷 (請檢查數據載入狀態)"
    is_bullish = False

# 顯示自動判斷的訊號
st.metric(f"🤖 **自動判斷的 {ma_days} 日均線訊號**", ma_signal_auto, delta=None)
st.markdown("---")


# 2. 根據訊號和現狀給出操作建議
if is_bullish: # 指數 > MA (多頭訊號，不需避險)
    if current_status == "目前持有 00631 多倉，未避險":
        action_required = "🟢 維持多倉狀態 (無須避險)"
        suggested_lots = 0
    elif current_status == "目前已避險 (持有 00631 多倉 + 小台空倉)":
        action_required = "🟢 平倉避險空單 (解除避險)"
        suggested_lots = required_lots_ceil

else: # 指數 <= MA (空頭/避險訊號，需要避險)
    if current_status == "目前持有 00631 多倉，未避險":
        action_required = "🔴 立即建立空單避險"
        suggested_lots = required_lots_ceil
    elif current_status == "目前已避險 (持有 00631 多倉 + 小台空倉)":
        action_required = "🟡 維持避險狀態 (維持空單)"
        suggested_lots = required_lots_ceil


# 輸出結果
if "🔴" in action_required:
    st.error(f"### {action_required}")
elif "🟢" in action_required:
    st.success(f"### {action_required}")
else:
    st.warning(f"### {action_required}")

st.markdown("---")

col4, col5, col6, col7 = st.columns(4)

col4.metric(
    "📊 實際風險敞口 (元)",
    f"{effective_exposure:,.0f} 元",
)

col5.metric(
    f"🛠️ 小台合約價值 (元)",
    f"{mtx_contract_value:,.0f} 元",
)

col6.metric(
    "🔬 理論避險口數 (浮點數)",
    f"{required_lots_float:.2f} 口",
)

# 顯示建議操作口數
if suggested_lots > 0 and "平倉" not in action_required:
    col7.metric(
        "🔥 建議操作口數 (口)",
        f"建倉 {int(suggested_lots):,} 口",
        help="建議無條件進位，確保足額對沖。"
    )
elif "平倉" in action_required:
    col7.metric(
        "🔥 建議操作口數 (口)",
        f"平倉 {int(suggested_lots):,} 口",
        help="建議平倉的口數。"
    )
else:
    col7.metric("🔥 建議操作口數 (口)", "0 口")

st.markdown("---")
st.info(f"**💡 避險邏輯摘要：** (基於 **大盤 {ma_days} 日均線**)\n\n1. 您的 {holding_lots} 張 00631 總風險敞口約為 **{effective_exposure:,.0f} 元**。\n2. 由於小台合約價值約為 **{mtx_contract_value:,.0f} 元**，您理論上應建立 **{required_lots_float:.2f} 口** 空單才能完全對沖。\n3. 我們建議採用 **無條件進位**，即操作 **{int(required_lots_ceil):,} 口** 來確保足額對沖。\n\n**數據更新時間：** 大盤指數和均線會依據 {ma_days} **即時計算** (若 yfinance 數據有更新且 cache 逾時)。00631 價格需要點擊「🚀 獲取 00631 最新價格」按鈕手動更新。")
