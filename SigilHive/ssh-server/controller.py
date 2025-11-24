# controller.py - FIXED VERSION
import llm_gen
import asyncio
import numpy as np
import time
import random
from typing import Dict, Any, Optional
from datetime import datetime
from adaptive_response import AdaptiveResponseSystem
from smart_prompt_generator import SmartPromptGenerator
from dynamic_filesystem import DynamicFileSystem
from smart_cache import SmartCache
from enhanced_analytics import EnhancedAnalytics, CommandEvent


SHOPHUB_STRUCTURE = {
    # Home directory
    "~": {
        "type": "directory",
        "description": "Home directory of the ShopHub application user",
        "contents": [
            "shophub",
            ".env",
            ".bashrc",
            ".bash_profile",
            ".bash_history",
            ".bash_logout",
            ".profile",
            ".vimrc",
            ".gitconfig",
            ".ssh",
            ".local",
            ".cache",
            ".config",
            "README.md",
        ],
    },
    # SSH configuration
    "~/.ssh": {
        "type": "directory",
        "description": "SSH configuration and keys",
        "contents": [
            "authorized_keys",
            "id_rsa",
            "id_rsa.pub",
            "known_hosts",
            "config",
        ],
    },
    # Local user data
    "~/.local": {
        "type": "directory",
        "description": "User-specific data and programs",
        "contents": ["bin", "share", "lib"],
    },
    "~/.local/bin": {
        "type": "directory",
        "description": "User-installed binaries",
        "contents": ["npm", "node", "mongod"],
    },
    # Cache directory
    "~/.cache": {
        "type": "directory",
        "description": "Application cache files",
        "contents": ["npm", "node-gyp", "yarn"],
    },
    # Config directory
    "~/.config": {
        "type": "directory",
        "description": "Application configuration files",
        "contents": ["git", "npm"],
    },
    # Main application
    "~/shophub": {
        "type": "directory",
        "description": "Main ShopHub ecommerce application directory",
        "contents": [
            "app",
            "config",
            "database",
            "logs",
            "scripts",
            "node_modules",
            "public",
            "tests",
            ".git",
            ".gitignore",
            "docker-compose.yml",
            "Dockerfile",
            ".dockerignore",
            "package.json",
            "package-lock.json",
            ".env",
            ".env.example",
            "README.md",
            "LICENSE",
        ],
    },
    # Application source
    "~/shophub/app": {
        "type": "directory",
        "description": "Application source code",
        "contents": [
            "controllers",
            "models",
            "routes",
            "middleware",
            "utils",
            "views",
            "app.js",
            "server.js",
        ],
    },
    "~/shophub/app/controllers": {
        "type": "directory",
        "description": "Controller files for handling business logic",
        "contents": [
            "authController.js",
            "productController.js",
            "orderController.js",
            "userController.js",
            "cartController.js",
            "paymentController.js",
            "adminController.js",
            "reviewController.js",
        ],
    },
    "~/shophub/app/models": {
        "type": "directory",
        "description": "Database models and schemas",
        "contents": [
            "User.js",
            "Product.js",
            "Order.js",
            "Cart.js",
            "Payment.js",
            "Category.js",
            "Review.js",
            "Session.js",
            "index.js",
        ],
    },
    "~/shophub/app/routes": {
        "type": "directory",
        "description": "API route definitions",
        "contents": [
            "auth.js",
            "products.js",
            "orders.js",
            "users.js",
            "cart.js",
            "payments.js",
            "admin.js",
            "reviews.js",
            "index.js",
        ],
    },
    "~/shophub/app/middleware": {
        "type": "directory",
        "description": "Middleware for authentication and validation",
        "contents": [
            "auth.js",
            "validation.js",
            "errorHandler.js",
            "rateLimiter.js",
            "logger.js",
            "cors.js",
            "sanitizer.js",
        ],
    },
    "~/shophub/app/utils": {
        "type": "directory",
        "description": "Utility functions and helpers",
        "contents": [
            "emailService.js",
            "imageProcessor.js",
            "paymentGateway.js",
            "encryption.js",
            "validator.js",
            "logger.js",
            "helpers.js",
        ],
    },
    "~/shophub/app/views": {
        "type": "directory",
        "description": "Email templates and view files",
        "contents": [
            "email-templates",
            "order-confirmation.html",
            "password-reset.html",
            "welcome.html",
            "invoice.html",
        ],
    },
    "~/shophub/app/views/email-templates": {
        "type": "directory",
        "description": "Email template files",
        "contents": [
            "header.html",
            "footer.html",
            "button.html",
            "order-shipped.html",
        ],
    },
    # Configuration
    "~/shophub/config": {
        "type": "directory",
        "description": "Configuration files",
        "contents": [
            "database.js",
            "server.js",
            "payment.js",
            "email.js",
            "redis.js",
            "storage.js",
            "security.js",
            ".env.example",
        ],
    },
    # Database
    "~/shophub/database": {
        "type": "directory",
        "description": "Database migrations and seeds",
        "contents": ["migrations", "seeds", "backup", "init.sql", "schema.sql"],
    },
    "~/shophub/database/migrations": {
        "type": "directory",
        "description": "Database migration files",
        "contents": [
            "001_create_users.sql",
            "002_create_products.sql",
            "003_create_orders.sql",
            "004_create_categories.sql",
            "005_create_reviews.sql",
            "006_create_sessions.sql",
            "007_add_indexes.sql",
        ],
    },
    "~/shophub/database/seeds": {
        "type": "directory",
        "description": "Database seed data",
        "contents": [
            "users.json",
            "products.json",
            "categories.json",
            "reviews.json",
            "admin.json",
        ],
    },
    "~/shophub/database/backup": {
        "type": "directory",
        "description": "Database backups",
        "contents": [
            "backup-2025-01-15.tar.gz",
            "backup-2025-01-14.tar.gz",
            "backup-2025-01-13.tar.gz",
        ],
    },
    # Logs
    "~/shophub/logs": {
        "type": "directory",
        "description": "Application logs",
        "contents": [
            "access.log",
            "error.log",
            "payment.log",
            "audit.log",
            "combined.log",
            "security.log",
            "access.log.1",
            "error.log.1",
        ],
    },
    # Scripts
    "~/shophub/scripts": {
        "type": "directory",
        "description": "Utility scripts",
        "contents": [
            "deploy.sh",
            "backup.sh",
            "migrate.sh",
            "seed.sh",
            "health-check.sh",
            "restart.sh",
            "update.sh",
        ],
    },
    # Node modules
    "~/shophub/node_modules": {
        "type": "directory",
        "description": "NPM dependencies",
        "contents": [
            "express",
            "mongoose",
            "redis",
            "dotenv",
            "bcrypt",
            "jsonwebtoken",
            "cors",
            "helmet",
            "morgan",
            "multer",
            "nodemailer",
            "stripe",
            "winston",
        ],
    },
    "~/shophub/node_modules/express": {
        "type": "directory",
        "description": "Express.js framework",
        "contents": ["package.json", "index.js", "lib"],
    },
    "~/shophub/node_modules/mongoose": {
        "type": "directory",
        "description": "MongoDB ODM",
        "contents": ["package.json", "index.js", "lib"],
    },
    # Public assets
    "~/shophub/public": {
        "type": "directory",
        "description": "Static assets and public files",
        "contents": [
            "css",
            "js",
            "images",
            "uploads",
            "favicon.ico",
            "robots.txt",
        ],
    },
    "~/shophub/public/css": {
        "type": "directory",
        "description": "CSS stylesheets",
        "contents": ["main.css", "admin.css", "responsive.css"],
    },
    "~/shophub/public/js": {
        "type": "directory",
        "description": "JavaScript files",
        "contents": ["main.js", "checkout.js", "admin.js"],
    },
    "~/shophub/public/images": {
        "type": "directory",
        "description": "Image assets",
        "contents": ["logo.png", "banner.jpg", "products"],
    },
    "~/shophub/public/uploads": {
        "type": "directory",
        "description": "User uploaded files",
        "contents": ["avatars", "products", "temp"],
    },
    # Tests
    "~/shophub/tests": {
        "type": "directory",
        "description": "Test files and test data",
        "contents": [
            "unit",
            "integration",
            "e2e",
            "fixtures",
            "setup.js",
            "teardown.js",
        ],
    },
    "~/shophub/tests/unit": {
        "type": "directory",
        "description": "Unit tests",
        "contents": [
            "auth.test.js",
            "product.test.js",
            "order.test.js",
        ],
    },
    "~/shophub/tests/integration": {
        "type": "directory",
        "description": "Integration tests",
        "contents": [
            "api.test.js",
            "database.test.js",
        ],
    },
    # Git repository
    "~/shophub/.git": {
        "type": "directory",
        "description": "Git repository metadata",
        "contents": [
            "config",
            "HEAD",
            "refs",
            "objects",
            "hooks",
            "logs",
        ],
    },
    "~/shophub/.git/refs": {
        "type": "directory",
        "description": "Git references",
        "contents": ["heads", "remotes", "tags"],
    },
    "~/shophub/.git/refs/heads": {
        "type": "directory",
        "description": "Git branch references",
        "contents": ["main", "develop"],
    },
}

