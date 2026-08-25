#!/bin/sh
set -eu

bootstrap_servers="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
topics_bin="${KAFKA_TOPICS_BIN:-kafka-topics.sh}"

for topic in \
  cases tasks documents users authority notifications \
  cases.dlq tasks.dlq documents.dlq users.dlq authority.dlq notifications.dlq
do
  "$topics_bin" --bootstrap-server "$bootstrap_servers" --create --if-not-exists \
    --topic "$topic" --partitions 3 --replication-factor 1
done
