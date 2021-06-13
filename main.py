# TinkProject
# developed by.. sorry, I should stay anonymous for my security.
# my nickname: softandiron
# Moscow 2021

import logging
import sys
import time
from dataclasses import dataclass
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from pycbrf.rates import ExchangeRate
from pycbrf.toolbox import ExchangeRates

import data_parser
from excel_builder import build_excel_file, supported_currencies

# creating ruble 1:1 exchange rate for cleaner iterating over currencies
ruble = ExchangeRate(code='RUB', value=1, rate=1, name='Рубль', id='KOSTYL', num='KOSTYL', par='KOSTYL')


def get_exchange_rate(date):
    rate = ExchangeRates(date)
    rate.rates.append(ruble)
    return rate


@dataclass
class PortfolioPosition:
    figi: str
    name: str
    ticker: str
    balance: Decimal
    currency: Decimal
    ave_price: Decimal
    sum_buy: Decimal
    exp_yield: Decimal
    market_price: Decimal
    percent_change: Decimal
    market_cost: Decimal
    market_cost_rub_cb: Decimal
    ave_buy_price_rub: Decimal
    sum_buy_rub: Decimal
    tax_base: Decimal
    exp_tax: Decimal


@dataclass
class PortfolioOperation:
    op_type: str
    op_date: str
    op_currency: str
    op_payment: Decimal


def get_portfolio_cash_rub():
    for cur in currencies.payload.currencies:
        if cur.currency == 'RUB':
            return cur.balance
    return 0


# tax calculation
def calculate_ave_buy_price_rub(this_pos):
    item_list = []
    # for this position's figi - add units into the list from operations
    for ops in reversed(operations.payload.operations):
        rate_for_date = get_exchange_rate(ops.date)

        if ops.figi == this_pos.figi and ops.payment != 0:
            if ops.operation_type == 'Buy':
                if ops.currency in supported_currencies:
                    # price for 1 item
                    item = (ops.payment / ops.quantity_executed) * rate_for_date[ops.currency].value
                    # add bought items to the list:
                    item_list += [item] * ops.quantity_executed
                else:
                    logger.warning('unknown currency in position: ' + this_pos.name)
            elif ops.operation_type == 'Sell':
                # remove sold items from the list:
                number = ops.quantity_executed
                del item_list[:number]
            time.sleep(delay_time)  # to prevent TimeOut error

        # solving problem with TCSG stocks:
        if this_pos.figi == 'BBG00QPYJ5H0':
            if ops.figi == 'BBG005DXJS36' and ops.payment != 0:
                if ops.operation_type == 'Buy':
                    if ops.currency == 'RUB':
                        # price for 1 item
                        item = ops.payment / ops.quantity_executed
                        # add bought items to the list:
                        item_list += [item] * ops.quantity_executed
                    else:
                        logger.warning('unknown currency in position: ' + this_pos.name)
                elif ops.operation_type == 'Sell':
                    # remove sold items from the list:
                    number = ops.quantity_executed
                    del item_list[:number]

    # calculate average buying price in Rub
    ave_buy_price_rub = 0
    if len(item_list) != 0:
        ave_buy_price_rub = sum(item_list) / len(item_list)

    return abs(ave_buy_price_rub)


def creating_positions_objects():
    logger.info('creating position objects..')

    number_positions = len(positions.payload.positions)
    logger.info(f'{number_positions} positions in portfolio')
    number_operations = len(operations.payload.operations)
    logger.info(f'{number_operations} operations in period')

    my_positions = list()
    for this_pos in positions.payload.positions:
        # market cost (total for each position)
        market_cost = this_pos.expected_yield.value + (this_pos.average_position_price.value * this_pos.balance)

        # current market prise for 1 item
        market_price = market_cost / this_pos.balance

        # % change
        percent_change = ((market_price / this_pos.average_position_price.value) * 100) - 100

        global market_cost_rub_cb
        # market value rub CB
        if this_pos.average_position_price.currency in supported_currencies:
            market_cost_rub_cb = market_cost * rates_today_cb[this_pos.average_position_price.currency].value
            time.sleep(delay_time)  # to prevent TimeOut error
        else:
            market_cost_rub_cb = 'unknown currency'

        # sum buy (purchase amount)

        sum_buy = this_pos.average_position_price.value * this_pos.balance

        ave_buy_price_rub = calculate_ave_buy_price_rub(this_pos)
        sum_buy_rub = ave_buy_price_rub * this_pos.balance

        tax_base = Decimal(max(0, market_cost_rub_cb - sum_buy_rub))
        exp_tax = tax_base * Decimal(tax_rate / 100)

        my_positions.append(PortfolioPosition(this_pos.figi, this_pos.name, this_pos.ticker, this_pos.balance,
                                              this_pos.average_position_price.currency,
                                              this_pos.average_position_price.value, sum_buy,
                                              this_pos.expected_yield.value,
                                              market_price, percent_change, market_cost, market_cost_rub_cb,
                                              ave_buy_price_rub, sum_buy_rub, tax_base, exp_tax))

        logger.info(this_pos.name)

    logger.info('..positions are ready')
    return my_positions


