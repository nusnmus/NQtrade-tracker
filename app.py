import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="小那期貨交易手帳", page_icon="📈", layout="centered")

DATA_FILE = "trades.json"
# 小那規格：0.25 點 = 5 USD，每 1 點 = 20 USD；每筆交易手續費 = 10 USD
POINT_VALUE_USD = 20.0  
FEE_USD = 10.0          

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"position": None, "history": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def calculate_stats(history):
    if not history:
        return 0.0, 0, 0, 0.0, "-"
    
    pnl_list = []
    for trade in history:
        if "pnl_usd_raw" in trade:
            pnl_list.append(trade["pnl_usd_raw"])
        else:
            raw_val = str(trade.get("淨損益(USD)", trade.get("損益(USD)", "0")))
            raw_val = raw_val.replace("$", "").replace(",", "").replace("+", "")
            try:
                pnl_list.append(float(raw_val))
            except ValueError:
                pnl_list.append(0.0)

    total_trades = len(pnl_list)
    total_pnl = sum(pnl_list)
    wins = [p for p in pnl_list if p > 0]
    losses = [p for p in pnl_list if p < 0]
    
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss = (abs(sum(losses)) / len(losses)) if losses else 0.0
    
    if avg_loss > 0:
        rr_ratio = f"{avg_win / avg_loss:.2f}"
    elif wins and not losses:
        rr_ratio = "∞"
    else:
        rr_ratio = "-"
        
    return total_pnl, total_trades, len(wins), win_rate, rr_ratio

def execute_close(exit_price, close_type):
    entry_p = pos["entry_price"]
    qty = pos.get("contracts", 1)
    
    # 點數與美元毛利計算
    pnl_pts = (exit_price - entry_p) if pos["type"] == "做多" else (entry_p - exit_price)
    gross_usd = pnl_pts * POINT_VALUE_USD * qty
    net_usd = gross_usd - FEE_USD  # 扣除 10 USD 手續費
    
    record = {
        "方向": pos["type"],
        "口數": qty,
        "進場": round(entry_p, 2),
        "出場": round(exit_price, 2),
        "預設止損": round(pos.get("stop_loss", 0.0), 2),
        "平倉類型": close_type,
        "損益(點)": f"{pnl_pts:+.2f}",
        "手續費": f"${FEE_USD:.2f}",
        "淨損益(USD)": f"${net_usd:+,.2f}",
        "開倉時間": pos["entry_time"],
        "平倉時間": datetime.now().strftime("%m/%d %H:%M"),
        "pnl_usd_raw": round(net_usd, 2)
    }
    data["history"].insert(0, record)
    data["position"] = None
    save_data(data)
    st.success(f"{close_type}完成！點數：{pnl_pts:+.2f} 點 | 淨損益：${net_usd:+,.2f} USD (已扣 ${FEE_USD:.0f} 手續費)")
    st.rerun()

data = load_data()
pos = data.get("position")
history = data.get("history", [])

st.title("📈 小那期貨交易手帳 (NQ)")

# 1. 績效數據看板 (已扣手續費)
total_pnl, total_trades, win_count, win_rate, rr_ratio = calculate_stats(history)

st.subheader("📊 績效數據總覽 (淨損益)")
col_m1, col_m2, col_m3 = st.columns(3)

col_m1.metric(
    label="累計淨損益 (USD)",
    value=f"${total_pnl:+,.2f}",
    delta=f"{total_pnl:+,.2f} USD" if total_trades > 0 else None
)

col_m2.metric(
    label="總勝率",
    value=f"{win_rate:.1f}%",
    delta=f"{win_count} 勝 / {total_trades} 筆" if total_trades > 0 else None,
    delta_color="off"
)

col_m3.metric(
    label="平均賺賠比",
    value=rr_ratio,
    delta="平均獲利 / 平均虧損" if total_trades > 0 else None,
    delta_color="off"
)

