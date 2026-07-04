# coding:gbk
"""
stock_exporter.py - 持仓数据导出策略
======================================
作为独立策略运行，每60秒导出持仓/挂单/成交到 stock.json
配合 app.py Flask看板使用，手机实时查看账户信息

在迅投极速中新建策略，填入本文件内容，绑定任意股票即可运行。
"""

import json
import os
import time
import datetime

# ============ 配置 ============
EXPORT_DIR = "C:\\"
EXPORT_FILE = os.path.join(EXPORT_DIR, "stock.json")
EXPORT_INTERVAL = 30  # 导出间隔（秒）
# 注意：handlebar 的调用频率 = 策略K线周期，60秒间隔仅在周期<=60秒时生效
# 请确保迅投极速策略设置中 K线周期为 1分钟 或 tick 级别


# ============================================================
# 迅投极速 策略入口
# ============================================================
def init(ContextInfo):
    ContextInfo.accountID = str(account)
    ContextInfo._last_export_time = 0
    # 随便挂一只股票让策略跑起来
    ContextInfo.set_universe(["510050.SH"])
    print("[数据导出] 策略初始化完成，账户:", ContextInfo.accountID)


def handlebar(ContextInfo):
    if not ContextInfo.is_last_bar():
        return

    now = time.time()
    # print(now)
    if now - ContextInfo._last_export_time >= EXPORT_INTERVAL:
        ContextInfo._last_export_time = now
        try:
            export_all_data(ContextInfo)
        except Exception as e:
            print(f"[数据导出] 导出异常: {e}")


# ============================================================
# 核心导出函数
# ============================================================
def export_all_data(ContextInfo):
    """
    导出全部数据到 stock.json
    包含: 账户概览、持仓信息、挂单记录、今日成交
    """
    account_id = getattr(ContextInfo, 'accountID', '')

    data = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account": _collect_account(ContextInfo, account_id),
        "positions": _collect_positions(ContextInfo, account_id),
        "pending_orders": _collect_orders(ContextInfo, account_id),
        "today_trades": _collect_deals(ContextInfo, account_id),
    }

    # 确保目录存在
    os.makedirs(EXPORT_DIR, exist_ok=True)

    # 原子写入: 先写临时文件再重命名，避免读取到半写文件
    tmp_file = EXPORT_FILE + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows 上 rename 需要先删除目标
        if os.path.exists(EXPORT_FILE):
            os.remove(EXPORT_FILE)
        os.rename(tmp_file, EXPORT_FILE)
        print(f"[数据导出] {data['update_time']} 成功 → {EXPORT_FILE}")
    except Exception as e:
        print(f"[数据导出] 写入失败: {e}")
        if os.path.exists(tmp_file):
            os.remove(tmp_file)


# ============================================================
# 数据采集函数
# ============================================================
def _collect_account(ContextInfo, account_id):
    """采集账户资金信息 (字段名参照官方文档 ACCOUNT 对象)"""
    result = {
        "total_assets": 0.0,
        "net_asset": 0.0,
        "market_value": 0.0,
        "total_debit": 0.0,
        "available": 0.0,
        "float_profit": 0.0,
    }
    try:
        accounts = get_trade_detail_data(account_id, "STOCK", "ACCOUNT")
        if accounts:
            acc = accounts[0]
            result["total_assets"] = round(getattr(acc, "m_dBalance", 0), 2)
            result["net_asset"] = round(getattr(acc, "m_dAssureAsset", 0), 2)
            result["market_value"] = round(getattr(acc, "m_dInstrumentValue", 0), 2)
            result["total_debit"] = round(getattr(acc, "m_dTotalDebit", 0), 2)
            result["available"] = round(getattr(acc, "m_dAvailable", 0), 2)
            result["float_profit"] = round(getattr(acc, "m_dPositionProfit", 0), 2)
    except Exception as e:
        print(f"[数据导出] 采集账户信息异常: {e}")
    return result


def _collect_positions(ContextInfo, account_id):
    """采集持仓信息 + 实时价格 (字段名参照官方文档 POSITION 对象)"""
    positions = []

    try:
        raw_positions = get_trade_detail_data(account_id, "STOCK", "position")
    except Exception as e:
        print(f"[数据导出] 获取持仓异常: {e}")
        return positions

    if not raw_positions:
        return positions

    # 批量获取实时行情
    stock_codes = []
    for p in raw_positions:
        inst_id = getattr(p, "m_strInstrumentID", "")
        exchange_id = getattr(p, "m_strExchangeID", "")
        if inst_id and getattr(p, "m_nVolume", 0) > 0:
            code = f"{inst_id}.{exchange_id}" if exchange_id else _to_full_code(inst_id)
            stock_codes.append(code)

    tick_data = {}
    if stock_codes:
        try:
            tick_data = ContextInfo.get_full_tick(stock_codes)
        except Exception as e:
            print(f"[数据导出] 获取实时行情异常: {e}")

    for p in raw_positions:
        inst_id = getattr(p, "m_strInstrumentID", "")
        volume = getattr(p, "m_nVolume", 0)
        if volume <= 0 or not inst_id:
            continue

        exchange_id = getattr(p, "m_strExchangeID", "")
        stock_name = getattr(p, "m_strInstrumentName", inst_id)
        cost_price = getattr(p, "m_dOpenPrice", 0.0)
        market_value = getattr(p, "m_dInstrumentValue", 0.0)
        position_cost = getattr(p, "m_dPositionCost", 0.0)
        position_profit = getattr(p, "m_dPositionProfit", 0.0)
        can_use = getattr(p, "m_nCanUseVolume", volume)

        full_code = f"{inst_id}.{exchange_id}" if exchange_id else _to_full_code(inst_id)

        # 实时行情
        current_price = 0.0
        pre_close = 0.0
        if full_code and tick_data and full_code in tick_data:
            current_price = tick_data[full_code].get("lastPrice", 0.0)
            pre_close = tick_data[full_code].get("preClose", 0.0) or tick_data[full_code].get("lastClose", 0.0)

        today_change = 0.0
        if current_price > 0 and pre_close > 0:
            today_change = round((current_price - pre_close) / pre_close * 100, 2)

        profit_rate = 0.0
        if position_cost > 0:
            profit_rate = round(position_profit / position_cost * 100, 2)

        positions.append({
            "stock_code": full_code,
            "stock_name": stock_name,
            "volume": volume,
            "can_use_volume": can_use,
            "cost_price": round(cost_price, 3),
            "current_price": round(current_price, 3),
            "pre_close": round(pre_close, 3),
            "market_value": round(market_value, 2),
            "position_cost": round(position_cost, 2),
            "float_profit": round(position_profit, 2),
            "profit_rate": profit_rate,
            "today_change": today_change,
        })

    return positions