def get_average_percent():
    sum_buy_list, yield_list = []
    for this_pos in my_positions:
        if this_pos.currency in supported_currencies:
            sum_buy_list.append(this_pos.sum_buy * market_rate_today[this_pos.currency])
            yield_list.append(this_pos.exp_yield * market_rate_today[this_pos.currency])
        else:
            logger.warning(f'Unsupported currency: {this_pos.currency}')
    return (sum(yield_list) / sum(sum_buy_list)) * 100


def get_portfolio_cost_rub_market():
    costs_list = []
    for this_pos in my_positions:
        if this_pos.currency in supported_currencies:
            costs_list.append(this_pos.market_cost * market_rate_today[this_pos.currency])
        else:
            logger.warning(f'Unsupported currency: {this_pos.currency}')
    return sum(costs_list) + cash_rub


def calculate_cb_value_rub_sum():
    return sum(pos.market_cost_rub_cb for pos in my_positions) + cash_rub


def calculate_sum_pos_ave_buy_rub():
    return sum(pos.sum_buy_rub for pos in my_positions)


def calculate_sum_exp_tax():
    return sum(pos.exp_tax for pos in my_positions)


def create_operations_objects():
    logger.info('creating operations objects..')
    my_operations = list()
    for this_op in operations.payload.operations:
        my_operations.append(PortfolioOperation(this_op.operation_type,
                                                this_op.date,
                                                this_op.currency,
                                                this_op.payment))

    logger.info('..operations are ready')
    return my_operations


def calculate_operations_sums_rub(current_op_type):
    op_list = []
    for op in my_operations:
        if op.op_type == current_op_type and op.op_payment != 0:
            if op.op_currency in supported_currencies:
                rate = get_exchange_rate(op.op_date)
                op_list.append(op.op_payment * rate[op.op_currency].value)
                time.sleep(delay_time)  # to prevent TimeOut error
            else:
                logger.warning(f'Unsupported currency: {op.op_currency}')
    return sum(op_list)


def calc_investing_period():
    start_date = account_data['start_date'].replace(tzinfo=None)
    inv_period = relativedelta(account_data['now_date'], start_date)
    return inv_period


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(asctime)s - %(message)s', datefmt='%H:%M:%S')
    logger = logging.getLogger()
    if sys.argv[-1] in ['-q', '--quiet']:
        logger.setLevel(logging.WARNING)

    start_time = time.time()
    delay_time = 0.2
    tax_rate = 13  # percents
    logger.info('Start')

    positions, operations, market_rate_today, currencies = data_parser.get_api_data(logger)

    account_data = data_parser.parse_text_file(logger)
    rates_today_cb = get_exchange_rate(account_data['now_date'])

    cash_rub = get_portfolio_cash_rub()
    my_positions = creating_positions_objects()
    average_percent = get_average_percent()
    portfolio_cost_rub_market = get_portfolio_cost_rub_market()

    sum_profile = {}
    sum_profile['portfolio_value_rub_cb'] = calculate_cb_value_rub_sum()
    sum_profile['pos_ave_buy_rub'] = calculate_sum_pos_ave_buy_rub()
    sum_profile['exp_tax'] = calculate_sum_exp_tax()

    my_operations = create_operations_objects()

    for operation in ['PayIn', 'PayOut', 'Buy', 'BuyCard', 'Sell', 'Coupon', 'Dividend', 'Tax', 'TaxCoupon', 'TaxDividend', 'BrokerCommission', 'ServiceCommission']:
        logger.info(f'calculating {operation} operations sum in RUB..')
        sum_profile[operation.lower()] = calculate_operations_sums_rub(operation)

    logger.info('preparing statistics')

    # investing period
    investing_period = calc_investing_period()
    investing_period_str = f'{investing_period.years}y {investing_period.months}m {investing_period.days}d'
    logger.info(f'investing period: {investing_period_str}\n')

    # PayIn - PayOut
    payin_payout = sum_profile['payin'] - abs(sum_profile['payout'])

    # EXCEL
    build_excel_file(my_positions, my_operations, rates_today_cb, market_rate_today,
                     average_percent, portfolio_cost_rub_market, sum_profile,
                     investing_period_str, cash_rub, payin_payout, logger)

    logger.info(f'done in {time.time() - start_time:.2f} seconds')
