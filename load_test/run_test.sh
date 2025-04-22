#!/bin/bash

mkdir -p reports

TOTAL_REQUESTS=1000
REPORT_FILE="reports/load_test_report_${TOTAL_REQUESTS}req.html"

echo "Starting load test simulation: ${TOTAL_REQUESTS} requests in a single run."

# Run Newman once for multiple iterations using the data file
newman run collection.json \
  --iteration-count ${TOTAL_REQUESTS} \
  --iteration-data iteration_data.json \
  --reporters cli,htmlextra \
  --reporter-htmlextra-export ${REPORT_FILE} \
  --disable-unicode

echo "✅ Done. Consolidated report for ${TOTAL_REQUESTS} requests is located at ${REPORT_FILE}"