# File contents for common files
FILE_CONTENTS = {
    # Home directory files
    "~/README.md": """ShopHub E-commerce Platform - Production Server
==============================================

This server hosts the ShopHub application.

## Quick Links
- Application: /home/shophub/shophub
- Logs: /home/shophub/shophub/logs
- Config: /home/shophub/shophub/config

## Server Info
- OS: Ubuntu 22.04 LTS
- Node.js: v18.17.0
- MongoDB: v6.0
- Redis: v7.0

## Emergency Contacts
- DevOps: devops@shophub.com
- Security: security@shophub.com
""",
    "~/.bashrc": """# ~/.bashrc: executed by bash(1) for non-login shells.

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# History settings
HISTCONTROL=ignoreboth
HISTSIZE=1000
HISTFILESIZE=2000
shopt -s histappend

# Prompt
PS1='\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '

# Aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'

# Node.js version manager
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \\. "$NVM_DIR/nvm.sh"

# Application shortcuts
alias shophub='cd ~/shophub'
alias logs='cd ~/shophub/logs && tail -f access.log'
""",
    "~/.bash_history": """ls
cd shophub
npm start
git status
git pull origin main
pm2 restart all
cat .env
docker ps
docker-compose up -d
tail -f logs/access.log
npm install
node app/app.js
""",
    "~/.bash_profile": """# ~/.bash_profile: executed by bash(1) for login shells.

if [ -f ~/.bashrc ]; then
    . ~/.bashrc
fi

# Set PATH
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/shophub/node_modules/.bin:$PATH"
""",
    "~/.vimrc": """set number
set autoindent
set tabstop=4
set shiftwidth=4
set expandtab
syntax on
""",
    "~/.gitconfig": """[user]
	name = ShopHub Deploy
	email = deploy@shophub.com
[core]
	editor = vim
[alias]
	st = status
	co = checkout
	br = branch
	ci = commit
""",
    "~/.ssh/config": """Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_rsa

Host production
    HostName 10.0.1.50
    User shophub
    IdentityFile ~/.ssh/id_rsa
""",
    "~/.ssh/authorized_keys": """ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDZm... deploy@shophub.com
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCxy... admin@shophub.com
""",
    # Application files
    "~/.env": """# ShopHub Environment Variables - PRODUCTION
# WARNING: Keep this file secure!

# Server
NODE_ENV=production
PORT=3000
HOST=0.0.0.0

# Database
DB_HOST=localhost
DB_PORT=27017
DB_NAME=shophub_prod
DB_USER=shophub_user
DB_PASS=<redacted>

# Redis Cache
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=<redacted>

# JWT Authentication
JWT_SECRET=<redacted>
JWT_EXPIRE=7d

# Payment Gateway
STRIPE_PUBLIC_KEY=pk_live_<redacted>
STRIPE_SECRET_KEY=sk_live_<redacted>

# Email Service
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@shophub.com
SMTP_PASS=<redacted>

# AWS S3
AWS_ACCESS_KEY=<redacted>
AWS_SECRET_KEY=<redacted>
S3_BUCKET=shophub-uploads

# Application
CLIENT_URL=https://shophub.com
API_URL=https://api.shophub.com
""",
    "~/shophub/README.md": """# ShopHub - Modern E-commerce Platform

A full-stack ecommerce solution built with Node.js, Express, and MongoDB.

## Features
- User authentication & authorization
- Product catalog with search & filters
- Shopping cart & checkout
- Payment processing (Stripe)
- Order management
- Admin dashboard

## Tech Stack
- **Backend**: Node.js, Express.js
- **Database**: MongoDB, Redis
- **Authentication**: JWT
- **Payment**: Stripe API
- **Storage**: AWS S3

## Installation

```bash
npm install
cp .env.example .env
npm run migrate
npm run seed
npm start
```

## API Documentation
See `/docs/API.md` for complete API documentation.

## License
MIT License - See LICENSE file
""",
    "~/shophub/package.json": """{
  "name": "shophub",
  "version": "2.3.1",
  "description": "ShopHub E-commerce Platform",
  "main": "app/app.js",
  "scripts": {
    "start": "node app/app.js",
    "dev": "nodemon app/app.js",
    "test": "jest --coverage",
    "migrate": "node scripts/migrate.sh",
    "seed": "node scripts/seed.sh",
    "lint": "eslint .",
    "format": "prettier --write ."
  },
  "dependencies": {
    "express": "^4.18.2",
    "mongoose": "^7.5.0",
    "redis": "^4.6.7",
    "dotenv": "^16.3.1",
    "bcrypt": "^5.1.1",
    "jsonwebtoken": "^9.0.2",
    "cors": "^2.8.5",
    "helmet": "^7.0.0",
    "morgan": "^1.10.0",
    "multer": "^1.4.5-lts.1",
    "nodemailer": "^6.9.4",
    "stripe": "^13.5.0",
    "winston": "^3.10.0"
  },
  "devDependencies": {
    "nodemon": "^3.0.1",
    "jest": "^29.6.4",
    "eslint": "^8.48.0",
    "prettier": "^3.0.3"
  },
  "engines": {
    "node": ">=18.0.0",
    "npm": ">=9.0.0"
  }
}
""",
    "~/shophub/docker-compose.yml": """version: '3.8'

services:
  app:
    build: .
    ports:
      - '3000:3000'
    environment:
      - NODE_ENV=production
    depends_on:
      - mongodb
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  mongodb:
    image: mongo:6.0
    ports:
      - '27017:27017'
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=<redacted>
    volumes:
      - mongodb_data:/data/db
    restart: unless-stopped

  redis:
    image: redis:7.0
    ports:
      - '6379:6379'
    command: redis-server --requirepass <redacted>
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  mongodb_data:
  redis_data:
""",
    "~/shophub/Dockerfile": """FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

EXPOSE 3000

CMD ["node", "app/app.js"]
""",
    "~/shophub/.gitignore": """# Dependencies
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Environment
.env
.env.local
.env.*.local

# Logs
logs/
*.log

# Database
*.sqlite
*.db

# Uploads
public/uploads/*
!public/uploads/.gitkeep

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# Build
dist/
build/
""",
    "~/shophub/app/app.js": """const express = require('express');
const dotenv = require('dotenv');
const mongoose = require('mongoose');
const redis = require('redis');
const morgan = require('morgan');
const helmet = require('helmet');
const cookieParser = require('cookie-parser');
const cors = require('cors');

// Load environment variables
dotenv.config();

const app = express();

// Connect to MongoDB
mongoose.connect(process.env.MONGO_URI, {
    useNewUrlParser: true,
    useUnifiedTopology: true,
})
.then(() => console.log('MongoDB Connected...'))
.catch(err => console.error('MongoDB connection error:', err));

// Connect to Redis
const redisClient = redis.createClient({
    url: process.env.REDIS_URL
});
redisClient.on('connect', () => console.log('Redis Connected...'));
redisClient.on('error', err => console.error('Redis connection error:', err));
redisClient.connect();

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(helmet());
app.use(morgan('dev'));

const corsOptions = {
    origin: process.env.CLIENT_URL,
    credentials: true,
    optionsSuccessStatus: 200
};
app.use(cors(corsOptions));

// Import Routes
const authRoutes = require('./routes/auth');
const productRoutes = require('./routes/products');
const orderRoutes = require('./routes/orders');
const userRoutes = require('./routes/users');
const cartRoutes = require('./routes/cart');

// Route Middlewares
app.use('/api/auth', authRoutes);
app.use('/api/products', productRoutes);
app.use('/api/orders', orderRoutes);
app.use('/api/users', userRoutes);
app.use('/api/cart', cartRoutes);

// Basic route
app.get('/', (req, res) => {
    res.send('ShopHub API is running!');
});

// Error handling middleware
app.use((err, req, res, next) => {
    console.error(err.stack);
    res.status(err.statusCode || 500).json({
        success: false,
        message: err.message || 'Server Error'
    });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

module.exports = app;
""",
    "~/shophub/.env.example": """# Server
NODE_ENV=development
PORT=3000

# Database
DB_HOST=localhost
DB_NAME=shophub_dev
DB_USER=your_db_user
DB_PASS=your_db_password

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=your_jwt_secret_here
JWT_EXPIRE=7d

# Stripe
STRIPE_PUBLIC_KEY=your_stripe_public_key
STRIPE_SECRET_KEY=your_stripe_secret_key

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_email_password
""",
    "~/shophub/.git/config": """[core]
	repositoryformatversion = 0
	filemode = true
	bare = false
	logallrefupdates = true
[remote "origin"]
	url = git@github.com:shophub/shophub.git
	fetch = +refs/heads/*:refs/remotes/origin/*
[branch "main"]
	remote = origin
	merge = refs/heads/main
""",
    "~/shophub/.git/HEAD": """ref: refs/heads/main
""",
}

