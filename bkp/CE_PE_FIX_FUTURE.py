# Place CE or PE orders independently
if not ce_order_id and ce_ltp and ce_ltp >= high_ce * 0.98:
    quantity_buy = calculate_quantity_with_risk(high_ce + 0.20)
    if ce_ltp > high_ce:
        log_and_print(f"🚀 CE breakout confirmed. Placing MARKET order.")
        ce_order_id = place_order(ce_symbol, "BUY", quantity_buy, None, ce_symbol_token, "MARKET")
        send_whatsapp_message(f"🚀{current_date}: CE breakout confirmed. Placing MARKET order.")
    else:
        log_and_print(f"🚀 Placing CE Limit Order at {high_ce + 0.20}")
        ce_order_id = place_order(ce_symbol, "BUY", quantity_buy, high_ce + 0.20, ce_symbol_token, "STOPLOSS_LIMIT")
        send_whatsapp_message(f"🚀{current_date}: Placing BUY CE({ce_symbol}) Limit Order at {high_ce + 0.20}")

if not pe_order_id and pe_ltp and pe_ltp >= high_pe * 0.98:
    quantity_buy = calculate_quantity_with_risk(high_pe + 0.20)
    if pe_ltp > high_pe:
        log_and_print(f"🚀 PE breakout confirmed. Placing MARKET order.")
        pe_order_id = place_order(pe_symbol, "BUY", quantity_buy, None, pe_symbol_token, "MARKET")
        send_whatsapp_message(f"🚀{current_date}: PE breakout confirmed. Placing MARKET order.")
    else:
        log_and_print(f"🚀 Placing PE Limit Order at {high_pe + 0.20}")
        pe_order_id = place_order(pe_symbol, "BUY", quantity_buy, high_pe + 0.20, pe_symbol_token, "STOPLOSS_LIMIT")
        send_whatsapp_message(f"🚀{current_date}: Placing BUY PE({pe_symbol}) Limit Order at {high_pe + 0.20}")

# Check execution and set active_trade accordingly
if ce_order_id and active_trade is None:
    ce_status = get_order_status_from_book(ce_order_id)
    if ce_status in ["complete", "executed"]:
        active_trade = "CE"
        log_and_print("✅ CE order executed.")
        send_whatsapp_message(f"✅{current_date}: CE order executed.")
        if pe_order_id:
            cancel_order(pe_order_id)
            log_and_print("❌ Cancelled PE order after CE executed.")
            send_whatsapp_message(f"❌{current_date}: Cancelled PE order after CE execution.")
            pe_order_id = None

if pe_order_id and active_trade is None:
    pe_status = get_order_status_from_book(pe_order_id)
    if pe_status in ["complete", "executed"]:
        active_trade = "PE"
        log_and_print("✅ PE order executed.")
        send_whatsapp_message(f"✅{current_date}: PE order executed.")
        if ce_order_id:
            cancel_order(ce_order_id)
            log_and_print("❌ Cancelled CE order after PE executed.")
            send_whatsapp_message(f"❌{current_date}: Cancelled CE order after PE execution.")
            ce_order_id = None

# If trade is active, monitor for exits
if active_trade:
    trade_order_id = ce_order_id if active_trade == "CE" else pe_order_id
    order_status = get_order_status_from_book(trade_order_id)

    if order_status not in ["complete", "executed"]:
        if not pending_order_logged:
            log_and_print(f"🚨 Order {trade_order_id} is not EXECUTED yet. Skipping exit orders.")
            send_whatsapp_message(f"🚨{current_date}: Order {trade_order_id} is not EXECUTED yet. Skipping exit orders.")
            pending_order_logged = True
        continue

    pending_order_logged = False
    if not exit_order_logged:
        log_and_print(f"✅ Order {trade_order_id} is executed. Proceeding with exit orders.")
        send_whatsapp_message(f"✅{current_date}: Order {trade_order_id} is executed. Proceeding with exit orders.")
        exit_order_logged = True

    trade_symbol = ce_symbol if active_trade == "CE" else pe_symbol
    trade_symbol_token = ce_symbol_token if active_trade == "CE" else pe_symbol_token
    trade_ltp = get_ltp(trade_symbol, trade_symbol_token)
    entry_price = high_ce + 0.20 if active_trade == "CE" else high_pe + 0.20
    target_price_trigger = round(round((entry_price * 1.15) / 0.05) * 0.05, 2)
    target_price = "{:.2f}".format(target_price_trigger)
    stop_loss_price_trigger = round(round((entry_price * 0.90) / 0.05) * 0.05, 2)
    stop_loss_price = "{:.2f}".format(stop_loss_price_trigger)

    if trade_ltp >= target_price_trigger * 0.93 and target_order_id is None:
        if stop_loss_order_id:
            log_and_print(f"❌ Cancelling Stop Loss Order as Target is Near")
            cancel_order(stop_loss_order_id)
            stop_loss_order_id = None
        log_and_print(f"🎯 Placing Target Order at {target_price}")
        target_order_id = place_order(trade_symbol, "SELL", quantity_buy, target_price, trade_symbol_token)
        send_whatsapp_message(f"❌{current_date}: Cancelling SL & Placing Target order for {trade_symbol} at {target_price}")

    elif trade_ltp <= stop_loss_price_trigger * 1.05 and stop_loss_order_id is None:
        if target_order_id:
            log_and_print(f"❌ Cancelling Target Order and placing Stop Loss Order at {stop_loss_price}")
            cancel_order(target_order_id)
            target_order_id = None
        stop_loss_order_id = place_order(trade_symbol, "SELL", quantity_buy, stop_loss_price, trade_symbol_token)
        send_whatsapp_message(f"❌{current_date}: Cancelling Target & Placing SL order for {trade_symbol} at {stop_loss_price}")

    if trade_ltp >= target_price_trigger:
        log_and_print(f"✅ Target reached, exiting at {trade_ltp}")
        send_whatsapp_message(f"✅{current_date}: Target reached, exiting at {trade_ltp} for {trade_symbol}")
        break

    elif trade_ltp <= stop_loss_price_trigger:
        log_and_print(f"✅ Stop Loss triggered, exiting at {trade_ltp}")
        send_whatsapp_message(f"✅{current_date}: Stop Loss triggered, exiting at {trade_ltp} for {trade_symbol}")
        break
