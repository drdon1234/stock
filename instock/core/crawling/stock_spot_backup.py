#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Desc: 东方财富 push2 列表接口(clist)不可用时的备用数据源
      行情：腾讯 qt.gtimg.cn 批量行情
      列表：东方财富综合选股(数据中心接口) / 新浪 Market_Center
      板块资金流：新浪 MoneyFlow
各函数返回的列与对应东方财富函数一致，可直接替换使用。
"""
import random
import time

import numpy as np
import pandas as pd
import requests
from instock.core.singleton_proxy import proxys

__author__ = 'myh '
__date__ = '2026/10/7 '

_SINA_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
_SINA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}
_QQ_URL = "https://qt.gtimg.cn/q="
_QQ_BATCH = 60  # 腾讯单次查询上限约70只

# 东方财富 每日股票数据 的列顺序
SPOT_COLUMNS = ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "振幅", "换手率", "量比", "今开",
                "最高", "最低", "昨收", "涨速", "5分钟涨跌", "60日涨跌幅", "年初至今涨跌幅", "市盈率动", "市盈率TTM",
                "市盈率静", "市净率", "每股收益", "每股净资产", "每股公积金", "每股未分配利润", "加权净资产收益率", "毛利率",
                "资产负债率", "营业收入", "营业收入同比增长", "归属净利润", "归属净利润同比增长", "报告期", "总股本",
                "已流通股份", "总市值", "流通市值", "所处行业", "上市时间"]

# 腾讯行情无法提供，从综合选股补充的列
_SELECTION_SPOT_MAP = {
    "年初至今涨跌幅": "changerate_ty",
    "每股收益": "basic_eps",
    "每股净资产": "bvps",
    "每股公积金": "per_capital_reserve",
    "每股未分配利润": "per_unassign_profit",
    "加权净资产收益率": "roe_weight",
    "毛利率": "sale_gpr",
    "资产负债率": "debt_asset_ratio",
    "营业收入": "total_operate_income",
    "营业收入同比增长": "toi_yoy_ratio",
    "归属净利润": "parent_netprofit",
    "归属净利润同比增长": "netprofit_yoy_ratio",
    "所处行业": "industry",
    "上市时间": "listing_date",
}

_FLOW_TYPES = ["主力", "超大单", "大单", "中单", "小单"]


def _get(url, params=None, headers=None, retry=3, timeout=15):
    for i in range(retry):
        try:
            r = requests.get(url, params=params, headers=headers, proxies=proxys().get_proxies(), timeout=timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException:
            if i == retry - 1:
                raise
            time.sleep(random.uniform(2, 4))


def _qq_symbol(code):
    # 6、5、9开头为上交所，其余为深交所
    return f"sh{code}" if code.startswith(('6', '5', '9')) else f"sz{code}"


def _num(v, scale=1):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return np.nan
    # 万元、亿元换算成元后取整，去掉浮点误差
    return round(v * scale) if scale != 1 else v


def qq_quotes(codes) -> pd.DataFrame:
    """
    腾讯批量行情
    https://qt.gtimg.cn/q=sz000001,sh600000
    :param codes: 6位代码列表
    :return: 行情，列名与东方财富一致
    """
    rows = []
    codes = list(codes)
    for i in range(0, len(codes), _QQ_BATCH):
        if i > 0:
            time.sleep(random.uniform(0.3, 0.6))
        q = ",".join(_qq_symbol(c) for c in codes[i:i + _QQ_BATCH])
        text = _get(_QQ_URL + q).content.decode("gbk", errors="ignore")
        for line in text.split(";"):
            if '="' not in line:
                continue
            f = line.split('="', 1)[1].rstrip('"').split("~")
            if len(f) < 74:
                continue
            price = _num(f[3])
            rows.append({
                "代码": f[2],
                "名称": f[1],
                "最新价": price if price > 0 else np.nan,  # 停牌为0
                "涨跌幅": _num(f[32]),
                "涨跌额": _num(f[31]),
                "成交量": _num(f[36]),  # 手
                "成交额": _num(f[37], 10000),  # 万元 -> 元
                "振幅": _num(f[43]),
                "换手率": _num(f[38]),
                "量比": _num(f[49]),
                "今开": _num(f[5]),
                "最高": _num(f[33]),
                "最低": _num(f[34]),
                "昨收": _num(f[4]),
                "市盈率动": _num(f[52]),
                "市盈率TTM": _num(f[39]),
                "市盈率静": _num(f[53]),
                "市净率": _num(f[46]),
                "总股本": _num(f[73]),
                "已流通股份": _num(f[72]),
                "总市值": _num(f[45], 100000000),  # 亿元 -> 元
                "流通市值": _num(f[44], 100000000),
            })
    return pd.DataFrame(rows)


def sina_node_data(node: str = "hs_a") -> pd.DataFrame:
    """
    新浪财经-行情中心-节点列表
    :param node: hs_a 沪深A股，etf_hq_fund ETF基金
    """
    page_size = 100  # 新浪单页上限100
    page = 1
    data = []
    while True:
        params = {"page": page, "num": page_size, "sort": "symbol", "asc": 1, "node": node}
        _data = _get(_SINA_URL + "Market_Center.getHQNodeData", params=params, headers=_SINA_HEADERS).json()
        if not _data:
            break
        data.extend(_data)
        if len(_data) < page_size:
            break
        page = page + 1
        time.sleep(random.uniform(1, 1.5))
    return pd.DataFrame(data)


def stock_zh_a_spot_backup(selection: pd.DataFrame = None) -> pd.DataFrame:
    """
    沪深A股实时行情(备用)：腾讯行情 + 综合选股基本面
    :param selection: 综合选股数据(英文列名)，为空时用新浪获取股票列表
    :return: 与 stock_zh_a_spot_em 相同的列
    """
    if selection is not None and len(selection.index) > 0:
        codes = selection["code"].astype(str).tolist()
    else:
        selection = None
        codes = sina_node_data("hs_a")["code"].astype(str).tolist()
    if not codes:
        return pd.DataFrame()

    temp_df = qq_quotes(codes)
    if len(temp_df.index) == 0:
        return pd.DataFrame()

    if selection is not None:
        sel = selection[["code"] + list(_SELECTION_SPOT_MAP.values())].drop_duplicates("code", keep="last")
        sel = sel.rename(columns={v: k for k, v in _SELECTION_SPOT_MAP.items()}).rename(columns={"code": "代码"})
        temp_df = temp_df.merge(sel, on="代码", how="left")

    for c in SPOT_COLUMNS:
        if c not in temp_df.columns:
            temp_df[c] = np.nan
    temp_df["报告期"] = pd.NaT
    if not pd.api.types.is_datetime64_any_dtype(temp_df["上市时间"]):
        temp_df["上市时间"] = pd.to_datetime(temp_df["上市时间"], errors="coerce")
    return temp_df[SPOT_COLUMNS]


def fund_etf_spot_backup() -> pd.DataFrame:
    """
    ETF实时行情(备用)：新浪ETF列表 + 腾讯行情
    :return: 与 fund_etf_spot_em 相同的列
    """
    etf = sina_node_data("etf_hq_fund")
    if len(etf.index) == 0:
        return pd.DataFrame()
    temp_df = qq_quotes(etf["code"].astype(str).tolist())
    if len(temp_df.index) == 0:
        return pd.DataFrame()
    temp_df.rename(columns={"今开": "开盘价", "最高": "最高价", "最低": "最低价"}, inplace=True)
    return temp_df[["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "开盘价", "最高价", "最低价",
                    "昨收", "换手率", "流通市值", "总市值"]]


def stock_individual_fund_flow_rank_backup(indicator: str = "今日", selection: pd.DataFrame = None) -> pd.DataFrame:
    """
    个股资金流向(备用)：取综合选股中的主力净流入，超大单/大单/中单/小单拆分无数据
    综合选股只有 今日、3日、5日 主力净流入，10日只有涨跌幅。
    :return: 与 stock_individual_fund_flow_rank 相同的列
    """
    if selection is None or len(selection.index) == 0:
        return pd.DataFrame()
    source = {
        "今日": ("change_rate", "net_inflow"),
        "3日": ("changerate_3days", "netinflow_3days"),
        "5日": ("changerate_5days", "netinflow_5days"),
        "10日": ("changerate_10days", None),
    }
    change_col, inflow_col = source[indicator]
    sel = selection.drop_duplicates("code", keep="last")
    temp_df = pd.DataFrame({
        "代码": sel["code"].values,
        "名称": sel["name"].values,
        "最新价": sel["new_price"].values,
        f"{indicator}涨跌幅": sel[change_col].values,
    })
    for t in _FLOW_TYPES:
        temp_df[f"{indicator}{t}净流入-净额"] = np.nan
        temp_df[f"{indicator}{t}净流入-净占比"] = np.nan
    if inflow_col is not None:
        temp_df[f"{indicator}主力净流入-净额"] = sel[inflow_col].values
        if indicator == "今日":
            amount = pd.to_numeric(sel["deal_amount"], errors="coerce").replace(0, np.nan).values
            temp_df["今日主力净流入-净占比"] = sel[inflow_col].values / amount * 100
    temp_df = temp_df[temp_df["最新价"].notna()]
    return temp_df


def stock_sector_fund_flow_rank_backup(indicator: str = "今日", sector_type: str = "行业资金流") -> pd.DataFrame:
    """
    新浪财经-板块资金流向(备用)，只有当日数据，行业为申万分类
    https://vip.stock.finance.sina.com.cn/moneyflow/#hyzjl
    净流入为板块全部资金(流入-流出)，超大单/大单/中单/小单拆分无数据
    :return: 与 stock_sector_fund_flow_rank 相同的列
    """
    if indicator != "今日":
        return pd.DataFrame()
    fenlei = {"行业资金流": 0, "概念资金流": 1}[sector_type]
    params = {"page": 1, "num": 1000, "sort": "netamount", "asc": 0, "fenlei": fenlei}
    data = _get(_SINA_URL + "MoneyFlow.ssl_bkzj_bk", params=params, headers=_SINA_HEADERS).json()
    if not data:
        return pd.DataFrame()
    # 新浪板块列表偶有重名（如“恒大概念”），名称是入库主键，需去重
    df = pd.DataFrame(data).drop_duplicates("name", keep="first").reset_index(drop=True)
    temp_df = pd.DataFrame({
        "名称": df["name"],
        "今日涨跌幅": pd.to_numeric(df["avg_changeratio"], errors="coerce") * 100,
    })
    for t in _FLOW_TYPES:
        temp_df[f"今日{t}净流入-净额"] = np.nan
        temp_df[f"今日{t}净流入-净占比"] = np.nan
    temp_df["今日主力净流入-净额"] = pd.to_numeric(df["netamount"], errors="coerce")
    temp_df["今日主力净流入-净占比"] = pd.to_numeric(df["ratioamount"], errors="coerce") * 100
    temp_df["今日主力净流入最大股"] = df["ts_name"]
    return temp_df
