#!/bin/sh
set -eu

bootstrap_servers="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"

for topic in \
  user.events case.events task.events document.events authority.events notification.events
do
  kafka-topics.sh --bootstrap-server "$bootstrap_servers" --create --if-not-exists \
    --topic "$topic" --partitions 3 --replication-factor 1
done
