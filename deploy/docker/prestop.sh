#!/bin/bash

shutdown_crons() {
    cron_processes=$(ps aux | grep crontab | grep -v grep)
    if [ -z "$cron_processes" ]; then
        echo "Cron jobs are not running..."
        echo "Cron Scheduler Status..."
        service cron status
        echo "Cron Jobs shutdown successfully."
        crontab -l
        return 0
    else
        echo "Cron jobs are still running:"
        echo "$cron_processes"
        return 1
    fi
}

service cron status

crontab -r

# Main loop to check and wait if cron jobs are running
while true; do
    shutdown_crons
    if [ $? -eq 0 ]; then
        break
    else
        echo "Retrying in 5 seconds..."
        sleep 5
    fi
done