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
TICKER_TWII = '^TWII'     # 台指加權指數

# 00631 (元大台灣50正2) 的槓桿倍數
LEVERAGE_RATIO = 2.0
# 台指小台（MTX）每點價值
MTX_POINT_VALUE = 50 

st.set_page_config(
    page_title="📈 00631 均線避險口數計算機", 
    layout="wide"
)

st.title("🛡️ 00631 均線避險口數計算機")
st.caption(f"本計算機基於 **{TICKER_631} (兩倍槓桿)** 與 **台指小台 (每點 {MTX_POINT_VALUE} 元)** 進行風險對沖。")


# ==============================================================================
# 數據抓取與 MA 計算函式
# ==============================================================================

@st.cache_data(ttl=600) 
def fetch_data_and_calculate_ma(ticker, ma_days):
    """從 Yahoo Finance 抓取數據並計算移動平均"""
    try:
        # 抓取最近六個月的數據，確保有足夠的數據計算長週期均線
        data = yf.download(ticker, period='6mo', interval='1d', progress=False)
        
        if data.empty or 'Close' not in data.columns:
            return None, None # 返回 None, None (最新價, 均線價)
        
        # 1. 計算最新價格
        latest_price = data['Close'].iloc[-1]
        
        # 2. 計算移動平均
        data['MA'] = data['Close'].rolling(window=ma_days).mean()
        ma_price = data['MA'].iloc[-1]

        # 處理數據格式
        if ticker == TICKER_TWII:
            # 指數點位取整數
            return int(round(latest_price, 0)), int(round(ma_price, 0))
        else:
            # 股價保留兩位小數
            return round(float(latest_price), 2), round(float(ma_price), 2)
        
    except Exception as e:
        print(f"❌ 抓取 {ticker} 數據發生錯誤: {e}")
        return None, None

# ==============================================================================
# 側邊欄輸入：策略參數 (定義 ma_days)
# ==============================================================================
st.sidebar.header("📜 避險策略設定")

ma_days = st.sidebar.number_input(
    "均線設定天數 (e.g., 13, 20, 60)",
    min_value=1,
    value=13,  # 預設值設定為 13
    step=1,
    help="設定您判斷多空趨勢所使用的均線週期。"
)

# ==============================================================================
# 數據獲取與按鈕 (現在同時抓取最新價和均線價)
# ==============================================================================

if st.button("🚀 點擊獲取最新市場數據 (含均線計算)", type="primary"):
    # 抓取 00631 數據
    latest_price_631, ma_price_631 = fetch_data_and_calculate_ma(TICKER_631, ma_days)
    
    # 抓取台指加權指數數據
    latest_index_twii, ma_price_twii = fetch_data_and_calculate_ma(TICKER_TWII, ma_days)
    
    # 判斷數據是否成功抓取
    if latest_price_631 is not None and latest_index_twii is not None:
        st.session_state['price_631_default'] = latest_price_631
        st.session_state['index_twii_default'] = latest_index_twii
        st.session_state['ma_price_631'] = ma_price_631
        st.session_state['ma_price_twii'] = ma_price_twii
        st.success(f"✅ 數據更新成功！00631 MA 價: {ma_price_631:,.2f} | 台指 MA 點: {ma_price_twii:,.0f}")
    else:
        st.warning("⚠️ 數據抓取或計算均線失敗！請檢查 ticker 或稍後再試。")
else:
    # 設置初始狀態值 (確保初始值也是匹配的整數/浮點數，且新增 MA 初始值)
    if 'price_631_default' not in st.session_state:
        st.session_state['price_631_default'] = 50.0 
    if 'index_twii_default' not in st.session_state:
        st.session_state['index_twii_default'] = 19500 
    if 'ma_price_631' not in st.session_state:
        st.session_state['ma_price_631'] = 48.0 # 初始預設 MA 
    if 'ma_price_twii' not in st.session_state:
        st.session_state['ma_price_twii'] = 19000 # 初始預設 MA


