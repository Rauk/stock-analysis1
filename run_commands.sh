#!/bin/bash
# Dynamic parallel runner: keeps up to MAX_PARALLEL jobs running at all times.
# As soon as a job finishes, the next queued command is started immediately.
# Status is printed every 20s. Each script run gets its own timestamped log folder.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMANDS_FILE="$SCRIPT_DIR/commandsToExecute.txt"
MAX_PARALLEL=10
LOG_BASE="$SCRIPT_DIR/logs"

# Per-run log folder
RUN_TS=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$LOG_BASE/run_$RUN_TS"
mkdir -p "$LOG_DIR"

# Read commands — skip shebang, comments, and blank lines
mapfile -t COMMANDS < <(grep -v '^\s*#' "$COMMANDS_FILE" | grep -v '^\s*$' | grep -v '^#!/')
TOTAL=${#COMMANDS[@]}

if [ "$TOTAL" -eq 0 ]; then
    echo "No commands found in $COMMANDS_FILE"
    exit 1
fi

echo "════════════════════════════════════════════════════"
echo " Stock Analysis Runner — $RUN_TS"
echo " Commands : $TOTAL  |  Max parallel : $MAX_PARALLEL"
echo " Logs     : $LOG_DIR"
echo "════════════════════════════════════════════════════"

# ── Per-command state (indexed by command index 0..TOTAL-1) ───────────────────
# CMD_STATUS : pending | running | success | failed
CMD_STATUS=()
CMD_PID=()
CMD_LOG=()
CMD_COMPANY=()
CMD_START=()   # epoch seconds
CMD_END=()     # epoch seconds

for (( i=0; i<TOTAL; i++ )); do
    CMD_STATUS+=("pending")
    CMD_PID+=("")
    CMD_LOG+=("")
    CMD_COMPANY+=("")
    CMD_START+=("")
    CMD_END+=("")
done

extract_company() {
    local result
    result=$(echo "$1" | grep -oP '(?<=/company/)[^/]+' | head -1)
    echo "${result:-unknown}"
}

format_duration() {
    local secs=$1
    if [ "$secs" -lt 60 ]; then
        printf "%ds" "$secs"
    else
        printf "%dm%02ds" "$(( secs/60 ))" "$(( secs%60 ))"
    fi
}

start_job() {
    local idx=$1
    local cmd="${COMMANDS[$idx]}"
    local company
    company=$(extract_company "$cmd")

    local log_file="$LOG_DIR/${company}.log"
    CMD_COMPANY[$idx]="$company"
    CMD_LOG[$idx]="$log_file"
    CMD_START[$idx]=$(date +%s)
    CMD_STATUS[$idx]="running"

    {
        echo "======================================"
        echo "  Company : $company"
        echo "  Index   : $((idx+1)) / $TOTAL"
        echo "  Started : $(date '+%Y-%m-%d %H:%M:%S')"
        echo "  CMD     : $cmd"
        echo "======================================"
        echo ""
        eval "$cmd"
        EC=$?
        echo ""
        echo "======================================"
        echo "  Finished : $(date '+%Y-%m-%d %H:%M:%S')"
        if [ $EC -eq 0 ]; then
            echo "  Status   : SUCCESS"
        else
            echo "  Status   : FAILED (exit code: $EC)"
        fi
        echo "======================================"
        exit $EC
    } > "$log_file" 2>&1 &

    CMD_PID[$idx]=$!
    echo "  [START] #$((idx+1)) ${company}  →  ${company}.log"
}

print_status() {
    local now
    now=$(date +%s)
    local pending=0 running=0 success=0 failed=0

    echo ""
    echo "── Status Update  $(date '+%Y-%m-%d %H:%M:%S') ──────────────────────────────────────"
    printf "  %-5s %-16s %-10s %s\n" "No." "Company" "Status" "Duration"
    echo "  ──────────────────────────────────────────────────────"
    for (( i=0; i<TOTAL; i++ )); do
        local status="${CMD_STATUS[$i]}"
        local company="${CMD_COMPANY[$i]}"
        [ -z "$company" ] && company=$(extract_company "${COMMANDS[$i]}")

        local duration="-"
        if [ -n "${CMD_START[$i]}" ]; then
            local end_ts="${CMD_END[$i]:-$now}"
            duration=$(format_duration "$(( end_ts - CMD_START[$i] ))")
        fi

        case "$status" in
            pending) pending=$((pending+1)) ;;
            running) running=$((running+1)) ;;
            success) success=$((success+1)) ;;
            failed)  failed=$((failed+1))  ;;
        esac

        printf "  %-5s %-16s %-10s %s\n" "$((i+1))" "$company" "$status" "$duration"
    done
    echo "  ──────────────────────────────────────────────────────"
    printf "  Pending: %-4s Running: %-4s Success: %-4s Failed: %s\n" \
        "$pending" "$running" "$success" "$failed"
    echo ""
}

# ── Main loop ─────────────────────────────────────────────────────────────────
next_idx=0
last_status_ts=$(date +%s)

# Seed the initial pool
while [ "$next_idx" -lt "$TOTAL" ] && [ "$next_idx" -lt "$MAX_PARALLEL" ]; do
    start_job "$next_idx"
    next_idx=$(( next_idx + 1 ))
done

print_status

while true; do
    # Poll each running job
    for (( i=0; i<TOTAL; i++ )); do
        if [ "${CMD_STATUS[$i]}" = "running" ]; then
            pid="${CMD_PID[$i]}"
            if ! kill -0 "$pid" 2>/dev/null; then
                # Process finished — collect exit code
                wait "$pid"
                ec=$?
                CMD_END[$i]=$(date +%s)
                if [ "$ec" -eq 0 ]; then
                    CMD_STATUS[$i]="success"
                    echo "  [OK]   #$((i+1)) ${CMD_COMPANY[$i]}  ($(format_duration "$(( CMD_END[i] - CMD_START[i] ))"))"
                else
                    CMD_STATUS[$i]="failed"
                    echo "  [FAIL] #$((i+1)) ${CMD_COMPANY[$i]}  exit=$ec  →  ${CMD_COMPANY[$i]}.log"
                fi

                # Immediately start next queued command if any
                if [ "$next_idx" -lt "$TOTAL" ]; then
                    start_job "$next_idx"
                    next_idx=$(( next_idx + 1 ))
                fi
            fi
        fi
    done

    # Check if all commands are done
    all_done=true
    for (( i=0; i<TOTAL; i++ )); do
        s="${CMD_STATUS[$i]}"
        if [ "$s" = "pending" ] || [ "$s" = "running" ]; then
            all_done=false
            break
        fi
    done
    [ "$all_done" = true ] && break

    # Print status every 20 seconds
    now=$(date +%s)
    if (( now - last_status_ts >= 20 )); then
        print_status
        last_status_ts=$now
    fi

    sleep 2
done

print_status

# Final summary
total_success=0
total_fail=0
for (( i=0; i<TOTAL; i++ )); do
    [ "${CMD_STATUS[$i]}" = "success" ] && total_success=$(( total_success+1 ))
    [ "${CMD_STATUS[$i]}" = "failed"  ] && total_fail=$(( total_fail+1 ))
done

echo "════════════════════════════════════════════════════"
echo " Run complete — $RUN_TS"
echo " Succeeded : $total_success  |  Failed : $total_fail"
echo " Logs      : $LOG_DIR"
echo "════════════════════════════════════════════════════"
