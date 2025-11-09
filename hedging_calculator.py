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
# 數據抓取函式 (使用 Streamlit 快取優化性能)
# ==============================================================================

# 設定 10 分鐘 (600秒) 的快取時間
@st.cache_data(ttl=600) 
def fetch_latest_price(ticker):
    """從 Yahoo Finance 抓取最新的收盤價，並返回 float 或 None"""
    try:
        # 抓取最近兩天數據，確保拿到最新收盤價
        # interval='1d' 是確保只拿日線數據
        data = yf.download(ticker, period='2d', interval='1d', progress=False)
        
        # 🚨 修正點：檢查 DataFrame 是否為空，且 'Close' 欄位存在
        if not data.empty and 'Close' in data.columns:
            latest_price = data['Close'].iloc[-1]
            # 確保返回的是 Python float 而非 Pandas Series/numpy.float64
            return round(float(latest_price), 2) 
        
        # 數據為空或結構不正確，在執行 log 中顯示錯誤
        print(f"❌ 抓取 {ticker} 數據失敗：數據為空或結構不正確。")
        return None # 失敗時返回 None
        
    except Exception as e:
        # 在執行 log 中顯示詳細的錯誤信息
        print(f"❌ 抓取 {ticker} 數據發生錯誤: {e}")
        return None

# ==============================================================================
# 數據獲取與按鈕
# ==============================================================================

# 創建一個按鈕，讓用戶手動觸發數據更新
if st.button("🚀 點擊獲取最新市場價格", type="primary"):
    latest_price_631 = fetch_latest_price(TICKER_631)
    latest_index_twii = fetch_latest_price(TICKER_TWII)
    
    # 🚨 修正點：使用 is not None 判斷數據是否成功抓取 (避免 Pandas ValueError)
    if latest_price_631 is not None and latest_index_twii is not None:
        st.session_state['price_631_default'] = latest_price_631
        st.session_state['index_twii_default'] = latest_index_twii
        st.success(f"✅ 價格更新成功！{TICKER_631} 最新價: {latest_price_631:,.2f} | {TICKER_TWII} 最新點: {latest_index_twii:,.0f}")
    else:
        # 如果任何一個抓取失敗，則警告並保留舊值 (或預設值)
        st.warning("⚠️ 數據抓取失敗！請檢查 ticker 是否正確或稍後再試。App 將使用預設或上次成功載入的值。")
else:
    # 設置初始狀態值，避免首次執行時出錯
    if 'price_631_default' not in st.session_state:
        st.session_state['price_631_default'] = 50.0 # 預設值
    if 'index_twii_default' not in st.session_state:
        st.session_state['index_twii_default'] = 19500.0 # 預設值


# ==============================================================================
# 側邊欄輸入：策略參數
# ==============================================================================
st.sidebar.header("📜 避險策略設定")

ma_signal = st.sidebar.selectbox(
    "1. 均線訊號判斷（進場/出場條件）",
    options=["收盤價在均線上方 (多頭)", "收盤價在均線下方 (空頭/避險)", "保持中立"],
    index=0,
)

current_status = st.sidebar.selectbox(
    "2. 您目前的部位狀態",
    options=["目前持有 00631 多倉，未避險", "目前已避險 (持有 00631 多倉 + 小台空倉)"],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.header("📊 持倉與市場數據")


# ==============================================================================
# 主頁面輸入：市場數據 (使用 session_state 作為預設值)
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
    # 使用 session_state 中的值作為預設值
    price_631 = st.number_input(
        f"00631 最新價格 (元/股) - 預設: {st.session_state['price_631_default']:,.2f}", 
        min_value=10.0, 
        value=st.session_state['price_631_default'], 
        step=0.1,
        format="%.2f",
    )

with col2:
    st.subheader("市場資訊")
    # 使用 session_state 中的值作為預設值
    current_index = st.number_input(
        f"台指加權指數 (點) - 預設: {st.session_state['index_twii_default']:,.0f}", 
        min_value=5000, 
        value=st.session_state['index_twii_default'], 
        step=10,
    )
    
# ==============================================================================
# 計算邏輯
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
# 結果展示
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
st.info(f"**💡 避險邏輯摘要：**\n\n1. 您的 {holding_lots} 張 00631 總風險敞口約為 **{effective_exposure:,.0f} 元**。\n2. 由於小台合約價值約為 **{mtx_contract_value:,.0f} 元**，您理論上應建立 **{required_lots_float:.2f} 口** 空單才能完全對沖。\n3. 我們建議採用 **無條件進位**，即操作 **{int(suggested_lots):,} 口** 來確保足額對沖。\n\n**數據更新時間：** 點擊「🚀 獲取最新市場價格」按鈕後，數據會在 10 分鐘內被快取（不會重複抓取），以提升應用程式效能。")
