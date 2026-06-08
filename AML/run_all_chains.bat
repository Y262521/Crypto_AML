@echo off
chcp 65001 > nul
cd /d C:\Users\yona\Desktop\Crypto_AML\AML
set VENV=C:\Users\yona\Desktop\Crypto_AML\crypto-aml-tracker\backend-py\venv\Scripts\python.exe

echo ============================================================
echo  MULTI-CHAIN ETL PIPELINE
echo  Runs: ETH, BNB, Polygon, Arbitrum, Base, BTC, LTC, DOGE, BCH, SOL
echo ============================================================
echo.

%VENV% run_all_chains.py
echo.
echo Done.