def _collect_orders(ContextInfo, account_id):
    """采集当日委托记录 (字段名参照官方文档 ORDER 对象)"""
    orders = []
    try:
        raw_orders = get_trade_detail_data(account_id, "STOCK", "order")
        if not raw_orders:
            return orders

        for o in raw_orders:
            inst_id = getattr(o, "m_strInstrumentID", "")
            exchange_id = getattr(o, "m_strExchangeID", "")
            stock_name = getattr(o, "m_strInstrumentName", inst_id)
            status = getattr(o, "m_nOrderStatus", 0)
            price = getattr(o, "m_dLimitPrice", 0.0)
            volume = getattr(o, "m_nVolumeTotalOriginal", 0)
            traded_vol = getattr(o, "m_nVolumeTraded", 0)
            traded_price = getattr(o, "m_dTradedPrice", 0.0)
            trade_amount = getattr(o, "m_dTradeAmount", 0.0)
            offset_flag = getattr(o, "m_nOffsetFlag", 0)
            order_id = getattr(o, "m_strOrderSysID", "")
            remark = getattr(o, "m_strRemark", "")
            order_time = getattr(o, "m_strInsertTime", "")
            error_msg = getattr(o, "m_strErrorMsg", "")

            if offset_flag == 48:
                direction = "买入"
            elif offset_flag == 49:
                direction = "卖出"
            else:
                direction = f"未知({offset_flag})"

            status_map = {
                48: "已报", 49: "已报待撤", 50: "部成",
                51: "部撤", 52: "全成", 53: "已撤",
                54: "废单", 55: "未报", 56: "待报",
            }
            status_text = status_map.get(status, f"未知({status})")

            full_code = f"{inst_id}.{exchange_id}" if exchange_id else _to_full_code(inst_id)

            orders.append({
                "stock_code": full_code,
                "stock_name": stock_name,
                "direction": direction,
                "price": round(price, 3),
                "volume": volume,
                "traded_volume": traded_vol,
                "traded_price": round(traded_price, 3),
                "trade_amount": round(trade_amount, 2),
                "remaining": volume - traded_vol,
                "status": status_text,
                "status_code": status,
                "is_active": status in [48, 50],
                "order_id": order_id,
                "remark": remark,
                "time": order_time,
                "error_msg": error_msg,
            })
    except Exception as e:
        print(f"[数据导出] 采集委托记录异常: {e}")
    return orders


def _collect_deals(ContextInfo, account_id):
    """采集当日成交记录 (字段名参照官方文档 DEAL 对象)"""
    trades = []
    try:
        raw_deals = get_trade_detail_data(account_id, "STOCK", "deal")
        if not raw_deals:
            return trades

        for d in raw_deals:
            inst_id = getattr(d, "m_strInstrumentID", "")
            exchange_id = getattr(d, "m_strExchangeID", "")
            stock_name = getattr(d, "m_strInstrumentName", inst_id)
            trade_id = getattr(d, "m_strTradeID", "")
            price = getattr(d, "m_dPrice", 0.0)
            volume = getattr(d, "m_nVolume", 0)
            trade_amount = getattr(d, "m_dTradeAmount", 0.0)
            offset_flag = getattr(d, "m_nOffsetFlag", 0)
            deal_time = getattr(d, "m_strTradeTime", "")
            remark = getattr(d, "m_strRemark", "")

            if offset_flag == 48:
                direction = "买入"
            elif offset_flag == 49:
                direction = "卖出"
            else:
                direction = f"未知({offset_flag})"

            full_code = f"{inst_id}.{exchange_id}" if exchange_id else _to_full_code(inst_id)

            trades.append({
                "stock_code": full_code,
                "stock_name": stock_name,
                "direction": direction,
                "price": round(price, 3),
                "volume": volume,
                "amount": round(trade_amount, 2) if trade_amount > 0 else round(price * volume, 2),
                "time": deal_time,
                "trade_id": trade_id,
                "remark": remark,
            })
    except Exception as e:
        print(f"[数据导出] 采集成交记录异常: {e}")
    return trades


# ============================================================
# 工具函数
# ============================================================
def _to_full_code(inst_id):
    """
    将纯数字代码转换为完整代码 (带交易所后缀)
    例: 510050 → 510050.SH
    """
    if not inst_id:
        return ""
    if "." in inst_id:
        return inst_id
    # 5/6开头 → 上海, 0/3开头 → 深圳
    if inst_id.startswith(("5", "6")):
        return f"{inst_id}.SH"
    elif inst_id.startswith(("0", "3")):
        return f"{inst_id}.SZ"
    return inst_id
