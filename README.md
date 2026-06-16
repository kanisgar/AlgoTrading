# AlgoTrading
Modules to install
python
sudo yum install pip
pip install pyotp
pip install smartapi-python
pip install pytz
pip install twilio
pip install logzero
pip install websocket-client

Main file -> app.py (Scheduled everyday in the morning 07.20 EET)
This is suitable only for AngelOne. Twilio Api for whatsapp.
test.py -> The script is for testing the twilio API. It will send Account balance . (Scheduled everyday 22.30 EET)


Target and Stop Loss Price Logic:
=================================
target_price_trigger	115%	                  Target is +15%
trade_ltp >= target_price_trigger * 0.93	      106.95% - Target prep starts at +6.95%
stop_loss_price_trigger	90%	                      Stop-loss is -10%
trade_ltp <= stop_loss_price_trigger * 1.05	      94.5%	- SL prep starts at -5.5%


Code Logic:
===========
target_price_trigger = round(round((entry_price * 1.15) / 0.05) * 0.05, 2)
target_price = "{:.2f}".format(target_price_trigger)
stop_loss_price_trigger = round(round((entry_price * 0.90) / 0.05) * 0.05, 2)
stop_loss_price = "{:.2f}".format(stop_loss_price_trigger)

if trade_ltp >= target_price_trigger * 0.93
--Place Target SL limit order
elif trade_ltp <= stop_loss_price_trigger * 1.05
--Place Stop Loss SL limit order