# ==============================================================================
# 側邊欄顯示 MA 計算結果 (新增區塊)
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.subheader("計算結果：均線點位")

col_ma1, col_ma2 = st.sidebar.columns(2)

# 顯示 00631 的均線價
col_ma1.metric(
    f"{TICKER_631} MA 價",
    f"{st.session_state['ma_price_631']:,.2f} 元",
    help=f"最新的 {ma_days} 日移動平均價格。"
)

# 顯示台指的均線點
col_ma2.metric(
    f"{TICKER_TWII} MA 點",
    f"{st.session_state['ma_price_twii']:,.0f} 點",
    help=f"最新的 {ma_days} 日移動平均點位。"
)

st.sidebar.markdown("---")

# 其他策略設定 (保持不變)
ma_signal = st.sidebar.selectbox(
    "1. 均線訊號判斷（進場/出場條件）",
    options=["收盤價在均線上方 (多頭)", "收盤價在均線下方 (空頭/避險)", "保持中立"],
    index=0,
    help=f"您判斷 {ma_days} 日均線的結果。請對比上方 MA 點位與您輸入的最新價格。"
)

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
col1, col2, col3 = st.columns(3)

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
# 計算邏輯 (保持不變)
# ==============================================================================

# 1. 00631 總名目價值（1X）
nominal_value_1x = holding_lots * 1000 * price_631

# 2. 實際風險敞口（2X 槓桿部位）
effective_exposure = nominal_value_1x * LEVERAGE_RATIO

# 3. 台指小台合約價值
mtx_contract_value = current_index * MTX_POINT_VALUE

# 4. 應避險的理論口數（未取整數）
required_lots_float = effective_exposure / mtx_contract_value

# 5. 決定建議口數（避險通常建議至少足額）
required_lots_ceil = np.ceil(required_lots_float)


# ==============================================================================
# 結果展示 (保持不變)
# ==============================================================================
st.markdown("---")
st.subheader("🎯 避險動作與口數建議")

action_required = ""
suggested_lots = 0

if ma_signal == "收盤價在均線下方 (空頭/避險)":
    if current_status == "目前持有 00631 多倉，未避險":
        action_required = "🔴 立即建立空單避險"
        suggested_lots = required_lots_ceil
    elif current_status == "目前已避險 (持有 00631 多倉 + 小台空倉)":
        action_required = "🟡 維持避險狀態 (維持空單)"
        suggested_lots = required_lots_ceil
        
elif ma_signal == "收盤價在均線上方 (多頭)":
    if current_status == "目前持有 00631 多倉，未避險":
        action_required = "🟢 維持多倉狀態 (無須避險)"
        suggested_lots = 0
    elif current_status == "目前已避險 (持有 00631 多倉 + 小台空倉)":
        action_required = "🟢 平倉避險空單 (解除避險)"
        suggested_lots = required_lots_ceil
    else: 
        action_required = "🟡 保持中立狀態 (無須避險)"
        suggested_lots = 0

else: # 保持中立（當均線判斷模糊時）
    action_required = "🟡 市場判斷不明，建議維持現狀或使用更長週期的均線。"
    suggested_lots = required_lots_ceil if current_status == "目前已避險 (持有 00631 多倉 + 小台空倉)" else 0


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
    col7.metric("🔥 建議操作口數 (口)", "0")

st.markdown("---")
st.info(f"**💡 避險邏輯摘要：** (基於 **{ma_days} 日均線**)\n\n1. 您的 {holding_lots} 張 00631 總風險敞口約為 **{effective_exposure:,.0f} 元**。\n2. 由於小台合約價值約為 **{mtx_contract_value:,.0f} 元**，您理論上應建立 **{required_lots_float:.2f} 口** 空單才能完全對沖。\n3. 我們建議採用 **無條件進位**，即操作 **{int(suggested_lots):,} 口** 來確保足額對沖。\n\n**數據更新時間：** 點擊「🚀 獲取最新市場數據」按鈕後，數據會在 10 分鐘內被快取（不會重複抓取），並計算 {ma_days} 日均線。")