ENHANCEMENTS_ENABLED = True


class Controller:
    def __init__(self, persona: str = "shophub-server"):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.persona = persona
        self.background_tasks = []  # Track background tasks

        # ensure we modify the module-level flag if needed
        global ENHANCEMENTS_ENABLED

        # Initialize enhancement systems (with fallback)
        if ENHANCEMENTS_ENABLED:
            try:
                self.adaptive_system = AdaptiveResponseSystem()
                self.prompt_generator = SmartPromptGenerator()
                self.dynamic_fs = DynamicFileSystem(SHOPHUB_STRUCTURE)
                self.cache = SmartCache(max_memory_cache_size=100)
                self.analytics = EnhancedAnalytics()

                # DON'T start background tasks here - they'll be started later
                print("[Controller] ✅ All enhancements loaded successfully")
            except Exception as e:
                print(f"[Controller] ⚠️  Enhancement initialization error: {e}")
                ENHANCEMENTS_ENABLED = False

        if not ENHANCEMENTS_ENABLED:
            print("[Controller] Running in BASIC mode (no enhancements)")

    async def start_background_tasks(self):
        """Start background tasks - call this after event loop is running"""
        if not ENHANCEMENTS_ENABLED:
            return

        try:
            # Create and store background tasks
            cache_task = asyncio.create_task(self._background_cache_cleanup())
            fs_task = asyncio.create_task(self._background_fs_evolution())

            self.background_tasks.extend([cache_task, fs_task])
            print("[Controller] 🔄 Background tasks started")
        except Exception as e:
            print(f"[Controller] ⚠️  Could not start background tasks: {e}")

    async def stop_background_tasks(self):
        """Stop all background tasks gracefully"""
        for task in self.background_tasks:
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        print("[Controller] 🛑 Background tasks stopped")

    def _update_meta(self, session_id: str, event: Dict[str, Any]):
        meta = self.sessions.setdefault(
            session_id,
            {
                "cmd_count": 0,
                "elapsed": 0.0,
                "last_cmd": "",
                "current_dir": "~",
                "command_history": [],
                "discovered_files": [],
            },
        )
        meta["cmd_count"] = event.get("cmd_count", meta["cmd_count"])
        meta["elapsed"] = event.get("elapsed", meta["elapsed"])

        if "command" in event:
            cmd = event.get("command", meta["last_cmd"])
            meta["last_cmd"] = cmd
            meta["command_history"].append(cmd)

            # Keep last 50 commands
            if len(meta["command_history"]) > 50:
                meta["command_history"] = meta["command_history"][-50:]

        if "current_dir" in event:
            meta["current_dir"] = event.get("current_dir", meta["current_dir"])

        meta["last_ts"] = time.time()
        self.sessions[session_id] = meta
        return meta

    def get_directory_context(self, current_dir: str) -> Dict[str, Any]:
        """Get context about the current directory for the LLM"""
        normalized_dir = current_dir.strip()

        if normalized_dir.endswith("/") and normalized_dir != "/":
            normalized_dir = normalized_dir[:-1]

        if normalized_dir == "~" or normalized_dir == "":
            normalized_dir = "~"
        if normalized_dir in SHOPHUB_STRUCTURE:
            return SHOPHUB_STRUCTURE[normalized_dir]

        if not normalized_dir.startswith("~") and normalized_dir.startswith("/"):
            pass
        elif not normalized_dir.startswith("~"):
            maybe = f"~/{normalized_dir}"
            if maybe in SHOPHUB_STRUCTURE:
                return SHOPHUB_STRUCTURE[maybe]

        return {
            "type": "directory",
            "description": f"Directory: {current_dir}",
            "contents": [],
        }

    def classify_command(self, cmd: str) -> str:
        cmd = (cmd or "").strip()
        if cmd == "":
            return "noop"

        cmd_parts = cmd.split()
        base_cmd = cmd_parts[0] if cmd_parts else ""

        # Terminal control commands
        if base_cmd in ("clear", "reset"):
            return "clear_screen"
        if base_cmd == "history":
            return "show_history"
        if base_cmd == "echo":
            return "echo"
        if base_cmd == "env" or base_cmd == "printenv":
            return "show_env"

        # Commands that require arguments
        if base_cmd in ("cat", "less", "more"):
            # Check if filename is provided
            if len(cmd_parts) < 2:
                return "read_file_no_arg"
            return "read_file"
        if base_cmd in ("ls", "dir", "ll"):
            return "list_dir"
        if base_cmd in ("whoami", "id"):
            return "identity"
        if base_cmd in ("uname", "hostname"):
            return "system_info"
        if base_cmd in ("ps", "top", "htop"):
            return "process_list"
        if base_cmd in ("netstat", "ss"):
            return "netstat"
        if base_cmd == "ping":
            return "network_probe"
        if base_cmd in ("curl", "wget"):
            return "http_fetch"
        if base_cmd == "pwd":
            return "print_dir"
        if base_cmd in ("find", "locate"):
            return "search"
        if base_cmd in ("grep", "egrep"):
            # Check if pattern is provided
            if len(cmd_parts) < 2:
                return "grep_no_arg"
            return "grep"
        if base_cmd in ("tail", "head"):
            return "file_peek"
        if base_cmd == "df":
            return "disk_usage"
        if base_cmd == "free":
            return "memory_info"
        if base_cmd in ("docker", "docker-compose"):
            return "docker"
        if base_cmd in ("npm", "node"):
            return "nodejs"
        if base_cmd == "git":
            return "git"
        if base_cmd.startswith("sudo"):
            return "privilege_escalation"
        if base_cmd == "ssh":
            return "remote_ssh"
        return "unknown"

    def _file_exists_in_directory(self, current_dir: str, filename: str) -> bool:
        """Check if a file exists in the directory structure"""
        dir_context = self.get_directory_context(current_dir)
        contents = dir_context.get("contents", [])

        filename_lower = filename.lower()
        for item in contents:
            if item.lower() == filename_lower:
                return True
        return False

    def _find_file_case_insensitive(
        self, current_dir: str, filename: str
    ) -> Optional[str]:
        """Find a file in FILE_CONTENTS with case-insensitive matching"""
        if filename.startswith("~"):
            full_path = filename
        elif filename.startswith("/"):
            full_path = filename
        else:
            if current_dir.endswith("/"):
                full_path = f"{current_dir}{filename}"
            else:
                full_path = f"{current_dir}/{filename}"

        full_path = full_path.replace("//", "/")

        if full_path in FILE_CONTENTS:
            return full_path

        full_path_lower = full_path.lower()
        for key in FILE_CONTENTS.keys():
            if key.lower() == full_path_lower:
                return key

        return None

    async def get_action_for_session(
        self, session_id: str, event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhanced version with all new systems integrated
        """
        meta = self._update_meta(session_id, event)
        cmd = meta.get("last_cmd", "")
        current_dir = meta.get("current_dir", "~")
        command_history = meta.get("command_history", [])
        intent = self.classify_command(cmd)

        # ENHANCEMENT: Evolve filesystem based on activity
        if ENHANCEMENTS_ENABLED:
            try:
                self.dynamic_fs.evolve_filesystem(session_id, command_history)
                dir_context = self.dynamic_fs.get_structure().get(
                    current_dir, self.get_directory_context(current_dir)
                )
            except Exception:
                dir_context = self.get_directory_context(current_dir)
        else:
            dir_context = self.get_directory_context(current_dir)

        # ENHANCEMENT: Try cache first
        cache_key = f"{session_id}:{cmd}:{current_dir}"
        if ENHANCEMENTS_ENABLED:
            try:
                cached_response = await self.cache.get(cache_key)
                if cached_response:
                    print(f"[Controller] 💾 Cache hit for: {cmd}")

                    # Still apply adaptive modifications
                    attacker_profile = self.adaptive_system.get_attacker_profile(
                        session_id
                    )
                    if not attacker_profile:
                        attacker_profile = (
                            self.adaptive_system.analyze_attacker_behavior(
                                session_id, command_history
                            )
                        )

                    adaptive_result = self.adaptive_system.get_adaptive_response(
                        session_id, cmd, cached_response, command_history
                    )

                    return {
                        "response": adaptive_result["response"],
                        "delay": adaptive_result["delay"],
                    }
            except Exception:
                pass  # Cache miss or error, continue

        # Quick direct responses for trivial intents
        if intent == "print_dir":
            response_text = current_dir

            if ENHANCEMENTS_ENABLED:
                try:
                    await self.cache.set(cache_key, response_text)
                    self._log_to_analytics(
                        session_id, cmd, intent, current_dir, response_text, 0.01, True
                    )
                except Exception:
                    pass

            return {"response": response_text, "delay": 0.01}

        # Handle clear screen command
        if intent == "clear_screen":
            # ANSI escape code to clear screen and move cursor to top
            response_text = "\033[2J\033[H"

            if ENHANCEMENTS_ENABLED:
                try:
                    self._log_to_analytics(
                        session_id,
                        cmd,
                        intent,
                        current_dir,
                        "[screen cleared]",
                        0.01,
                        True,
                    )
                except Exception:
                    pass

            return {"response": response_text, "delay": 0.01}

        # Handle history command
        if intent == "show_history":
            history_lines = []
            for i, hist_cmd in enumerate(command_history[-50:], 1):
                history_lines.append(f"  {i}  {hist_cmd}")

            response_text = "\n".join(history_lines) if history_lines else ""

            if ENHANCEMENTS_ENABLED:
                try:
                    self._log_to_analytics(
                        session_id,
                        cmd,
                        intent,
                        current_dir,
                        "[history displayed]",
                        0.01,
                        True,
                    )
                except Exception:
                    pass

            return {"response": response_text, "delay": 0.01}

        # Handle echo command
        if intent == "echo":
            parts = cmd.split(maxsplit=1)
            response_text = parts[1] if len(parts) > 1 else ""
            return {"response": response_text, "delay": 0.01}

        # Handle env/printenv command
        if intent == "show_env":
            env_vars = {
                "USER": "shophub",
                "HOME": "/home/shophub",
                "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin",
                "SHELL": "/bin/bash",
                "PWD": current_dir.replace("~", "/home/shophub"),
                "LANG": "en_US.UTF-8",
                "NODE_ENV": "production",
                "PORT": "3000",
            }
            response_text = "\n".join([f"{k}={v}" for k, v in env_vars.items()])

            if ENHANCEMENTS_ENABLED:
                try:
                    self._log_to_analytics(
                        session_id,
                        cmd,
                        intent,
                        current_dir,
                        "[env displayed]",
                        0.01,
                        True,
                    )
                except Exception:
                    pass

            return {"response": response_text, "delay": 0.01}

        # Handle commands with missing arguments
        if intent == "read_file_no_arg":
            error_msg = f"{cmd.split()[0]}: missing operand\nTry '{cmd.split()[0]} --help' for more information."
            return {"response": error_msg, "delay": 0.01}

        if intent == "grep_no_arg":
            error_msg = (
                "grep: missing pattern\nUsage: grep [OPTION]... PATTERN [FILE]..."
            )
            return {"response": error_msg, "delay": 0.01}

        # Handle read_file intent
        filename_hint = None
        if intent == "read_file":
            parts = cmd.split()
            file_parts = [p for p in parts[1:] if not p.startswith("-")]

            if file_parts:
                filename_hint = file_parts[0].strip()

                # ENHANCEMENT: Check dynamic filesystem first
                if ENHANCEMENTS_ENABLED:
                    try:
                        file_path = f"{current_dir}/{filename_hint}"
                        dynamic_content = self.dynamic_fs.get_file_content(file_path)

                        if dynamic_content:
                            await self.cache.set(cache_key, dynamic_content)
                            self._log_to_analytics(
                                session_id,
                                cmd,
                                intent,
                                current_dir,
                                dynamic_content,
                                0.05,
                                True,
                            )

                            meta["discovered_files"].append(filename_hint)
                            self.prompt_generator.update_discovered_files(
                                session_id, filename_hint
                            )

                            return {"response": dynamic_content, "delay": 0.05}
                    except Exception:
                        pass

                # Check predefined FILE_CONTENTS
                matched_path = self._find_file_case_insensitive(
                    current_dir, filename_hint
                )
                if matched_path:
                    content = FILE_CONTENTS[matched_path]

                    if ENHANCEMENTS_ENABLED:
                        try:
                            await self.cache.set(cache_key, content)
                            self._log_to_analytics(
                                session_id,
                                cmd,
                                intent,
                                current_dir,
                                content,
                                0.05,
                                True,
                            )
                            meta["discovered_files"].append(filename_hint)
                            self.prompt_generator.update_discovered_files(
                                session_id, filename_hint
                            )
                        except Exception:
                            pass

                    return {"response": content, "delay": 0.05}

                # File doesn't exist
                if not self._file_exists_in_directory(current_dir, filename_hint):
                    error_msg = f"cat: {filename_hint}: No such file or directory"

                    if ENHANCEMENTS_ENABLED:
                        try:
                            self._log_to_analytics(
                                session_id,
                                cmd,
                                intent,
                                current_dir,
                                error_msg,
                                0.02,
                                False,
                            )
                        except Exception:
                            pass

                    return {"response": error_msg, "delay": 0.02}

        # Try simulated responses
        try:
            if intent == "list_dir":
                response_text = self._simulate_list_dir(dir_context, cmd)

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        await self.cache.prefetch(
                            session_id, cmd, current_dir, ["cat", "cd", "pwd"]
                        )
                    except Exception:
                        pass

                delay = 0.02 + random.random() * 0.15

                if ENHANCEMENTS_ENABLED:
                    try:
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

            if intent == "identity":
                response_text = self._simulate_identity()
                delay = 0.01

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

            if intent == "system_info":
                response_text = self._simulate_system_info(cmd)
                delay = 0.02

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

            if intent == "process_list":
                response_text = self._simulate_process_list()
                delay = 0.03

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

            if intent == "network_probe":
                response_text = self._simulate_ping(cmd)
                delay = 0.05

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

            if intent == "http_fetch":
                response_text = self._simulate_http_fetch(cmd)
                delay = 0.05 + random.random() * 0.2

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

            if intent == "docker":
                response_text = self._simulate_docker(cmd)
                delay = 0.04

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

            if intent == "git":
                response_text = self._simulate_git(cmd, dir_context)
                delay = 0.03

                if ENHANCEMENTS_ENABLED:
                    try:
                        await self.cache.set(cache_key, response_text)
                        self._log_to_analytics(
                            session_id,
                            cmd,
                            intent,
                            current_dir,
                            response_text,
                            delay,
                            True,
                        )
                    except Exception:
                        pass

                return {"response": response_text, "delay": delay}

        except Exception as e:
            print(f"[Controller] Simulation error: {e}")

        # Fallback to LLM
        context = {
            "current_directory": current_dir,
            "directory_description": dir_context.get("description", ""),
            "directory_contents": dir_context.get("contents", []),
            "application": "ShopHub E-commerce Platform",
            "application_tech": "Node.js, Express, MongoDB, Redis, Docker",
        }

        # ENHANCEMENT: Use enhanced prompt if available
        if ENHANCEMENTS_ENABLED:
            try:
                attacker_profile = self.adaptive_system.analyze_attacker_behavior(
                    session_id, command_history
                )
                discovered_files = meta.get("discovered_files", [])

                enhanced_prompt = self.prompt_generator.build_contextual_prompt(
                    session_id=session_id,
                    command=cmd,
                    current_dir=current_dir,
                    intent=intent,
                    attacker_profile=attacker_profile,
                    discovered_files=discovered_files,
                )
                context["enhanced_prompt"] = enhanced_prompt
            except Exception:
                pass

        try:
            response_text = await llm_gen.generate_response_for_command_async(
                command=cmd,
                filename_hint=filename_hint,
                persona=self.persona,
                context=context,
            )
        except Exception as e:
            print(f"[Controller] LLM error: {e}")
            response_text = (
                f"bash: {cmd.split()[0] if cmd else 'unknown'}: command not found"
            )

        # ENHANCEMENT: Apply adaptive response and cache
        if ENHANCEMENTS_ENABLED:
            try:
                await self.cache.set(cache_key, response_text)

                adaptive_result = self.adaptive_system.get_adaptive_response(
                    session_id, cmd, response_text, command_history
                )

                await self.cache.prefetch(
                    session_id, cmd, current_dir, ["ls", "pwd", "cat"]
                )

                self._log_to_analytics(
                    session_id,
                    cmd,
                    intent,
                    current_dir,
                    adaptive_result["response"],
                    adaptive_result["delay"],
                    True,
                )

                return {
                    "response": adaptive_result["response"],
                    "delay": adaptive_result["delay"],
                }
            except Exception:
                pass

        # Fallback: basic response
        base_delay = 0.05
        delay = base_delay + float(np.random.rand()) * 0.2

        return {"response": response_text, "delay": delay}

    def _log_to_analytics(
        self,
        session_id: str,
        command: str,
        intent: str,
        current_dir: str,
        response: str,
        delay: float,
        success: bool,
    ):
        """Log command to analytics system"""
        if not ENHANCEMENTS_ENABLED:
            return

        try:
            event = CommandEvent(
                session_id=session_id,
                timestamp=datetime.now(),
                command=command,
                intent=intent,
                current_dir=current_dir,
                response_preview=response[:400],
                delay=delay,
                success=success,
            )
            self.analytics.log_command(event)
        except Exception as e:
            print(f"[Controller] Analytics logging error: {e}")

    async def _background_cache_cleanup(self):
        """Background task to clean up expired cache entries"""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                self.cache.cleanup_expired()
                stats = self.cache.get_stats()
                print(f"[Controller] 🧹 Cache cleanup: {stats['hit_rate']} hit rate")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Controller] Cache cleanup error: {e}")

    async def _background_fs_evolution(self):
        """Background task to evolve filesystem"""
        while True:
            try:
                await asyncio.sleep(600)  # Every 10 minutes

                for session_id, meta in self.sessions.items():
                    commands = meta.get("command_history", [])
                    if commands:
                        self.dynamic_fs.evolve_filesystem(session_id, commands)

                print("[Controller] 🌱 Filesystem evolved")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Controller] Filesystem evolution error: {e}")

    def get_analytics_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get analytics report"""
        if ENHANCEMENTS_ENABLED:
            return self.analytics.generate_report(hours)
        return {}

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if ENHANCEMENTS_ENABLED:
            return self.cache.get_stats()
        return {}

    def end_session(self, session_id: str):
        """End a session and finalize analytics"""
        if session_id in self.sessions:
            if ENHANCEMENTS_ENABLED:
                try:
                    profile = self.adaptive_system.get_attacker_profile(session_id)
                    self.analytics.end_session(session_id, profile)
                except Exception:
                    pass

            del self.sessions[session_id]

    # Simulation helper methods
    def _simulate_list_dir(self, dir_context: Dict[str, Any], cmd: str) -> str:
        contents = dir_context.get("contents", [])
        if not contents:
            return ""

        show_hidden = "-a" in cmd or "-la" in cmd or "-al" in cmd
        lines = []

        if show_hidden:
            lines.append("drwxr-xr-x  2 shophub shophub 4096 .")
            lines.append("drwxr-xr-x  2 shophub shophub 4096 ..")

        for name in contents:
            if name.endswith("/"):
                lines.append(f"drwxr-xr-x  2 shophub shophub 4096 {name}")
            elif "." in name:
                lines.append(
                    f"-rw-r--r--  1 shophub shophub {random.randint(20, 4000)} {name}"
                )
            else:
                lines.append(f"drwxr-xr-x  2 shophub shophub 4096 {name}")
        return "\n".join(lines)

    def _simulate_identity(self) -> str:
        return "shophub"

    def _simulate_system_info(self, cmd: str) -> str:
        if cmd.startswith("uname"):
            return "Linux shophub-server 5.15.0-100-generic #1 SMP Thu Jan 1 00:00:00 UTC 2025 x86_64 GNU/Linux"
        if cmd.startswith("hostname"):
            return "shophub-server"
        return "Unknown system info query"

    def _simulate_process_list(self) -> str:
        sample = [
            "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND",
            "root         1  0.0  0.1 169084  6044 ?        Ss   09:30   0:01 /sbin/init",
            "shophub   1023  0.3  1.2 238564 25432 ?        Sl   09:31   0:12 node /home/shophub/shophub/app/app.js",
            "redis     2048  0.1  0.8  84900 16844 ?        Ssl  09:31   0:03 redis-server *:6379",
            "mongodb   3120  1.2  2.5 452128 51200 ?        Ssl  09:31   0:45 /usr/bin/mongod --config /etc/mongod.conf",
        ]
        return "\n".join(sample)

    def _simulate_ping(self, cmd: str) -> str:
        parts = cmd.split()
        target = parts[1] if len(parts) > 1 else "127.0.0.1"
        rtts = [round(random.uniform(0.3, 3.0), 3) for _ in range(4)]
        lines = [f"PING {target} ({target}): 56 data bytes"]
        for i, r in enumerate(rtts, 1):
            lines.append(f"64 bytes from {target}: icmp_seq={i} ttl=64 time={r} ms")
        avg = round(sum(rtts) / len(rtts), 3)
        lines.append("")
        lines.append(f"--- {target} ping statistics ---")
        lines.append("4 packets transmitted, 4 packets received, 0.0% packet loss")
        lines.append(f"round-trip min/avg/max = {min(rtts)}/{avg}/{max(rtts)} ms")
        return "\n".join(lines)

    def _simulate_http_fetch(self, cmd: str) -> str:
        if "http" in cmd:
            return "HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\n\n<html><head><title>ShopHub</title></head><body><h1>ShopHub</h1></body></html>"
        return "wget: missing URL"

    def _simulate_docker(self, cmd: str) -> str:
        if "ps" in cmd or "container ls" in cmd:
            return (
                "CONTAINER ID   IMAGE          COMMAND                  CREATED        STATUS        PORTS                    NAMES\n"
                'a1b2c3d4e5f6   shophub:latest  "node /app/app.js"      2 hours ago    Up 2 hours    0.0.0.0:3000->3000/tcp   shophub_app\n'
                'd7e8f9a0b1c2   mongo:6.0       "docker-entrypoint.s…" 3 hours ago    Up 3 hours    27017/tcp                shophub_mongo\n'
            )
        if "images" in cmd:
            return "REPOSITORY   TAG       IMAGE ID       CREATED       SIZE\nshophub       latest    abcdef012345   2 hours ago   200MB\nmongo         6.0       123456abcdef   3 weeks ago   350MB"
        return "docker: unknown command or not implemented in honeypot simulation"

    def _simulate_git(self, cmd: str, dir_context: Dict[str, Any]) -> str:
        contents = dir_context.get("contents", [])
        if ".git" in contents:
            if cmd.strip() == "git status":
                return "On branch main\nYour branch is up to date with 'origin/main'.\n\nnothing to commit, working tree clean"
            return f"git: simulated output for '{cmd}'"
        return "fatal: not a git repository (or any of the parent directories): .git"
