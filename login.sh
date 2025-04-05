#!/bin/bash

# Captive portal details
PORTAL_URL="http://10.24.1.2:2280/cportal/ip/user_login.php"
BASE_FRAME_URL="http://10.24.1.2:2280/cportal/login.html"
USERNAME="jssbh23"
PASSWORD="jssbh23"
CHECK_INTERVAL=1800  # 30 minutes in seconds
COOKIE_FILE="/tmp/captive_portal_cookies.txt"
LOG_FILE="/tmp/captive_portal.log"

# Function to log messages with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to handle script termination
cleanup() {
    log_message "Cleaning up and exiting..."
    rm -f "$COOKIE_FILE"
    exit 0
}

# Register cleanup function for script termination
trap cleanup SIGINT SIGTERM

# Function to check internet connectivity
check_internet() {
    local test_urls=("google.com" "8.8.8.8" "1.1.1.1")
    
    for url in "${test_urls[@]}"; do
        if ping -c 1 "$url" &>/dev/null; then
            log_message "Internet connection is active"
            return 0
        fi
    done
    
    log_message "No internet connection"
    return 1
}

# Function to extract frame URL from response
get_frame_url() {
    local response="$1"
    local frame_url=$(echo "$response" | grep -o 'FRAME SRC="[^"]*"' | cut -d'"' -f2)
    if [ -n "$frame_url" ]; then
        echo "http://10.24.1.2:2280$frame_url"
    else
        echo "$BASE_FRAME_URL"
    fi
}

# Function to perform login
do_login() {
    log_message "Attempting login..."
    
    # First try to access the main portal page
    local MAIN_RESPONSE=$(curl -s -L -c "$COOKIE_FILE" -b "$COOKIE_FILE" "$PORTAL_URL")
    
    # Check if we need to handle a frame
    if echo "$MAIN_RESPONSE" | grep -q "FRAMESET"; then
        log_message "Detected frameset, extracting frame URL..."
        local FRAME_URL=$(get_frame_url "$MAIN_RESPONSE")
        log_message "Accessing frame URL: $FRAME_URL"
        RESPONSE=$(curl -s -L -c "$COOKIE_FILE" -b "$COOKIE_FILE" "$FRAME_URL")
    else
        RESPONSE="$MAIN_RESPONSE"
    fi
    
    # Check if already logged in
    if echo "$RESPONSE" | grep -q "Already logged in"; then
        log_message "Already logged in - session is active"
        return 0
    fi
    
    # Extract any hidden fields or tokens if they exist
    local HIDDEN_FIELDS=""
    while read -r line; do
        if echo "$line" | grep -q 'input.*type="hidden"'; then
            name=$(echo "$line" | grep -o 'name="[^"]*"' | cut -d'"' -f2)
            value=$(echo "$line" | grep -o 'value="[^"]*"' | cut -d'"' -f2)
            if [ ! -z "$name" ] && [ ! -z "$value" ]; then
                HIDDEN_FIELDS="$HIDDEN_FIELDS -d $name=$value"
            fi
        fi
    done <<< "$RESPONSE"
    
    # Set the login URL to the correct form action
    local LOGIN_URL="http://10.24.1.2:2280/submit/user_login.php"
    
    log_message "Using login URL: $LOGIN_URL"
    
    # Perform the login with the correct field names
    local LOGIN_CMD="curl -s -L -c $COOKIE_FILE -b $COOKIE_FILE \
        -d usrname=$USERNAME \
        -d newpasswd=$PASSWORD \
        -d terms=on \
        -d page_sid=internal \
        -d update_btn=Login \
        $HIDDEN_FIELDS \
        \"$LOGIN_URL\""
    
    log_message "Sending login request..."
    local LOGIN_RESPONSE=$(eval "$LOGIN_CMD")
    
    # Save the response for debugging
    echo "$LOGIN_RESPONSE" > "/tmp/login_response.html"
    
    # Check login success
    if echo "$LOGIN_RESPONSE" | grep -q "success\|Already logged in\|Welcome\|logged in"; then
        log_message "Login successful"
        # Verify internet connectivity
        if check_internet; then
            log_message "Internet access confirmed"
            return 0
        else
            log_message "Login seemed successful but no internet access"
            return 1
        fi
    else
        log_message "Login failed"
        # Log response for debugging
        echo "$LOGIN_RESPONSE" > "/tmp/failed_login_response.html"
        log_message "Saved failed login response to /tmp/failed_login_response.html"
        return 1
    fi
}

# Main loop
main() {
    log_message "Starting login monitor..."
    
    # Create or clear log file
    > "$LOG_FILE"
    
    # Remove old cookie file if it exists
    rm -f "$COOKIE_FILE"
    
    while true; do
        # Try to login
        if do_login; then
            current_time=$(date '+%H:%M:%S')
            log_message "Waiting 30 minutes before next check... (Current time: $current_time)"
            
            # Check connection periodically while waiting
            local time_elapsed=0
            while [ $time_elapsed -lt $CHECK_INTERVAL ]; do
                sleep 60  # Check every minute
                if ! check_internet; then
                    log_message "Internet connection lost, attempting to reconnect..."
                    break
                fi
                time_elapsed=$((time_elapsed + 60))
            done
        else
            log_message "Login failed, retrying in 5 seconds..."
            sleep 5
        fi
    done
}

# Start the script
main 