# 2. 淨值累積曲線
if history:
    pnl_chronological = []
    for trade in reversed(history):
        if "pnl_usd_raw" in trade:
            pnl_chronological.append(trade["pnl_usd_raw"])
        else:
            raw_val = str(trade.get("淨損益(USD)", trade.get("損益(USD)", "0")))
            raw_val = raw_val.replace("$", "").replace(",", "").replace("+", "")
            try:
                pnl_chronological.append(float(raw_val))
            except ValueError:
                pnl_chronological.append(0.0)

    cum_series = [0.0] + list(pd.Series(pnl_chronological).cumsum())
    labels = ["起點"] + [f"第 {i} 筆" for i in range(1, len(cum_series))]
    
    chart_df = pd.DataFrame({
        "交易進度": labels,
        "累計淨值 (USD)": cum_series
    }).set_index("交易進度")

    st.caption("📈 淨值累積曲線 (已計入每筆 $10 手續費)")
    st.line_chart(chart_df["累計淨值 (USD)"])

st.divider()

# 3. 持倉狀態卡片
if pos:
    side = pos["type"]
    color = "red" if side == "做多" else "green"
    qty = pos.get("contracts", 1)
    sl_price = pos.get("stop_loss", 0.0)
    
    st.warning(
        f"目前持倉：**:{color}[{side}]** {qty} 口 @ **{pos['entry_price']:.2f}**\n\n"
        f"🎯 **預設止損價**：`{sl_price:.2f}`\n\n"
        f"🕒 **開倉時間**：`{pos['entry_time']}`"
    )
else:
    st.info("目前無任何持倉")

# 4. 下單 / 平倉操作區
if not pos:
    st.subheader("開倉操作")
    contracts = st.number_input("交易口數", min_value=1, value=1, step=1)
    col1, col2 = st.columns(2)
    
    # 做多開倉
    with col1:
        st.markdown("**📈 做多 (Long)**")
        long_price = st.number_input("多單進場點位", value=0.0, step=0.25, format="%.2f", key="long_in")
        long_sl = st.number_input("多單止損點位", value=0.0, step=0.25, format="%.2f", key="long_sl")
        if st.button("確認做多開倉", use_container_width=True, type="primary"):
            if long_price > 0 and long_sl > 0:
                data["position"] = {
                    "type": "做多",
                    "contracts": contracts,
                    "entry_price": long_price,
                    "stop_loss": long_sl,
                    "entry_time": datetime.now().strftime("%m/%d %H:%M")
                }
                save_data(data)
                st.rerun()
            else:
                st.error("請輸入有效的進場價與止損價！")
                
    # 做空開倉
    with col2:
        st.markdown("**📉 做空 (Short)**")
        short_price = st.number_input("空單進場點位", value=0.0, step=0.25, format="%.2f", key="short_in")
        short_sl = st.number_input("空單止損點位", value=0.0, step=0.25, format="%.2f", key="short_sl")
        if st.button("確認做空開倉", use_container_width=True):
            if short_price > 0 and short_sl > 0:
                data["position"] = {
                    "type": "做空",
                    "contracts": contracts,
                    "entry_price": short_price,
                    "stop_loss": short_sl,
                    "entry_time": datetime.now().strftime("%m/%d %H:%M")
                }
                save_data(data)
                st.rerun()
            else:
                st.error("請輸入有效的進場價與止損價！")
else:
    st.subheader("平倉結算")
    tab_sl, tab_tp = st.tabs(["🛑 止損平倉 (依設定價)", "🎯 止盈 / 自訂平倉"])
    
    with tab_sl:
        sl_val = pos.get("stop_loss", 0.0)
        st.write(f"將依開倉設定之止損價 **{sl_val:.2f}** 進行結算，並扣除 $10 USD 手續費。")
        if st.button("🛑 執行止損平倉", use_container_width=True, type="primary"):
            execute_close(sl_val, "止損平倉")
            
    with tab_tp:
        tp_price = st.number_input(
            "輸入平倉點位",
            value=float(pos["entry_price"]),
            step=0.25,
            format="%.2f",
            key="tp_input"
        )
        if st.button("🎯 執行止盈平倉", use_container_width=True, type="primary"):
            execute_close(tp_price, "止盈平倉")

# 5. 歷史紀錄明細
st.divider()
st.subheader("歷史交易紀錄")
if data["history"]:
    display_df = pd.DataFrame(data["history"]).drop(columns=["pnl_usd_raw"], errors="ignore")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    if st.button("🗑️ 清空所有歷史紀錄"):
        data["history"] = []
        save_data(data)
        st.rerun()
else:
    st.caption("尚無歷史交易紀錄")
