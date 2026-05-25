# Run SnapMeal AI locally with PySpark configured for Windows
$py = (Get-Command python).Source
$env:PYSPARK_PYTHON = $py
$env:PYSPARK_DRIVER_PYTHON = $py
Set-Location $PSScriptRoot
streamlit run app.py
