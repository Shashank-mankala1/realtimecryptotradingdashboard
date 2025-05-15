#!/bin/bash
set -e

touch /var/log/container.log

echo "Starting cron service..."
cron

echo "Tailing log..."
tail -f /var/log/container.log