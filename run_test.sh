#!/bin/bash
# Run the RQ workers in the background for testing purposes.
#
# Note: This script is intended for testing purposes only.  In
# production the workers should be started with a process manager like
# systemd.

rq worker enqueue_objects &
rq worker download_object &
rq worker create_sip &
rq worker submit_sip &
rq worker confirm_sip &

# Wait a bit for workers to start and stop outputting to console
sleep 1

printf "\nWorkers started:\n%s\n\n" "$(jobs -l)"
printf "Press Ctrl+C to shutdown the workers.\n"
while true; do sleep 10; done

# Note: Workers will stop when the script is terminated with Ctrl+C
# because they are background jobs and the script is the parent process.
