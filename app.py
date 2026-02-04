from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import akshare as ak
import pandas as pd
from datetime import datetime
import time

app = Flask(__name__)
CORS(app)

def safe_api_call(func, *args, **kwargs):
    """安全的API调用，带重试机制"""
    max_retries = 3
    for i in range(max_retries):
        try:
            time.sleep(0.5)  # 添加延迟避免请求过快
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            print(f"API call failed (attempt {i+1}/{max_retries}): {str(e)}")
            if i == max_retries - 1:
                raise
            time.sleep(1)
    return None

def calculate_financial_indicators(stock_code):
    """计算五大核心指标和详细财务信息"""
    try:
        print(f"开始获取 {stock_code} 的财务数据...")

        # 使用安全调用获取数据
        balance = safe_api_call(ak.stock_financial_report_sina, stock=stock_code, symbol="资产负债表")
        income = safe_api_call(ak.stock_financial_report_sina, stock=stock_code, symbol="利润表")
        cashflow = safe_api_call(ak.stock_financial_report_sina, stock=stock_code, symbol="现金流量表")

        if balance is None or balance.empty:
            print(f"无法获取 {stock_code} 的资产负债表")
            return None

        if income is None or income.empty:
            print(f"无法获取 {stock_code} 的利润表")
            return None

        if cashflow is None or cashflow.empty:
            print(f"无法获取 {stock_code} 的现金流量表")
            return None

        print(f"成功获取数据，资产负债表列数: {len(balance.columns)}")

        # 提取本期数和上期数（第2列和第3列）
        if len(balance.columns) < 2:
            print("数据列数不足")
            return None

        current_col = balance.columns[1]
        previous_col = balance.columns[2] if len(balance.columns) > 2 else balance.columns[1]

        print(f"报告期: {current_col}, 上期: {previous_col}")

        # 辅助函数：安全获取数值
        def get_value(df, row_name, col):
            try:
                row = df[df.iloc[:, 0] == row_name]
                if not row.empty:
                    val = row.iloc[0][col]
                    # 清理数值
                    if isinstance(val, str):
                        val = val.replace(',', '').replace('--', '0')
                    return float(val) if val not in ['', '--', None] else 0
                return 0
            except Exception as e:
                print(f"获取 {row_name} 出错: {str(e)}")
                return 0

        # 提取关键财务数据
        # 资产负债表数据
        total_assets_current = get_value(balance, '资产总计', current_col)
        total_assets_previous = get_value(balance, '资产总计', previous_col)
        total_liabilities_current = get_value(balance, '负债合计', current_col)
        total_liabilities_previous = get_value(balance, '负债合计', previous_col)
        current_assets = get_value(balance, '流动资产合计', current_col)
        current_assets_previous = get_value(balance, '流动资产合计', previous_col)
        current_liabilities = get_value(balance, '流动负债合计', current_col)
        current_liabilities_previous = get_value(balance, '流动负债合计', previous_col)
        accounts_payable_current = get_value(balance, '应付账款', current_col)
        accounts_payable_previous = get_value(balance, '应付账款', previous_col)
        accounts_receivable_current = get_value(balance, '应收账款', current_col)
        accounts_receivable_previous = get_value(balance, '应收账款', previous_col)
        cash_current = get_value(balance, '货币资金', current_col)
        cash_previous = get_value(balance, '货币资金', previous_col)

        # 利润表数据
        revenue_current = get_value(income, '营业收入', current_col)
        revenue_previous = get_value(income, '营业收入', previous_col)
        net_profit_current = get_value(income, '净利润', current_col)
        net_profit_previous = get_value(income, '净利润', previous_col)
        operating_cost_current = get_value(income, '营业成本', current_col)
        operating_cost_previous = get_value(income, '营业成本', previous_col)

        # 现金流量表数据
        operating_cashflow_current = get_value(cashflow, '经营活动产生的现金流量净额', current_col)
        operating_cashflow_previous = get_value(cashflow, '经营活动产生的现金流量净额', previous_col)

        print(f"关键指标: 资产={total_assets_current}, 负债={total_liabilities_current}, 营收={revenue_current}")

        # 计算核心指标
        # 1. 资产负债率
        debt_ratio_current = (total_liabilities_current / total_assets_current * 100) if total_assets_current > 0 else 0
        debt_ratio_previous = (total_liabilities_previous / total_assets_previous * 100) if total_assets_previous > 0 else 0

        # 2. 应付账款周转率
        payable_turnover_current = (operating_cost_current / accounts_payable_current) if accounts_payable_current > 0 else 0
        payable_turnover_previous = (operating_cost_previous / accounts_payable_previous) if accounts_payable_previous > 0 else 0

        # 3. 利润变现率（净利润/经营现金流）
        profit_cash_rate_current = (operating_cashflow_current / net_profit_current) if net_profit_current > 0 else 0
        profit_cash_rate_previous = (operating_cashflow_previous / net_profit_previous) if net_profit_previous > 0 else 0

        # 4. 短期负债偿还能力（流动比率）
        current_ratio = (current_assets / current_liabilities * 100) if current_liabilities > 0 else 0
        current_ratio_previous = (current_assets_previous / current_liabilities_previous * 100) if current_liabilities_previous > 0 else 0

        # 5. 应收账款周转率
        receivable_turnover_current = (revenue_current / accounts_receivable_current) if accounts_receivable_current > 0 else 0
        receivable_turnover_previous = (revenue_previous / accounts_receivable_previous) if accounts_receivable_previous > 0 else 0

        # 构建完整数据结构
        result = {
            'report_date': current_col,
            'previous_date': previous_col,
            'coreIndicators': {
                'debtRatio': {
                    'value': f"{debt_ratio_current:.1f}%",
                    'previous': f"{debt_ratio_previous:.1f}%",
                    'trend': 'up' if debt_ratio_current > debt_ratio_previous else 'down' if debt_ratio_current < debt_ratio_previous else 'neutral',
                    'change': f"{debt_ratio_current - debt_ratio_previous:+.1f}%"
                },
                'payableTurnover': {
                    'value': f"{payable_turnover_current:.1f}",
                    'previous': f"{payable_turnover_previous:.1f}",
                    'trend': 'up' if payable_turnover_current > payable_turnover_previous else 'down' if payable_turnover_current < payable_turnover_previous else 'neutral',
                    'change': f"{((payable_turnover_current - payable_turnover_previous) / payable_turnover_previous * 100):+.0f}%" if payable_turnover_previous > 0 else "N/A"
                },
                'profitCashRate': {
                    'value': f"{profit_cash_rate_current:.1f}",
                    'previous': f"{profit_cash_rate_previous:.1f}",
                    'trend': 'up' if profit_cash_rate_current > profit_cash_rate_previous else 'down' if profit_cash_rate_current < profit_cash_rate_previous else 'neutral',
                    'change': f"{((profit_cash_rate_current - profit_cash_rate_previous) / profit_cash_rate_previous * 100):+.0f}%" if profit_cash_rate_previous > 0 else "N/A"
                },
                'currentRatio': {
                    'value': f"{current_ratio:.0f}%",
                    'previous': f"{current_ratio_previous:.0f}%",
                    'trend': 'up' if current_ratio > current_ratio_previous else 'down' if current_ratio < current_ratio_previous else 'neutral',
                    'change': f"{current_ratio - current_ratio_previous:+.0f}%"
                },
                'receivableTurnover': {
                    'value': f"{receivable_turnover_current:.1f}",
                    'previous': f"{receivable_turnover_previous:.1f}",
                    'trend': 'up' if receivable_turnover_current > receivable_turnover_previous else 'down' if receivable_turnover_current < receivable_turnover_previous else 'neutral',
                    'change': f"{((receivable_turnover_current - receivable_turnover_previous) / receivable_turnover_previous * 100):+.0f}%" if receivable_turnover_previous > 0 else "N/A"
                }
            },
            'detailData': {
                'cashFlowRisk': extract_detail_data(balance, cashflow, income, current_col, previous_col, 'cash'),
                'supplyChainRisk': extract_detail_data(balance, cashflow, income, current_col, previous_col, 'supply'),
                'profitabilityRisk': extract_detail_data(balance, cashflow, income, current_col, previous_col, 'profit'),
                'otherRisk': extract_detail_data(balance, cashflow, income, current_col, previous_col, 'other')
            }
        }

        print("数据处理成功")
        return result

    except Exception as e:
        print(f"Error calculating indicators: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def extract_detail_data(balance, cashflow, income, current_col, previous_col, category):
    """提取详细财务数据"""
    def get_value(df, row_name, col):
        try:
            row = df[df.iloc[:, 0] == row_name]
            if not row.empty:
                val = row.iloc[0][col]
                if isinstance(val, str):
                    val = val.replace(',', '')
                if val in ['', '--', None]:
                    return "缺失"
                return f"{float(val):,.0f}"
            return "缺失"
        except:
            return "缺失"

    def calc_change(current, previous):
        try:
            if current == "缺失" or previous == "缺失":
                return "缺失"
            c = float(current.replace(',', ''))
            p = float(previous.replace(',', ''))
            if p == 0:
                return "N/A"
            change = ((c - p) / p * 100)
            return f"{change:+.0f}%"
        except:
            return "缺失"

    data = {}

    if category == 'cash':
        items = [
            ('货币资金', balance),
            ('流动负债合计', balance),
            ('流动比率', None),
            ('经营活动产生的现金流量净额', cashflow),
            ('净利润', income),
            ('营业成本', income)
        ]

        for item_name, df in items:
            if df is not None:
                current = get_value(df, item_name, current_col)
                previous = get_value(df, item_name, previous_col)
                data[item_name] = {
                    'current': current,
                    'previous': previous,
                    'change': calc_change(current, previous)
                }
            elif item_name == '流动比率':
                ca_c = get_value(balance, '流动资产合计', current_col)
                cl_c = get_value(balance, '流动负债合计', current_col)
                ca_p = get_value(balance, '流动资产合计', previous_col)
                cl_p = get_value(balance, '流动负债合计', previous_col)

                try:
                    ratio_c = f"{(float(ca_c.replace(',', '')) / float(cl_c.replace(',', '')) * 100):.0f}%"
                    ratio_p = f"{(float(ca_p.replace(',', '')) / float(cl_p.replace(',', '')) * 100):.0f}%"
                    data['流动比率'] = {
                        'current': ratio_c,
                        'previous': ratio_p,
                        'change': f"{float(ratio_c[:-1]) - float(ratio_p[:-1]):+.0f}%"
                    }
                except:
                    data['流动比率'] = {'current': '缺失', 'previous': '缺失', 'change': '缺失'}

    elif category == 'supply':
        items = [
            ('应付账款', balance),
            ('预付款项', balance),
            ('应付票据', balance)
        ]

        for item_name, df in items:
            current = get_value(df, item_name, current_col)
            previous = get_value(df, item_name, previous_col)
            data[item_name] = {
                'current': current,
                'previous': previous,
                'change': calc_change(current, previous)
            }

    elif category == 'profit':
        items = [
            ('净利润', income),
            ('营业收入', income),
            ('营业成本', income),
            ('营业利润', income),
            ('利润总额', income)
        ]

        for item_name, df in items:
            current = get_value(df, item_name, current_col)
            previous = get_value(df, item_name, previous_col)
            data[item_name] = {
                'current': current,
                'previous': previous,
                'change': calc_change(current, previous)
            }

    elif category == 'other':
        items = [
            ('应收账款', balance),
            ('存货', balance),
            ('固定资产', balance),
            ('无形资产', balance),
            ('资产总计', balance),
            ('负债合计', balance)
        ]

        for item_name, df in items:
            current = get_value(df, item_name, current_col)
            previous = get_value(df, item_name, previous_col)
            data[item_name] = {
                'current': current,
                'previous': previous,
                'change': calc_change(current, previous)
            }

    return data

@app.route('/')
def index():
    return send_from_directory('.', 'supplier-finance.html')

@app.route('/api/search', methods=['GET'])
def search_companies():
    """搜索上市公司"""
    query = request.args.get('q', '').strip()

    if not query:
        return jsonify([])

    try:
        print(f"搜索公司: {query}")
        # 获取A股上市公司列表
        stock_info = safe_api_call(ak.stock_info_a_code_name)

        if stock_info is None or stock_info.empty:
            print("无法获取股票列表")
            return jsonify([])

        # 模糊搜索
        results = stock_info[
            stock_info['code'].str.contains(query, na=False) |
            stock_info['name'].str.contains(query, na=False)
        ].head(10)

        print(f"找到 {len(results)} 个结果")
        return jsonify(results.to_dict('records'))

    except Exception as e:
        print(f"Search error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/api/company/<stock_code>', methods=['GET'])
def get_company_data(stock_code):
    """获取公司财务数据"""
    try:
        print(f"获取公司数据: {stock_code}")

        # 获取公司基本信息
        stock_info = safe_api_call(ak.stock_info_a_code_name)

        if stock_info is None or stock_info.empty:
            return jsonify({'error': '无法获取公司列表'}), 500

        company_info = stock_info[stock_info['code'] == stock_code]

        if company_info.empty:
            return jsonify({'error': 'Company not found'}), 404

        # 计算财务指标
        financial_data = calculate_financial_indicators(stock_code)

        if financial_data is None:
            return jsonify({'error': 'Failed to fetch financial data'}), 500

        result = {
            'code': stock_code,
            'name': company_info.iloc[0]['name'],
            'financial_data': financial_data
        }

        return jsonify(result)

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print("启动供应商财务健康度分析系统...")
    print(f"请访问: http://localhost:{port}")
    app.run(host='0.0.0.0', debug=False, port=port)
