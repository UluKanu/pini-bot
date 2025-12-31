#!/bin/bash

# source .env file for AZURE_STORAGE_ACCOUNT_KEY
if [ -f /app/.env ]; then
    export $(grep -v '^#' /app/.env | xargs)
fi

git clone https://github.com/dimm-city/pini-bot.git /app

/usr/local/bin/python /app/fetch_levels.py --combined_filename /app/output/combined.csv

echo "Uploading combined.csv to Azure Blob Storage..."
echo "${AZURE_STORAGE_ACCOUNT_KEY:0:5}"
az storage blob upload \
    --account-name dimmcity \
    --account-key "${AZURE_STORAGE_ACCOUNT_KEY}" \
    --container-name fetch-levels \
    --name combined.csv \
    --file /app/output/combined.csv \
    --overwrite true \
    --type block
