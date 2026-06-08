@echo off
chcp 65001 > nul
set VENV=C:\Users\yona\Desktop\Crypto_AML\crypto-aml-tracker\backend-py\venv\Scripts\python.exe
echo Running UTXO full ETL...
%VENV% C:\Users\yona\Desktop\Crypto_AML\AML\run_utxo_full_etl.py
echo Done.
