@echo off
chcp 65001 > nul
cd /d C:\Users\yona\Desktop\Crypto_AML\AML

echo Using correct AML directory: %CD%
echo.
echo Running ETL pipeline (3 blocks, skip-neo4j)...
C:\Users\yona\Desktop\Crypto_AML\crypto-aml-tracker\backend-py\venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'src'); from aml_pipeline.pipelines.run_etl import main; import sys; sys.argv=['run_etl','--batch','3','--skip-neo4j']; main()"
