DATABASES = {
    "information_schema": {
        "tables": {
            "schemata": {
                "columns": ["SCHEMA_NAME", "DEFAULT_CHARACTER_SET_NAME"],
                "rows": [
                    ["information_schema", "utf8"],
                    ["mysql", "utf8"],
                    ["shophub", "utf8mb4"],
                    ["shophub_logs", "utf8mb4"],
                ],
            },
            "tables": {
                "columns": ["TABLE_SCHEMA", "TABLE_NAME", "TABLE_TYPE"],
                "rows": [
                    ["shophub", "users", "BASE TABLE"],
                    ["shophub", "products", "BASE TABLE"],
                    ["shophub", "categories", "BASE TABLE"],
                    ["shophub", "orders", "BASE TABLE"],
                    ["shophub", "order_items", "BASE TABLE"],
                    ["shophub", "cart", "BASE TABLE"],
                    ["shophub", "payments", "BASE TABLE"],
                    ["shophub", "reviews", "BASE TABLE"],
                    ["shophub", "addresses", "BASE TABLE"],
                    ["shophub", "admin_users", "BASE TABLE"],
                ],
            },
        }
    },
    "mysql": {
        "tables": {
            "user": {
                "columns": ["Host", "User", "authentication_string"],
                "rows": [
                    ["localhost", "root", "*[REDACTED]"],
                    ["localhost", "shophub_app", "*[REDACTED]"],
                ],
            }
        }
    },
    "shophub": {
        "tables": {
            "users": {
                "columns": [
                    "id",
                    "email",
                    "password_hash",
                    "first_name",
                    "last_name",
                    "created_at",
                    "last_login",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["email", "varchar(100)", "NO", "UNI", None, ""],
                    ["password_hash", "varchar(255)", "NO", "", None, ""],
                    ["first_name", "varchar(50)", "YES", "", None, ""],
                    ["last_name", "varchar(50)", "YES", "", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                    ["last_login", "timestamp", "YES", "", None, ""],
                ],
                "rows": [],
            },
            "categories": {
                "columns": [
                    "id",
                    "name",
                    "slug",
                    "description",
                    "parent_id",
                    "created_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["name", "varchar(100)", "NO", "", None, ""],
                    ["slug", "varchar(100)", "NO", "UNI", None, ""],
                    ["description", "text", "YES", "", None, ""],
                    ["parent_id", "int", "YES", "MUL", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "products": {
                "columns": [
                    "id",
                    "name",
                    "slug",
                    "category_id",
                    "price",
                    "stock",
                    "description",
                    "image_url",
                    "created_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["name", "varchar(200)", "NO", "", None, ""],
                    ["slug", "varchar(200)", "NO", "UNI", None, ""],
                    ["category_id", "int", "YES", "MUL", None, ""],
                    ["price", "decimal(10,2)", "NO", "", None, ""],
                    ["stock", "int", "NO", "", "0", ""],
                    ["description", "text", "YES", "", None, ""],
                    ["image_url", "varchar(255)", "YES", "", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "orders": {
                "columns": [
                    "id",
                    "user_id",
                    "total_amount",
                    "status",
                    "payment_status",
                    "shipping_address_id",
                    "created_at",
                    "updated_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["user_id", "int", "NO", "MUL", None, ""],
                    ["total_amount", "decimal(10,2)", "NO", "", None, ""],
                    ["status", "varchar(50)", "NO", "", "pending", ""],
                    ["payment_status", "varchar(50)", "NO", "", "pending", ""],
                    ["shipping_address_id", "int", "YES", "MUL", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                    [
                        "updated_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED on update CURRENT_TIMESTAMP",
                    ],
                ],
                "rows": [],
            },
            "order_items": {
                "columns": [
                    "id",
                    "order_id",
                    "product_id",
                    "quantity",
                    "price",
                    "created_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["order_id", "int", "NO", "MUL", None, ""],
                    ["product_id", "int", "NO", "MUL", None, ""],
                    ["quantity", "int", "NO", "", "1", ""],
                    ["price", "decimal(10,2)", "NO", "", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "cart": {
                "columns": [
                    "id",
                    "user_id",
                    "product_id",
                    "quantity",
                    "added_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["user_id", "int", "NO", "MUL", None, ""],
                    ["product_id", "int", "NO", "MUL", None, ""],
                    ["quantity", "int", "NO", "", "1", ""],
                    [
                        "added_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "payments": {
                "columns": [
                    "id",
                    "order_id",
                    "amount",
                    "payment_method",
                    "transaction_id",
                    "status",
                    "created_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["order_id", "int", "NO", "MUL", None, ""],
                    ["amount", "decimal(10,2)", "NO", "", None, ""],
                    ["payment_method", "varchar(50)", "NO", "", None, ""],
                    ["transaction_id", "varchar(100)", "NO", "UNI", None, ""],
                    ["status", "varchar(50)", "NO", "", "pending", ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "reviews": {
                "columns": [
                    "id",
                    "product_id",
                    "user_id",
                    "rating",
                    "title",
                    "comment",
                    "created_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["product_id", "int", "NO", "MUL", None, ""],
                    ["user_id", "int", "NO", "MUL", None, ""],
                    ["rating", "int", "NO", "", None, ""],
                    ["title", "varchar(200)", "YES", "", None, ""],
                    ["comment", "text", "YES", "", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "addresses": {
                "columns": [
                    "id",
                    "user_id",
                    "type",
                    "street",
                    "city",
                    "state",
                    "zip_code",
                    "country",
                    "created_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["user_id", "int", "NO", "MUL", None, ""],
                    ["type", "varchar(20)", "NO", "", "shipping", ""],
                    ["street", "varchar(200)", "NO", "", None, ""],
                    ["city", "varchar(100)", "NO", "", None, ""],
                    ["state", "varchar(100)", "NO", "", None, ""],
                    ["zip_code", "varchar(20)", "NO", "", None, ""],
                    ["country", "varchar(100)", "NO", "", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "admin_users": {
                "columns": [
                    "id",
                    "username",
                    "password_hash",
                    "email",
                    "role",
                    "last_login",
                    "created_at",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["username", "varchar(50)", "NO", "UNI", None, ""],
                    ["password_hash", "varchar(255)", "NO", "", None, ""],
                    ["email", "varchar(100)", "NO", "UNI", None, ""],
                    ["role", "varchar(50)", "NO", "", "viewer", ""],
                    ["last_login", "timestamp", "YES", "", None, ""],
                    [
                        "created_at",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
        }
    },
    "shophub_logs": {
        "tables": {
            "access_logs": {
                "columns": [
                    "id",
                    "user_id",
                    "ip_address",
                    "action",
                    "endpoint",
                    "timestamp",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["user_id", "int", "YES", "MUL", None, ""],
                    ["ip_address", "varchar(45)", "NO", "", None, ""],
                    ["action", "varchar(100)", "NO", "", None, ""],
                    ["endpoint", "varchar(255)", "NO", "", None, ""],
                    [
                        "timestamp",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
            "error_logs": {
                "columns": [
                    "id",
                    "error_type",
                    "message",
                    "stack_trace",
                    "timestamp",
                ],
                "column_defs": [
                    ["id", "int", "NO", "PRI", None, "auto_increment"],
                    ["error_type", "varchar(100)", "NO", "", None, ""],
                    ["message", "text", "NO", "", None, ""],
                    ["stack_trace", "text", "YES", "", None, ""],
                    [
                        "timestamp",
                        "timestamp",
                        "NO",
                        "",
                        "CURRENT_TIMESTAMP",
                        "DEFAULT_GENERATED",
                    ],
                ],
                "rows": [],
            },
        }
    },
}

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

PAGES = {
    "/": {
        "title": "ShopHub - Your Online Shopping Destination",
        "type": "home",
        "exists": True,
    },
    "/index.html": {
        "title": "ShopHub - Your Online Shopping Destination",
        "type": "home",
        "exists": True,
    },
    "/products": {
        "title": "All Products - ShopHub",
        "type": "product_listing",
        "exists": True,
    },
    "/products/electronics": {
        "title": "Electronics - ShopHub",
        "type": "category",
        "exists": True,
    },
    "/products/clothing": {
        "title": "Clothing - ShopHub",
        "type": "category",
        "exists": True,
    },
    "/products/home": {
        "title": "Home & Garden - ShopHub",
        "type": "category",
        "exists": True,
    },
    "/cart": {
        "title": "Shopping Cart - ShopHub",
        "type": "cart",
        "exists": True,
    },
    "/checkout": {
        "title": "Checkout - ShopHub",
        "type": "checkout",
        "exists": True,
    },
    "/login": {"title": "Login - ShopHub", "type": "auth", "exists": True},
    "/register": {
        "title": "Register - ShopHub",
        "type": "auth",
        "exists": True,
    },
    "/account": {
        "title": "My Account - ShopHub",
        "type": "account",
        "exists": True,
    },
    "/orders": {
        "title": "My Orders - ShopHub",
        "type": "orders",
        "exists": True,
    },
    "/admin": {
        "title": "Admin Panel - ShopHub",
        "type": "admin",
        "exists": True,
    },
    "/admin/login": {
        "title": "Admin Login - ShopHub",
        "type": "admin",
        "exists": True,
    },
    "/admin/dashboard": {
        "title": "Admin Dashboard - ShopHub",
        "type": "admin",
        "exists": True,
    },
    "/about": {"title": "About Us - ShopHub", "type": "static", "exists": True},
    "/contact": {
        "title": "Contact Us - ShopHub",
        "type": "static",
        "exists": True,
    },
    "/help": {
        "title": "Help Center - ShopHub",
        "type": "static",
        "exists": True,
    },
    "/robots.txt": {"type": "static", "exists": True},
    "/sitemap.xml": {"type": "static", "exists": True},
}

PRODUCTS = {
    "1": {
        "id": 1,
        "name": "Allen Solly Cotton Shirt",
        "price": 2354,
        "category": "clothing",
    },
    "2": {
        "id": 2,
        "name": "Sleepwell Memory Foam Mattress Black",
        "price": 12051,
        "category": "home",
    },
    "3": {
        "id": 3,
        "name": "Fitbit Charge 6",
        "price": 148662,
        "category": "electronics",
    },
    "4": {
        "id": 4,
        "name": "Prestige Pressure Cooker",
        "price": 14432,
        "category": "kitchen",
    },
    "5": {
        "id": 5,
        "name": "Logitech G Pro X Keyboard Pro Edition",
        "price": 20512,
        "category": "gaming",
    },
    "6": {
        "id": 6,
        "name": "Levi's 511 Slim Fit Jeans Black",
        "price": 2694,
        "category": "clothing",
    },
    "7": {
        "id": 7,
        "name": "Samsung Galaxy Book 3 Black",
        "price": 14893,
        "category": "electronics",
    },
    "8": {"id": 8, "name": "Xbox Series X", "price": 27675, "category": "gaming"},
    "9": {
        "id": 9,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 50565,
        "category": "home",
    },
    "10": {
        "id": 10,
        "name": "Zara Slim Fit Blazer 2024 Model",
        "price": 1483,
        "category": "clothing",
    },
    "11": {
        "id": 11,
        "name": "Puma Running Shoes Blue",
        "price": 2316,
        "category": "clothing",
    },
    "12": {
        "id": 12,
        "name": "Xiaomi Redmi Note 12 Pro Blue",
        "price": 83334,
        "category": "electronics",
    },
    "13": {
        "id": 13,
        "name": "Acer Aspire 7 2024 Model",
        "price": 98502,
        "category": "electronics",
    },
    "14": {
        "id": 14,
        "name": "Levi's 511 Slim Fit Jeans Black",
        "price": 1127,
        "category": "clothing",
    },
    "15": {
        "id": 15,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 4917,
        "category": "kitchen",
    },
    "16": {
        "id": 16,
        "name": "Sony PlayStation 5 Black",
        "price": 19796,
        "category": "gaming",
    },
    "17": {
        "id": 17,
        "name": "AmazonBasics Wall Clock 2024 Model",
        "price": 21647,
        "category": "home",
    },
    "18": {
        "id": 18,
        "name": "Puma Running Shoes Silver",
        "price": 7647,
        "category": "clothing",
    },
    "19": {
        "id": 19,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 2478,
        "category": "kitchen",
    },
    "20": {
        "id": 20,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 33985,
        "category": "home",
    },
    "21": {
        "id": 21,
        "name": "Razer DeathAdder V3 Mouse Blue",
        "price": 46235,
        "category": "gaming",
    },
    "22": {
        "id": 22,
        "name": "Apple AirPods Pro 2 Silver",
        "price": 7482,
        "category": "electronics",
    },
    "23": {
        "id": 23,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 23962,
        "category": "home",
    },
    "24": {
        "id": 24,
        "name": "AmazonBasics Wall Clock 2024 Model",
        "price": 33849,
        "category": "home",
    },
    "25": {
        "id": 25,
        "name": "H&M Oversized Hoodie Pro Edition",
        "price": 3442,
        "category": "clothing",
    },
    "26": {
        "id": 26,
        "name": "Prestige Pressure Cooker",
        "price": 5721,
        "category": "kitchen",
    },
    "27": {
        "id": 27,
        "name": "Ikea Study Table LINNMON Blue",
        "price": 53899,
        "category": "home",
    },
    "28": {
        "id": 28,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 24207,
        "category": "gaming",
    },
    "29": {
        "id": 29,
        "name": "Nintendo Switch OLED",
        "price": 12120,
        "category": "gaming",
    },
    "30": {
        "id": 30,
        "name": "Nike Air Max Shoes 2024 Model",
        "price": 616,
        "category": "clothing",
    },
    "31": {
        "id": 31,
        "name": "Adidas Supercourt Sneakers Blue",
        "price": 7803,
        "category": "clothing",
    },
    "32": {
        "id": 32,
        "name": "Dell XPS 13 Black",
        "price": 91197,
        "category": "electronics",
    },
    "33": {
        "id": 33,
        "name": "Nintendo Switch OLED Blue",
        "price": 15263,
        "category": "gaming",
    },
    "34": {
        "id": 34,
        "name": "Logitech G Pro X Keyboard",
        "price": 47331,
        "category": "gaming",
    },
    "35": {
        "id": 35,
        "name": "Zara Slim Fit Blazer",
        "price": 3068,
        "category": "clothing",
    },
    "36": {
        "id": 36,
        "name": "Noise ColorFit Ultra Silver",
        "price": 8627,
        "category": "electronics",
    },
    "37": {
        "id": 37,
        "name": "Sleepwell Memory Foam Mattress Black",
        "price": 51009,
        "category": "home",
    },
    "38": {
        "id": 38,
        "name": "Nintendo Switch OLED 2024 Model",
        "price": 38162,
        "category": "gaming",
    },
    "39": {
        "id": 39,
        "name": "Logitech G Pro X Keyboard Black",
        "price": 43722,
        "category": "gaming",
    },
    "40": {
        "id": 40,
        "name": 'Samsung Neo QLED 55" Blue',
        "price": 74347,
        "category": "electronics",
    },
    "41": {
        "id": 41,
        "name": "Sony PlayStation 5 Blue",
        "price": 19435,
        "category": "gaming",
    },
    "42": {
        "id": 42,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 19390,
        "category": "home",
    },
    "43": {
        "id": 43,
        "name": "Nike Air Max Shoes Pro Edition",
        "price": 4896,
        "category": "clothing",
    },
    "44": {
        "id": 44,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 2867,
        "category": "gaming",
    },
    "45": {
        "id": 45,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 3293,
        "category": "kitchen",
    },
    "46": {
        "id": 46,
        "name": "Philips LED Desk Lamp 2024 Model",
        "price": 55640,
        "category": "home",
    },
    "47": {
        "id": 47,
        "name": "Zara Slim Fit Blazer Black",
        "price": 3464,
        "category": "clothing",
    },
    "48": {
        "id": 48,
        "name": "Bosch Mixer Grinder Black",
        "price": 17285,
        "category": "kitchen",
    },
    "49": {
        "id": 49,
        "name": "HyperX Cloud II Gaming Headset",
        "price": 7081,
        "category": "gaming",
    },
    "50": {
        "id": 50,
        "name": "AmazonBasics Wall Clock 2024 Model",
        "price": 37006,
        "category": "home",
    },
    "51": {
        "id": 51,
        "name": "Sony Bravia X80K Pro Edition",
        "price": 11555,
        "category": "electronics",
    },
    "52": {
        "id": 52,
        "name": "Milton Thermosteel Bottle 1L Black",
        "price": 12380,
        "category": "kitchen",
    },
    "53": {
        "id": 53,
        "name": "Nintendo Switch OLED Black",
        "price": 5131,
        "category": "gaming",
    },
    "54": {
        "id": 54,
        "name": "Allen Solly Cotton Shirt 2024 Model",
        "price": 2323,
        "category": "clothing",
    },
    "55": {
        "id": 55,
        "name": "Sleepwell Memory Foam Mattress Pro Edition",
        "price": 58904,
        "category": "home",
    },
    "56": {
        "id": 56,
        "name": "Xbox Series X 2024 Model",
        "price": 55321,
        "category": "gaming",
    },
    "57": {
        "id": 57,
        "name": "Puma Running Shoes Pro Edition",
        "price": 7343,
        "category": "clothing",
    },
    "58": {
        "id": 58,
        "name": "Nike Air Max Shoes Silver",
        "price": 4767,
        "category": "clothing",
    },
    "59": {
        "id": 59,
        "name": "Marshall Emberton Blue",
        "price": 119343,
        "category": "electronics",
    },
    "60": {
        "id": 60,
        "name": "Puma Running Shoes Blue",
        "price": 5289,
        "category": "clothing",
    },
    "61": {
        "id": 61,
        "name": "Adidas Supercourt Sneakers 2024 Model",
        "price": 2238,
        "category": "clothing",
    },
    "62": {
        "id": 62,
        "name": "Nike Air Max Shoes Pro Edition",
        "price": 7234,
        "category": "clothing",
    },
    "63": {
        "id": 63,
        "name": "Allen Solly Cotton Shirt Silver",
        "price": 7133,
        "category": "clothing",
    },
    "64": {
        "id": 64,
        "name": "Nike Air Max Shoes Silver",
        "price": 4022,
        "category": "clothing",
    },
    "65": {
        "id": 65,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 14179,
        "category": "home",
    },
    "66": {
        "id": 66,
        "name": "Philips LED Desk Lamp Silver",
        "price": 29946,
        "category": "home",
    },
    "67": {
        "id": 67,
        "name": "Philips LED Desk Lamp Silver",
        "price": 51877,
        "category": "home",
    },
    "68": {
        "id": 68,
        "name": "Logitech G Pro X Keyboard Pro Edition",
        "price": 50353,
        "category": "gaming",
    },
    "69": {
        "id": 69,
        "name": "Dyson V12 Vacuum Cleaner Blue",
        "price": 52376,
        "category": "home",
    },
    "70": {
        "id": 70,
        "name": "Apple iPhone 15 Pro 2024 Model",
        "price": 90441,
        "category": "electronics",
    },
    "71": {
        "id": 71,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 59993,
        "category": "home",
    },
    "72": {
        "id": 72,
        "name": "Puma Running Shoes Pro Edition",
        "price": 1498,
        "category": "clothing",
    },
    "73": {
        "id": 73,
        "name": "TCL Mini LED TV Black",
        "price": 36987,
        "category": "electronics",
    },
    "74": {
        "id": 74,
        "name": "Havells Toaster Blue",
        "price": 17829,
        "category": "kitchen",
    },
    "75": {
        "id": 75,
        "name": "Xbox Series X 2024 Model",
        "price": 19479,
        "category": "gaming",
    },
    "76": {
        "id": 76,
        "name": "Prestige Pressure Cooker Black",
        "price": 6506,
        "category": "kitchen",
    },
    "77": {
        "id": 77,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 19571,
        "category": "home",
    },
    "78": {
        "id": 78,
        "name": "H&M Oversized Hoodie Black",
        "price": 3135,
        "category": "clothing",
    },
    "79": {
        "id": 79,
        "name": "Apple AirPods Pro 2 Blue",
        "price": 20471,
        "category": "electronics",
    },
    "80": {
        "id": 80,
        "name": "HyperX Cloud II Gaming Headset Blue",
        "price": 37931,
        "category": "gaming",
    },
    "81": {
        "id": 81,
        "name": "Nothing Phone 2 Silver",
        "price": 156726,
        "category": "electronics",
    },
    "82": {
        "id": 82,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 9533,
        "category": "gaming",
    },
    "83": {
        "id": 83,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 5689,
        "category": "kitchen",
    },
    "84": {
        "id": 84,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 17965,
        "category": "home",
    },
    "85": {
        "id": 85,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 31510,
        "category": "home",
    },
    "86": {
        "id": 86,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 3170,
        "category": "kitchen",
    },
    "87": {
        "id": 87,
        "name": "MacBook Pro 14-inch M3 2024 Model",
        "price": 119707,
        "category": "electronics",
    },
    "88": {
        "id": 88,
        "name": "Sleepwell Memory Foam Mattress Blue",
        "price": 19124,
        "category": "home",
    },
    "89": {
        "id": 89,
        "name": "Zara Slim Fit Blazer Black",
        "price": 5399,
        "category": "clothing",
    },
    "90": {
        "id": 90,
        "name": "Nothing Phone 2",
        "price": 140908,
        "category": "electronics",
    },
    "91": {
        "id": 91,
        "name": "Sony PlayStation 5",
        "price": 48013,
        "category": "gaming",
    },
    "92": {
        "id": 92,
        "name": "Bosch Mixer Grinder Silver",
        "price": 17006,
        "category": "kitchen",
    },
    "93": {
        "id": 93,
        "name": "Bosch Mixer Grinder",
        "price": 644,
        "category": "kitchen",
    },
    "94": {
        "id": 94,
        "name": "Apple Watch Series 9",
        "price": 99104,
        "category": "electronics",
    },
    "95": {
        "id": 95,
        "name": "JBL Flip 6 2024 Model",
        "price": 126269,
        "category": "electronics",
    },
    "96": {
        "id": 96,
        "name": "Sleepwell Memory Foam Mattress Black",
        "price": 1501,
        "category": "home",
    },
    "97": {
        "id": 97,
        "name": "Dell XPS 13 Black",
        "price": 12336,
        "category": "electronics",
    },
    "98": {
        "id": 98,
        "name": "Puma Running Shoes Black",
        "price": 2445,
        "category": "clothing",
    },
    "99": {
        "id": 99,
        "name": "H&M Oversized Hoodie Silver",
        "price": 2229,
        "category": "clothing",
    },
    "100": {
        "id": 100,
        "name": "Philips Airfryer XL Blue",
        "price": 1610,
        "category": "kitchen",
    },
    "101": {
        "id": 101,
        "name": "Prestige Pressure Cooker 2024 Model",
        "price": 522,
        "category": "kitchen",
    },
    "102": {
        "id": 102,
        "name": "Sleepwell Memory Foam Mattress Black",
        "price": 20332,
        "category": "home",
    },
    "103": {
        "id": 103,
        "name": "Allen Solly Cotton Shirt Pro Edition",
        "price": 2662,
        "category": "clothing",
    },
    "104": {
        "id": 104,
        "name": "Levi's 511 Slim Fit Jeans 2024 Model",
        "price": 4063,
        "category": "clothing",
    },
    "105": {
        "id": 105,
        "name": "Bosch Mixer Grinder Silver",
        "price": 18216,
        "category": "kitchen",
    },
    "106": {
        "id": 106,
        "name": "H&M Oversized Hoodie 2024 Model",
        "price": 3450,
        "category": "clothing",
    },
    "107": {
        "id": 107,
        "name": "Amazon Echo Dot 5th Gen",
        "price": 65479,
        "category": "electronics",
    },
    "108": {
        "id": 108,
        "name": "AmazonBasics Wall Clock",
        "price": 31380,
        "category": "home",
    },
    "109": {
        "id": 109,
        "name": "Sony PlayStation 5 2024 Model",
        "price": 51023,
        "category": "gaming",
    },
    "110": {
        "id": 110,
        "name": "Sony Bravia X80K Pro Edition",
        "price": 112752,
        "category": "electronics",
    },
    "111": {
        "id": 111,
        "name": "Puma Running Shoes 2024 Model",
        "price": 6389,
        "category": "clothing",
    },
    "112": {
        "id": 112,
        "name": "Philips Airfryer XL Silver",
        "price": 6376,
        "category": "kitchen",
    },
    "113": {
        "id": 113,
        "name": "Samsung Galaxy Watch 6 Blue",
        "price": 113391,
        "category": "electronics",
    },
    "114": {
        "id": 114,
        "name": "Prestige Pressure Cooker Blue",
        "price": 4500,
        "category": "kitchen",
    },
    "115": {
        "id": 115,
        "name": "Xbox Series X Pro Edition",
        "price": 14748,
        "category": "gaming",
    },
    "116": {
        "id": 116,
        "name": "Nintendo Switch OLED",
        "price": 63828,
        "category": "gaming",
    },
    "117": {
        "id": 117,
        "name": "Prestige Pressure Cooker",
        "price": 5575,
        "category": "kitchen",
    },
    "118": {
        "id": 118,
        "name": "Xbox Series X Black",
        "price": 32249,
        "category": "gaming",
    },
    "119": {
        "id": 119,
        "name": "Acer Aspire 7 2024 Model",
        "price": 41193,
        "category": "electronics",
    },
    "120": {
        "id": 120,
        "name": "Philips LED Desk Lamp Silver",
        "price": 17080,
        "category": "home",
    },
    "121": {
        "id": 121,
        "name": "Bosch Mixer Grinder",
        "price": 17243,
        "category": "kitchen",
    },
    "122": {
        "id": 122,
        "name": "Marshall Emberton 2024 Model",
        "price": 151692,
        "category": "electronics",
    },
    "123": {
        "id": 123,
        "name": "Havells Toaster Black",
        "price": 12571,
        "category": "kitchen",
    },
    "124": {
        "id": 124,
        "name": "Sony PlayStation 5 Silver",
        "price": 57133,
        "category": "gaming",
    },
    "125": {
        "id": 125,
        "name": "Logitech G Pro X Keyboard Pro Edition",
        "price": 3464,
        "category": "gaming",
    },
    "126": {
        "id": 126,
        "name": "Xbox Series X Black",
        "price": 23016,
        "category": "gaming",
    },
    "127": {
        "id": 127,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 51740,
        "category": "gaming",
    },
    "128": {
        "id": 128,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 68437,
        "category": "gaming",
    },
    "129": {
        "id": 129,
        "name": "Ikea Study Table LINNMON",
        "price": 11497,
        "category": "home",
    },
    "130": {
        "id": 130,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 21166,
        "category": "home",
    },
    "131": {
        "id": 131,
        "name": "Havells Toaster",
        "price": 14689,
        "category": "kitchen",
    },
    "132": {
        "id": 132,
        "name": "Allen Solly Cotton Shirt Blue",
        "price": 6310,
        "category": "clothing",
    },
    "133": {
        "id": 133,
        "name": "Nothing Phone 2 Black",
        "price": 47799,
        "category": "electronics",
    },
    "134": {
        "id": 134,
        "name": "Adidas Supercourt Sneakers Black",
        "price": 2533,
        "category": "clothing",
    },
    "135": {
        "id": 135,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 10819,
        "category": "kitchen",
    },
    "136": {
        "id": 136,
        "name": "Havells Toaster Black",
        "price": 5518,
        "category": "kitchen",
    },
    "137": {
        "id": 137,
        "name": "Xiaomi Smart TV 5A Black",
        "price": 67068,
        "category": "electronics",
    },
    "138": {
        "id": 138,
        "name": "Havells Toaster Black",
        "price": 3891,
        "category": "kitchen",
    },
    "139": {
        "id": 139,
        "name": "Nike Air Max Shoes Pro Edition",
        "price": 5689,
        "category": "clothing",
    },
    "140": {
        "id": 140,
        "name": "Lenovo ThinkPad X1 Carbon Pro Edition",
        "price": 131559,
        "category": "electronics",
    },
    "141": {
        "id": 141,
        "name": "Philips Airfryer XL Black",
        "price": 8558,
        "category": "kitchen",
    },
    "142": {
        "id": 142,
        "name": "Zara Slim Fit Blazer Silver",
        "price": 2651,
        "category": "clothing",
    },
    "143": {
        "id": 143,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 28754,
        "category": "home",
    },
    "144": {
        "id": 144,
        "name": "Boat Rockerz 255 Pro+ Silver",
        "price": 169606,
        "category": "electronics",
    },
    "145": {
        "id": 145,
        "name": "Dyson V12 Vacuum Cleaner Blue",
        "price": 40776,
        "category": "home",
    },
    "146": {
        "id": 146,
        "name": "Philips LED Desk Lamp Black",
        "price": 35509,
        "category": "home",
    },
    "147": {
        "id": 147,
        "name": "Sony SRS-XB13 Silver",
        "price": 125493,
        "category": "electronics",
    },
    "148": {
        "id": 148,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 57929,
        "category": "home",
    },
    "149": {
        "id": 149,
        "name": "Logitech G Pro X Keyboard Pro Edition",
        "price": 9318,
        "category": "gaming",
    },
    "150": {
        "id": 150,
        "name": "Ikea Study Table LINNMON",
        "price": 49844,
        "category": "home",
    },
    "151": {
        "id": 151,
        "name": "Levi's 511 Slim Fit Jeans 2024 Model",
        "price": 7216,
        "category": "clothing",
    },
    "152": {
        "id": 152,
        "name": "MSI Modern 14 Black",
        "price": 94789,
        "category": "electronics",
    },
    "153": {
        "id": 153,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 9990,
        "category": "kitchen",
    },
    "154": {
        "id": 154,
        "name": "Razer DeathAdder V3 Mouse 2024 Model",
        "price": 27567,
        "category": "gaming",
    },
    "155": {
        "id": 155,
        "name": "Zara Slim Fit Blazer Blue",
        "price": 1772,
        "category": "clothing",
    },
    "156": {
        "id": 156,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 27239,
        "category": "home",
    },
    "157": {
        "id": 157,
        "name": "Xbox Series X Blue",
        "price": 61079,
        "category": "gaming",
    },
    "158": {
        "id": 158,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 12846,
        "category": "kitchen",
    },
    "159": {
        "id": 159,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 36909,
        "category": "home",
    },
    "160": {
        "id": 160,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 6714,
        "category": "kitchen",
    },
    "161": {
        "id": 161,
        "name": "H&M Oversized Hoodie Black",
        "price": 5484,
        "category": "clothing",
    },
    "162": {
        "id": 162,
        "name": "Sleepwell Memory Foam Mattress Pro Edition",
        "price": 29835,
        "category": "home",
    },
    "163": {
        "id": 163,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 35758,
        "category": "home",
    },
    "164": {
        "id": 164,
        "name": "Sleepwell Memory Foam Mattress Black",
        "price": 53340,
        "category": "home",
    },
    "165": {
        "id": 165,
        "name": "Razer DeathAdder V3 Mouse Silver",
        "price": 51500,
        "category": "gaming",
    },
    "166": {
        "id": 166,
        "name": "Sleepwell Memory Foam Mattress Pro Edition",
        "price": 16817,
        "category": "home",
    },
    "167": {
        "id": 167,
        "name": "Philips LED Desk Lamp Pro Edition",
        "price": 56203,
        "category": "home",
    },
    "168": {
        "id": 168,
        "name": "Adidas Supercourt Sneakers 2024 Model",
        "price": 5348,
        "category": "clothing",
    },
    "169": {
        "id": 169,
        "name": "Zara Slim Fit Blazer Black",
        "price": 5391,
        "category": "clothing",
    },
    "170": {
        "id": 170,
        "name": "MacBook Pro 14-inch M3 Black",
        "price": 160198,
        "category": "electronics",
    },
    "171": {
        "id": 171,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 13422,
        "category": "kitchen",
    },
    "172": {
        "id": 172,
        "name": "Xiaomi Redmi Note 12 Pro Black",
        "price": 59490,
        "category": "electronics",
    },
    "173": {
        "id": 173,
        "name": "Bosch Mixer Grinder Blue",
        "price": 13293,
        "category": "kitchen",
    },
    "174": {
        "id": 174,
        "name": "Samsung Galaxy Buds2 Pro 2024 Model",
        "price": 144685,
        "category": "electronics",
    },
    "175": {
        "id": 175,
        "name": "Xiaomi Smart TV 5A Blue",
        "price": 47120,
        "category": "electronics",
    },
    "176": {
        "id": 176,
        "name": "Acer Aspire 7 2024 Model",
        "price": 117383,
        "category": "electronics",
    },
    "177": {
        "id": 177,
        "name": "Bosch Mixer Grinder",
        "price": 8591,
        "category": "kitchen",
    },
    "178": {
        "id": 178,
        "name": "HyperX Cloud II Gaming Headset",
        "price": 10366,
        "category": "gaming",
    },
    "179": {
        "id": 179,
        "name": "Ikea Study Table LINNMON Blue",
        "price": 49437,
        "category": "home",
    },
    "180": {
        "id": 180,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 2513,
        "category": "kitchen",
    },
    "181": {
        "id": 181,
        "name": "Levi's 511 Slim Fit Jeans",
        "price": 6144,
        "category": "clothing",
    },
    "182": {
        "id": 182,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 10645,
        "category": "kitchen",
    },
    "183": {
        "id": 183,
        "name": "Philips Airfryer XL",
        "price": 15390,
        "category": "kitchen",
    },
    "184": {
        "id": 184,
        "name": "Philips LED Desk Lamp Blue",
        "price": 37098,
        "category": "home",
    },
    "185": {
        "id": 185,
        "name": "Puma Running Shoes Silver",
        "price": 1314,
        "category": "clothing",
    },
    "186": {
        "id": 186,
        "name": "Levi's 511 Slim Fit Jeans",
        "price": 6418,
        "category": "clothing",
    },
    "187": {
        "id": 187,
        "name": "Levi's 511 Slim Fit Jeans Blue",
        "price": 6834,
        "category": "clothing",
    },
    "188": {
        "id": 188,
        "name": "MacBook Pro 14-inch M3 Blue",
        "price": 115126,
        "category": "electronics",
    },
    "189": {
        "id": 189,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 5797,
        "category": "kitchen",
    },
    "190": {
        "id": 190,
        "name": "Xiaomi Redmi Note 12 Pro Pro Edition",
        "price": 154298,
        "category": "electronics",
    },
    "191": {
        "id": 191,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 12427,
        "category": "kitchen",
    },
    "192": {
        "id": 192,
        "name": "Apple iPhone 14 Pro Edition",
        "price": 162124,
        "category": "electronics",
    },
    "193": {
        "id": 193,
        "name": "Nintendo Switch OLED 2024 Model",
        "price": 26661,
        "category": "gaming",
    },
    "194": {
        "id": 194,
        "name": "Allen Solly Cotton Shirt",
        "price": 6846,
        "category": "clothing",
    },
    "195": {
        "id": 195,
        "name": "MacBook Air M2 2024 Model",
        "price": 104671,
        "category": "electronics",
    },
    "196": {
        "id": 196,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 11615,
        "category": "kitchen",
    },
    "197": {
        "id": 197,
        "name": "Sleepwell Memory Foam Mattress Silver",
        "price": 42199,
        "category": "home",
    },
    "198": {
        "id": 198,
        "name": "Sony PlayStation 5 Blue",
        "price": 21285,
        "category": "gaming",
    },
    "199": {
        "id": 199,
        "name": "Nintendo Switch OLED Black",
        "price": 40675,
        "category": "gaming",
    },
    "200": {
        "id": 200,
        "name": "MacBook Air M2 Blue",
        "price": 120033,
        "category": "electronics",
    },
    "201": {
        "id": 201,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 19281,
        "category": "gaming",
    },
    "202": {
        "id": 202,
        "name": "Sony WH-1000XM5 2024 Model",
        "price": 31812,
        "category": "electronics",
    },
    "203": {
        "id": 203,
        "name": "Sleepwell Memory Foam Mattress 2024 Model",
        "price": 34392,
        "category": "home",
    },
    "204": {
        "id": 204,
        "name": "Philips Airfryer XL",
        "price": 4055,
        "category": "kitchen",
    },
    "205": {
        "id": 205,
        "name": "Philips LED Desk Lamp Pro Edition",
        "price": 467,
        "category": "home",
    },
    "206": {
        "id": 206,
        "name": "Amazon Echo Dot 5th Gen Black",
        "price": 176453,
        "category": "electronics",
    },
    "207": {
        "id": 207,
        "name": "Havells Toaster 2024 Model",
        "price": 13952,
        "category": "kitchen",
    },
    "208": {
        "id": 208,
        "name": "Ikea Study Table LINNMON Black",
        "price": 8347,
        "category": "home",
    },
    "209": {
        "id": 209,
        "name": "HyperX Cloud II Gaming Headset",
        "price": 35913,
        "category": "gaming",
    },
    "210": {
        "id": 210,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 9005,
        "category": "kitchen",
    },
    "211": {
        "id": 211,
        "name": "Nike Air Max Shoes",
        "price": 2015,
        "category": "clothing",
    },
    "212": {
        "id": 212,
        "name": "Nintendo Switch OLED",
        "price": 21369,
        "category": "gaming",
    },
    "213": {
        "id": 213,
        "name": "Nintendo Switch OLED Silver",
        "price": 65773,
        "category": "gaming",
    },
    "214": {
        "id": 214,
        "name": "Sleepwell Memory Foam Mattress Blue",
        "price": 13485,
        "category": "home",
    },
    "215": {
        "id": 215,
        "name": "Apple AirPods Pro 2",
        "price": 122283,
        "category": "electronics",
    },
    "216": {
        "id": 216,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 30903,
        "category": "home",
    },
    "217": {
        "id": 217,
        "name": "H&M Oversized Hoodie Silver",
        "price": 5886,
        "category": "clothing",
    },
    "218": {
        "id": 218,
        "name": "Logitech G Pro X Keyboard",
        "price": 69892,
        "category": "gaming",
    },
    "219": {
        "id": 219,
        "name": "Apple AirPods Pro 2",
        "price": 78395,
        "category": "electronics",
    },
    "220": {
        "id": 220,
        "name": "JBL Flip 6 Pro Edition",
        "price": 170247,
        "category": "electronics",
    },
    "221": {
        "id": 221,
        "name": "Logitech G Pro X Keyboard",
        "price": 42865,
        "category": "gaming",
    },
    "222": {
        "id": 222,
        "name": "H&M Oversized Hoodie Blue",
        "price": 4024,
        "category": "clothing",
    },
    "223": {
        "id": 223,
        "name": "Samsung Galaxy Book 3 Pro Edition",
        "price": 63646,
        "category": "electronics",
    },
    "224": {
        "id": 224,
        "name": "Zara Slim Fit Blazer Black",
        "price": 1745,
        "category": "clothing",
    },
    "225": {
        "id": 225,
        "name": "Apple iPhone 14 Black",
        "price": 142203,
        "category": "electronics",
    },
    "226": {
        "id": 226,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 3372,
        "category": "kitchen",
    },
    "227": {
        "id": 227,
        "name": "Xbox Series X Silver",
        "price": 31956,
        "category": "gaming",
    },
    "228": {
        "id": 228,
        "name": "Levi's 511 Slim Fit Jeans",
        "price": 3453,
        "category": "clothing",
    },
    "229": {
        "id": 229,
        "name": "Sleepwell Memory Foam Mattress Silver",
        "price": 30536,
        "category": "home",
    },
    "230": {
        "id": 230,
        "name": "Prestige Pressure Cooker 2024 Model",
        "price": 2361,
        "category": "kitchen",
    },
    "231": {
        "id": 231,
        "name": "Philips Airfryer XL Blue",
        "price": 367,
        "category": "kitchen",
    },
    "232": {
        "id": 232,
        "name": "Xiaomi Smart TV 5A",
        "price": 53500,
        "category": "electronics",
    },
    "233": {
        "id": 233,
        "name": "Marshall Emberton",
        "price": 54891,
        "category": "electronics",
    },
    "234": {
        "id": 234,
        "name": 'Samsung Neo QLED 55" 2024 Model',
        "price": 71629,
        "category": "electronics",
    },
    "235": {
        "id": 235,
        "name": "Nintendo Switch OLED Blue",
        "price": 33572,
        "category": "gaming",
    },
    "236": {
        "id": 236,
        "name": "Levi's 511 Slim Fit Jeans Black",
        "price": 5016,
        "category": "clothing",
    },
    "237": {
        "id": 237,
        "name": "Xbox Series X Silver",
        "price": 29549,
        "category": "gaming",
    },
    "238": {
        "id": 238,
        "name": "Samsung Galaxy Watch 6",
        "price": 171894,
        "category": "electronics",
    },
    "239": {
        "id": 239,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 10088,
        "category": "gaming",
    },
    "240": {
        "id": 240,
        "name": "Prestige Pressure Cooker 2024 Model",
        "price": 15367,
        "category": "kitchen",
    },
    "241": {
        "id": 241,
        "name": "Xiaomi Smart TV 5A Silver",
        "price": 41132,
        "category": "electronics",
    },
    "242": {
        "id": 242,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 14045,
        "category": "kitchen",
    },
    "243": {
        "id": 243,
        "name": "Sony SRS-XB13 Blue",
        "price": 176566,
        "category": "electronics",
    },
    "244": {
        "id": 244,
        "name": "Zara Slim Fit Blazer Blue",
        "price": 3582,
        "category": "clothing",
    },
    "245": {
        "id": 245,
        "name": "Logitech G Pro X Keyboard Black",
        "price": 39139,
        "category": "gaming",
    },
    "246": {
        "id": 246,
        "name": "Apple iPhone 14 2024 Model",
        "price": 43337,
        "category": "electronics",
    },
    "247": {
        "id": 247,
        "name": "Nike Air Max Shoes Black",
        "price": 769,
        "category": "clothing",
    },
    "248": {
        "id": 248,
        "name": "Havells Toaster Blue",
        "price": 16147,
        "category": "kitchen",
    },
    "249": {
        "id": 249,
        "name": "Samsung Galaxy A54 Silver",
        "price": 156834,
        "category": "electronics",
    },
    "250": {
        "id": 250,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 27684,
        "category": "home",
    },
    "251": {
        "id": 251,
        "name": "Nintendo Switch OLED Blue",
        "price": 45631,
        "category": "gaming",
    },
    "252": {
        "id": 252,
        "name": "Puma Running Shoes Pro Edition",
        "price": 3352,
        "category": "clothing",
    },
    "253": {
        "id": 253,
        "name": "Apple iPhone 15 Pro 2024 Model",
        "price": 32634,
        "category": "electronics",
    },
    "254": {
        "id": 254,
        "name": "AmazonBasics Wall Clock Black",
        "price": 36328,
        "category": "home",
    },
    "255": {
        "id": 255,
        "name": "Levi's 511 Slim Fit Jeans Silver",
        "price": 2156,
        "category": "clothing",
    },
    "256": {
        "id": 256,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 1829,
        "category": "home",
    },
    "257": {
        "id": 257,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 18237,
        "category": "kitchen",
    },
    "258": {
        "id": 258,
        "name": "Samsung Galaxy A54 Blue",
        "price": 128865,
        "category": "electronics",
    },
    "259": {
        "id": 259,
        "name": "Zara Slim Fit Blazer Black",
        "price": 5238,
        "category": "clothing",
    },
    "260": {
        "id": 260,
        "name": "AmazonBasics Wall Clock 2024 Model",
        "price": 28195,
        "category": "home",
    },
    "261": {
        "id": 261,
        "name": "Ikea Study Table LINNMON",
        "price": 48527,
        "category": "home",
    },
    "262": {
        "id": 262,
        "name": "Xbox Series X Blue",
        "price": 58037,
        "category": "gaming",
    },
    "263": {
        "id": 263,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 54808,
        "category": "home",
    },
    "264": {
        "id": 264,
        "name": "Zara Slim Fit Blazer Blue",
        "price": 3231,
        "category": "clothing",
    },
    "265": {
        "id": 265,
        "name": "Bosch Mixer Grinder Pro Edition",
        "price": 5696,
        "category": "kitchen",
    },
    "266": {
        "id": 266,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 40568,
        "category": "home",
    },
    "267": {
        "id": 267,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 16273,
        "category": "kitchen",
    },
    "268": {
        "id": 268,
        "name": "Havells Toaster Silver",
        "price": 4349,
        "category": "kitchen",
    },
    "269": {
        "id": 269,
        "name": "Levi's 511 Slim Fit Jeans Blue",
        "price": 6652,
        "category": "clothing",
    },
    "270": {
        "id": 270,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 58869,
        "category": "home",
    },
    "271": {
        "id": 271,
        "name": "Nintendo Switch OLED",
        "price": 67833,
        "category": "gaming",
    },
    "272": {
        "id": 272,
        "name": "Levi's 511 Slim Fit Jeans",
        "price": 4374,
        "category": "clothing",
    },
    "273": {
        "id": 273,
        "name": "Sony PlayStation 5 Blue",
        "price": 59704,
        "category": "gaming",
    },
    "274": {
        "id": 274,
        "name": "Nike Air Max Shoes Silver",
        "price": 3081,
        "category": "clothing",
    },
    "275": {
        "id": 275,
        "name": "Xbox Series X Pro Edition",
        "price": 48926,
        "category": "gaming",
    },
    "276": {
        "id": 276,
        "name": "Nintendo Switch OLED Silver",
        "price": 50181,
        "category": "gaming",
    },
    "277": {
        "id": 277,
        "name": "Allen Solly Cotton Shirt 2024 Model",
        "price": 7394,
        "category": "clothing",
    },
    "278": {
        "id": 278,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 39857,
        "category": "gaming",
    },
    "279": {
        "id": 279,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 3122,
        "category": "gaming",
    },
    "280": {
        "id": 280,
        "name": "Philips LED Desk Lamp Blue",
        "price": 54894,
        "category": "home",
    },
    "281": {
        "id": 281,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 23792,
        "category": "home",
    },
    "282": {
        "id": 282,
        "name": "Logitech G Pro X Keyboard Black",
        "price": 59424,
        "category": "gaming",
    },
    "283": {
        "id": 283,
        "name": "Philips LED Desk Lamp",
        "price": 5078,
        "category": "home",
    },
    "284": {
        "id": 284,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 9356,
        "category": "home",
    },
    "285": {
        "id": 285,
        "name": "Nike Air Max Shoes",
        "price": 7841,
        "category": "clothing",
    },
    "286": {
        "id": 286,
        "name": "Sony PlayStation 5 Blue",
        "price": 19924,
        "category": "gaming",
    },
    "287": {
        "id": 287,
        "name": "Xbox Series X Blue",
        "price": 25571,
        "category": "gaming",
    },
    "288": {
        "id": 288,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 2418,
        "category": "kitchen",
    },
    "289": {
        "id": 289,
        "name": "H&M Oversized Hoodie Blue",
        "price": 6272,
        "category": "clothing",
    },
    "290": {
        "id": 290,
        "name": "AmazonBasics Wall Clock",
        "price": 43885,
        "category": "home",
    },
    "291": {
        "id": 291,
        "name": "Xbox Series X Black",
        "price": 12036,
        "category": "gaming",
    },
    "292": {
        "id": 292,
        "name": "Havells Toaster Blue",
        "price": 18246,
        "category": "kitchen",
    },
    "293": {
        "id": 293,
        "name": "Bose QuietComfort 45 Black",
        "price": 168727,
        "category": "electronics",
    },
    "294": {
        "id": 294,
        "name": "Sleepwell Memory Foam Mattress 2024 Model",
        "price": 46834,
        "category": "home",
    },
    "295": {
        "id": 295,
        "name": "Havells Toaster Blue",
        "price": 11551,
        "category": "kitchen",
    },
    "296": {
        "id": 296,
        "name": "AmazonBasics Wall Clock",
        "price": 33892,
        "category": "home",
    },
    "297": {
        "id": 297,
        "name": "Realme GT Neo 3 Pro Edition",
        "price": 84981,
        "category": "electronics",
    },
    "298": {
        "id": 298,
        "name": "Sony Bravia X80K Blue",
        "price": 127894,
        "category": "electronics",
    },
    "299": {
        "id": 299,
        "name": "MSI Modern 14",
        "price": 94944,
        "category": "electronics",
    },
    "300": {
        "id": 300,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 44497,
        "category": "home",
    },
    "301": {
        "id": 301,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 50915,
        "category": "gaming",
    },
    "302": {
        "id": 302,
        "name": "Xbox Series X 2024 Model",
        "price": 6125,
        "category": "gaming",
    },
    "303": {
        "id": 303,
        "name": "Xbox Series X Black",
        "price": 6785,
        "category": "gaming",
    },
    "304": {
        "id": 304,
        "name": "Ikea Study Table LINNMON Blue",
        "price": 5485,
        "category": "home",
    },
    "305": {
        "id": 305,
        "name": "Samsung Galaxy Book 3 Pro Edition",
        "price": 41088,
        "category": "electronics",
    },
    "306": {
        "id": 306,
        "name": "Samsung Galaxy Buds2 Pro",
        "price": 82732,
        "category": "electronics",
    },
    "307": {
        "id": 307,
        "name": "Ikea Study Table LINNMON 2024 Model",
        "price": 24481,
        "category": "home",
    },
    "308": {
        "id": 308,
        "name": "Milton Thermosteel Bottle 1L Black",
        "price": 15388,
        "category": "kitchen",
    },
    "309": {
        "id": 309,
        "name": "Philips Airfryer XL Black",
        "price": 15333,
        "category": "kitchen",
    },
    "310": {
        "id": 310,
        "name": "Prestige Pressure Cooker Black",
        "price": 4354,
        "category": "kitchen",
    },
    "311": {
        "id": 311,
        "name": "Realme GT Neo 3 Black",
        "price": 44201,
        "category": "electronics",
    },
    "312": {
        "id": 312,
        "name": "Dyson V12 Vacuum Cleaner 2024 Model",
        "price": 57863,
        "category": "home",
    },
    "313": {
        "id": 313,
        "name": "Havells Toaster Blue",
        "price": 1466,
        "category": "kitchen",
    },
    "314": {
        "id": 314,
        "name": "Puma Running Shoes",
        "price": 1423,
        "category": "clothing",
    },
    "315": {
        "id": 315,
        "name": "Philips LED Desk Lamp Silver",
        "price": 45761,
        "category": "home",
    },
    "316": {
        "id": 316,
        "name": "Razer DeathAdder V3 Mouse Silver",
        "price": 33602,
        "category": "gaming",
    },
    "317": {
        "id": 317,
        "name": "Adidas Supercourt Sneakers Blue",
        "price": 824,
        "category": "clothing",
    },
    "318": {
        "id": 318,
        "name": "Boat Stone 1000",
        "price": 98832,
        "category": "electronics",
    },
    "319": {
        "id": 319,
        "name": "H&M Oversized Hoodie Blue",
        "price": 2704,
        "category": "clothing",
    },
    "320": {
        "id": 320,
        "name": "Zara Slim Fit Blazer",
        "price": 5415,
        "category": "clothing",
    },
    "321": {
        "id": 321,
        "name": "Dyson V12 Vacuum Cleaner 2024 Model",
        "price": 3575,
        "category": "home",
    },
    "322": {
        "id": 322,
        "name": "AmazonBasics Wall Clock",
        "price": 57280,
        "category": "home",
    },
    "323": {
        "id": 323,
        "name": 'Samsung Neo QLED 55" Pro Edition',
        "price": 168887,
        "category": "electronics",
    },
    "324": {
        "id": 324,
        "name": "Havells Toaster",
        "price": 19566,
        "category": "kitchen",
    },
    "325": {
        "id": 325,
        "name": "Allen Solly Cotton Shirt Blue",
        "price": 1552,
        "category": "clothing",
    },
    "326": {
        "id": 326,
        "name": "Nintendo Switch OLED",
        "price": 8857,
        "category": "gaming",
    },
    "327": {
        "id": 327,
        "name": "JBL Tune 760NC Black",
        "price": 71839,
        "category": "electronics",
    },
    "328": {
        "id": 328,
        "name": "Levi's 511 Slim Fit Jeans",
        "price": 3813,
        "category": "clothing",
    },
    "329": {
        "id": 329,
        "name": "Allen Solly Cotton Shirt Blue",
        "price": 2180,
        "category": "clothing",
    },
    "330": {
        "id": 330,
        "name": "Razer DeathAdder V3 Mouse 2024 Model",
        "price": 69617,
        "category": "gaming",
    },
    "331": {
        "id": 331,
        "name": "Boat Stone 1000 Silver",
        "price": 8868,
        "category": "electronics",
    },
    "332": {
        "id": 332,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 2774,
        "category": "kitchen",
    },
    "333": {
        "id": 333,
        "name": "Razer DeathAdder V3 Mouse",
        "price": 10690,
        "category": "gaming",
    },
    "334": {
        "id": 334,
        "name": "Bose QuietComfort 45 2024 Model",
        "price": 118116,
        "category": "electronics",
    },
    "335": {
        "id": 335,
        "name": "Prestige Pressure Cooker Blue",
        "price": 18446,
        "category": "kitchen",
    },
    "336": {
        "id": 336,
        "name": "Havells Toaster 2024 Model",
        "price": 8587,
        "category": "kitchen",
    },
    "337": {
        "id": 337,
        "name": "Havells Toaster Silver",
        "price": 18659,
        "category": "kitchen",
    },
    "338": {
        "id": 338,
        "name": "Bosch Mixer Grinder Blue",
        "price": 2226,
        "category": "kitchen",
    },
    "339": {
        "id": 339,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 1248,
        "category": "kitchen",
    },
    "340": {
        "id": 340,
        "name": "Adidas Supercourt Sneakers Blue",
        "price": 2033,
        "category": "clothing",
    },
    "341": {
        "id": 341,
        "name": "Google Pixel 8 Pro 2024 Model",
        "price": 162353,
        "category": "electronics",
    },
    "342": {
        "id": 342,
        "name": "Sleepwell Memory Foam Mattress Pro Edition",
        "price": 52767,
        "category": "home",
    },
    "343": {
        "id": 343,
        "name": "Puma Running Shoes",
        "price": 5466,
        "category": "clothing",
    },
    "344": {
        "id": 344,
        "name": "HyperX Cloud II Gaming Headset Silver",
        "price": 69802,
        "category": "gaming",
    },
    "345": {
        "id": 345,
        "name": "Levi's 511 Slim Fit Jeans Black",
        "price": 7778,
        "category": "clothing",
    },
    "346": {
        "id": 346,
        "name": "Levi's 511 Slim Fit Jeans Black",
        "price": 5020,
        "category": "clothing",
    },
    "347": {
        "id": 347,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 7081,
        "category": "kitchen",
    },
    "348": {
        "id": 348,
        "name": "HyperX Cloud II Gaming Headset Silver",
        "price": 19148,
        "category": "gaming",
    },
    "349": {
        "id": 349,
        "name": "Razer DeathAdder V3 Mouse",
        "price": 28058,
        "category": "gaming",
    },
    "350": {
        "id": 350,
        "name": "Samsung Galaxy Book 3 Blue",
        "price": 73743,
        "category": "electronics",
    },
    "351": {
        "id": 351,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 5431,
        "category": "home",
    },
    "352": {
        "id": 352,
        "name": "Boat Rockerz 255 Pro+ Silver",
        "price": 147488,
        "category": "electronics",
    },
    "353": {
        "id": 353,
        "name": "Prestige Pressure Cooker Blue",
        "price": 13909,
        "category": "kitchen",
    },
    "354": {
        "id": 354,
        "name": "Samsung Galaxy Buds2 Pro Pro Edition",
        "price": 112266,
        "category": "electronics",
    },
    "355": {
        "id": 355,
        "name": "Havells Toaster Blue",
        "price": 2299,
        "category": "kitchen",
    },
    "356": {
        "id": 356,
        "name": "AmazonBasics Wall Clock Black",
        "price": 40467,
        "category": "home",
    },
    "357": {
        "id": 357,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 28614,
        "category": "home",
    },
    "358": {
        "id": 358,
        "name": "H&M Oversized Hoodie Blue",
        "price": 6249,
        "category": "clothing",
    },
    "359": {
        "id": 359,
        "name": "Sony PlayStation 5",
        "price": 64117,
        "category": "gaming",
    },
    "360": {
        "id": 360,
        "name": "HyperX Cloud II Gaming Headset Pro Edition",
        "price": 56721,
        "category": "gaming",
    },
    "361": {
        "id": 361,
        "name": "Allen Solly Cotton Shirt Silver",
        "price": 6754,
        "category": "clothing",
    },
    "362": {
        "id": 362,
        "name": "Logitech G Pro X Keyboard Blue",
        "price": 62934,
        "category": "gaming",
    },
    "363": {
        "id": 363,
        "name": "Sony WH-1000XM5",
        "price": 27548,
        "category": "electronics",
    },
    "364": {
        "id": 364,
        "name": "Apple Watch Series 9 Pro Edition",
        "price": 142542,
        "category": "electronics",
    },
    "365": {
        "id": 365,
        "name": "Bosch Mixer Grinder Black",
        "price": 12433,
        "category": "kitchen",
    },
    "366": {
        "id": 366,
        "name": "Philips LED Desk Lamp",
        "price": 17521,
        "category": "home",
    },
    "367": {
        "id": 367,
        "name": "Razer DeathAdder V3 Mouse Blue",
        "price": 24812,
        "category": "gaming",
    },
    "368": {
        "id": 368,
        "name": "Nintendo Switch OLED Blue",
        "price": 62248,
        "category": "gaming",
    },
    "369": {
        "id": 369,
        "name": "Dell XPS 13 Pro Edition",
        "price": 104172,
        "category": "electronics",
    },
    "370": {
        "id": 370,
        "name": "Havells Toaster 2024 Model",
        "price": 19734,
        "category": "kitchen",
    },
    "371": {
        "id": 371,
        "name": "Philips Airfryer XL",
        "price": 18284,
        "category": "kitchen",
    },
    "372": {
        "id": 372,
        "name": "Philips Airfryer XL Black",
        "price": 12042,
        "category": "kitchen",
    },
    "373": {
        "id": 373,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 42904,
        "category": "gaming",
    },
    "374": {
        "id": 374,
        "name": "H&M Oversized Hoodie Silver",
        "price": 5630,
        "category": "clothing",
    },
    "375": {
        "id": 375,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 49141,
        "category": "home",
    },
    "376": {
        "id": 376,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 9404,
        "category": "home",
    },
    "377": {
        "id": 377,
        "name": "Apple iPhone 15 Pro Black",
        "price": 18734,
        "category": "electronics",
    },
    "378": {
        "id": 378,
        "name": "Xbox Series X Black",
        "price": 42481,
        "category": "gaming",
    },
    "379": {
        "id": 379,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 6912,
        "category": "kitchen",
    },
    "380": {
        "id": 380,
        "name": "Ikea Study Table LINNMON Black",
        "price": 10776,
        "category": "home",
    },
    "381": {
        "id": 381,
        "name": "Prestige Pressure Cooker Silver",
        "price": 11604,
        "category": "kitchen",
    },
    "382": {
        "id": 382,
        "name": "Prestige Pressure Cooker Silver",
        "price": 15109,
        "category": "kitchen",
    },
    "383": {
        "id": 383,
        "name": "Puma Running Shoes Black",
        "price": 2564,
        "category": "clothing",
    },
    "384": {
        "id": 384,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 16123,
        "category": "home",
    },
    "385": {
        "id": 385,
        "name": "Allen Solly Cotton Shirt Black",
        "price": 4746,
        "category": "clothing",
    },
    "386": {
        "id": 386,
        "name": "Samsung Galaxy Book 3 Blue",
        "price": 24724,
        "category": "electronics",
    },
    "387": {
        "id": 387,
        "name": "Bosch Mixer Grinder Blue",
        "price": 4470,
        "category": "kitchen",
    },
    "388": {
        "id": 388,
        "name": "Sleepwell Memory Foam Mattress Pro Edition",
        "price": 48233,
        "category": "home",
    },
    "389": {
        "id": 389,
        "name": "Logitech G Pro X Keyboard",
        "price": 3583,
        "category": "gaming",
    },
    "390": {
        "id": 390,
        "name": "Lenovo ThinkPad X1 Carbon 2024 Model",
        "price": 75236,
        "category": "electronics",
    },
    "391": {
        "id": 391,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 10762,
        "category": "kitchen",
    },
    "392": {
        "id": 392,
        "name": "Sony Bravia X80K",
        "price": 127917,
        "category": "electronics",
    },
    "393": {
        "id": 393,
        "name": "Zara Slim Fit Blazer",
        "price": 6022,
        "category": "clothing",
    },
    "394": {
        "id": 394,
        "name": "Philips LED Desk Lamp 2024 Model",
        "price": 50497,
        "category": "home",
    },
    "395": {
        "id": 395,
        "name": "Apple AirPods Pro 2 Blue",
        "price": 21327,
        "category": "electronics",
    },
    "396": {
        "id": 396,
        "name": "Google Pixel 8 Pro Silver",
        "price": 83938,
        "category": "electronics",
    },
    "397": {
        "id": 397,
        "name": "Apple AirPods Pro 2 Black",
        "price": 163372,
        "category": "electronics",
    },
    "398": {
        "id": 398,
        "name": "H&M Oversized Hoodie 2024 Model",
        "price": 1483,
        "category": "clothing",
    },
    "399": {
        "id": 399,
        "name": "H&M Oversized Hoodie",
        "price": 1228,
        "category": "clothing",
    },
    "400": {
        "id": 400,
        "name": "Allen Solly Cotton Shirt Black",
        "price": 1667,
        "category": "clothing",
    },
    "401": {
        "id": 401,
        "name": "Adidas Supercourt Sneakers Black",
        "price": 3306,
        "category": "clothing",
    },
    "402": {
        "id": 402,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 909,
        "category": "gaming",
    },
    "403": {
        "id": 403,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 12773,
        "category": "home",
    },
    "404": {
        "id": 404,
        "name": "Havells Toaster Black",
        "price": 11418,
        "category": "kitchen",
    },
    "405": {
        "id": 405,
        "name": "Samsung Galaxy A54 2024 Model",
        "price": 174848,
        "category": "electronics",
    },
    "406": {
        "id": 406,
        "name": "Allen Solly Cotton Shirt",
        "price": 3410,
        "category": "clothing",
    },
    "407": {
        "id": 407,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 525,
        "category": "kitchen",
    },
    "408": {
        "id": 408,
        "name": "Noise ColorFit Ultra Blue",
        "price": 70491,
        "category": "electronics",
    },
    "409": {
        "id": 409,
        "name": "Razer DeathAdder V3 Mouse Silver",
        "price": 21374,
        "category": "gaming",
    },
    "410": {
        "id": 410,
        "name": "Allen Solly Cotton Shirt Pro Edition",
        "price": 3639,
        "category": "clothing",
    },
    "411": {
        "id": 411,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 45057,
        "category": "home",
    },
    "412": {
        "id": 412,
        "name": "Xbox Series X Silver",
        "price": 15215,
        "category": "gaming",
    },
    "413": {
        "id": 413,
        "name": "Prestige Pressure Cooker",
        "price": 19402,
        "category": "kitchen",
    },
    "414": {
        "id": 414,
        "name": "H&M Oversized Hoodie Silver",
        "price": 1166,
        "category": "clothing",
    },
    "415": {
        "id": 415,
        "name": "AmazonBasics Wall Clock 2024 Model",
        "price": 47539,
        "category": "home",
    },
    "416": {
        "id": 416,
        "name": "HyperX Cloud II Gaming Headset Blue",
        "price": 26088,
        "category": "gaming",
    },
    "417": {
        "id": 417,
        "name": "Nike Air Max Shoes Blue",
        "price": 3234,
        "category": "clothing",
    },
    "418": {
        "id": 418,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 24956,
        "category": "home",
    },
    "419": {
        "id": 419,
        "name": "Philips LED Desk Lamp Pro Edition",
        "price": 48816,
        "category": "home",
    },
    "420": {
        "id": 420,
        "name": "Allen Solly Cotton Shirt",
        "price": 7523,
        "category": "clothing",
    },
    "421": {
        "id": 421,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 32333,
        "category": "gaming",
    },
    "422": {
        "id": 422,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 17945,
        "category": "kitchen",
    },
    "423": {
        "id": 423,
        "name": "Philips Airfryer XL Silver",
        "price": 9126,
        "category": "kitchen",
    },
    "424": {
        "id": 424,
        "name": "JBL Flip 6 Blue",
        "price": 91234,
        "category": "electronics",
    },
    "425": {
        "id": 425,
        "name": "Havells Toaster Silver",
        "price": 16062,
        "category": "kitchen",
    },
    "426": {
        "id": 426,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 19477,
        "category": "home",
    },
    "427": {
        "id": 427,
        "name": "Sony PlayStation 5 Pro Edition",
        "price": 45155,
        "category": "gaming",
    },
    "428": {
        "id": 428,
        "name": "Sleepwell Memory Foam Mattress 2024 Model",
        "price": 750,
        "category": "home",
    },
    "429": {
        "id": 429,
        "name": "Samsung Galaxy S23 Ultra Pro Edition",
        "price": 161166,
        "category": "electronics",
    },
    "430": {
        "id": 430,
        "name": "Zara Slim Fit Blazer",
        "price": 1392,
        "category": "clothing",
    },
    "431": {
        "id": 431,
        "name": "Sony PlayStation 5 Silver",
        "price": 4767,
        "category": "gaming",
    },
    "432": {
        "id": 432,
        "name": "Sleepwell Memory Foam Mattress Silver",
        "price": 13287,
        "category": "home",
    },
    "433": {
        "id": 433,
        "name": "MacBook Pro 14-inch M3 Blue",
        "price": 158017,
        "category": "electronics",
    },
    "434": {
        "id": 434,
        "name": "Zara Slim Fit Blazer Pro Edition",
        "price": 3822,
        "category": "clothing",
    },
    "435": {"id": 435, "name": "Havells Toaster", "price": 1710, "category": "kitchen"},
    "436": {
        "id": 436,
        "name": "Zara Slim Fit Blazer Blue",
        "price": 5217,
        "category": "clothing",
    },
    "437": {
        "id": 437,
        "name": "Logitech G Pro X Keyboard",
        "price": 17385,
        "category": "gaming",
    },
    "438": {
        "id": 438,
        "name": "Xbox Series X 2024 Model",
        "price": 21892,
        "category": "gaming",
    },
    "439": {
        "id": 439,
        "name": "Havells Toaster Pro Edition",
        "price": 4687,
        "category": "kitchen",
    },
    "440": {
        "id": 440,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 6829,
        "category": "kitchen",
    },
    "441": {
        "id": 441,
        "name": "Samsung Galaxy S23 Ultra 2024 Model",
        "price": 32273,
        "category": "electronics",
    },
    "442": {
        "id": 442,
        "name": "Philips Airfryer XL Black",
        "price": 15123,
        "category": "kitchen",
    },
    "443": {
        "id": 443,
        "name": "Havells Toaster Blue",
        "price": 3530,
        "category": "kitchen",
    },
    "444": {
        "id": 444,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 14531,
        "category": "kitchen",
    },
    "445": {
        "id": 445,
        "name": "Sony PlayStation 5 Blue",
        "price": 34304,
        "category": "gaming",
    },
    "446": {
        "id": 446,
        "name": "Apple iPhone 14 Blue",
        "price": 106295,
        "category": "electronics",
    },
    "447": {
        "id": 447,
        "name": "Xiaomi Redmi Note 12 Pro Black",
        "price": 135180,
        "category": "electronics",
    },
    "448": {
        "id": 448,
        "name": "HyperX Cloud II Gaming Headset Silver",
        "price": 14903,
        "category": "gaming",
    },
    "449": {
        "id": 449,
        "name": "Dell XPS 13 2024 Model",
        "price": 34596,
        "category": "electronics",
    },
    "450": {
        "id": 450,
        "name": "Samsung Galaxy Book 3 Silver",
        "price": 34109,
        "category": "electronics",
    },
    "451": {
        "id": 451,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 43740,
        "category": "home",
    },
    "452": {
        "id": 452,
        "name": "Philips LED Desk Lamp",
        "price": 6292,
        "category": "home",
    },
    "453": {
        "id": 453,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 21170,
        "category": "home",
    },
    "454": {
        "id": 454,
        "name": "Razer DeathAdder V3 Mouse Pro Edition",
        "price": 51400,
        "category": "gaming",
    },
    "455": {
        "id": 455,
        "name": "Samsung Galaxy Watch 6",
        "price": 124840,
        "category": "electronics",
    },
    "456": {
        "id": 456,
        "name": "Xbox Series X Black",
        "price": 25712,
        "category": "gaming",
    },
    "457": {
        "id": 457,
        "name": "Havells Toaster Black",
        "price": 8624,
        "category": "kitchen",
    },
    "458": {
        "id": 458,
        "name": "Sleepwell Memory Foam Mattress Silver",
        "price": 40121,
        "category": "home",
    },
    "459": {
        "id": 459,
        "name": "Xbox Series X Silver",
        "price": 26624,
        "category": "gaming",
    },
    "460": {
        "id": 460,
        "name": "Xbox Series X Black",
        "price": 52964,
        "category": "gaming",
    },
    "461": {
        "id": 461,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 34309,
        "category": "home",
    },
    "462": {
        "id": 462,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 53351,
        "category": "home",
    },
    "463": {
        "id": 463,
        "name": "Philips LED Desk Lamp Blue",
        "price": 59514,
        "category": "home",
    },
    "464": {
        "id": 464,
        "name": "Ikea Study Table LINNMON 2024 Model",
        "price": 13649,
        "category": "home",
    },
    "465": {
        "id": 465,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 29976,
        "category": "home",
    },
    "466": {
        "id": 466,
        "name": "Sleepwell Memory Foam Mattress",
        "price": 57711,
        "category": "home",
    },
    "467": {
        "id": 467,
        "name": "Sony PlayStation 5",
        "price": 53252,
        "category": "gaming",
    },
    "468": {
        "id": 468,
        "name": "Prestige Pressure Cooker Black",
        "price": 976,
        "category": "kitchen",
    },
    "469": {
        "id": 469,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 20919,
        "category": "home",
    },
    "470": {
        "id": 470,
        "name": "MacBook Pro 14-inch M3 Black",
        "price": 96595,
        "category": "electronics",
    },
    "471": {
        "id": 471,
        "name": "Xbox Series X Pro Edition",
        "price": 3982,
        "category": "gaming",
    },
    "472": {
        "id": 472,
        "name": "Apple AirPods Pro 2 Silver",
        "price": 54605,
        "category": "electronics",
    },
    "473": {
        "id": 473,
        "name": "Zara Slim Fit Blazer Blue",
        "price": 1482,
        "category": "clothing",
    },
    "474": {
        "id": 474,
        "name": "Dyson V12 Vacuum Cleaner 2024 Model",
        "price": 9079,
        "category": "home",
    },
    "475": {
        "id": 475,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 14811,
        "category": "home",
    },
    "476": {
        "id": 476,
        "name": "Allen Solly Cotton Shirt Silver",
        "price": 4112,
        "category": "clothing",
    },
    "477": {
        "id": 477,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 48878,
        "category": "home",
    },
    "478": {
        "id": 478,
        "name": "Nothing Phone 2 2024 Model",
        "price": 155322,
        "category": "electronics",
    },
    "479": {
        "id": 479,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 8553,
        "category": "kitchen",
    },
    "480": {
        "id": 480,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 6135,
        "category": "home",
    },
    "481": {
        "id": 481,
        "name": "Philips Airfryer XL Silver",
        "price": 17231,
        "category": "kitchen",
    },
    "482": {
        "id": 482,
        "name": "Razer DeathAdder V3 Mouse Silver",
        "price": 58158,
        "category": "gaming",
    },
    "483": {
        "id": 483,
        "name": "Amazfit GTS 4 Blue",
        "price": 105919,
        "category": "electronics",
    },
    "484": {
        "id": 484,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 19536,
        "category": "kitchen",
    },
    "485": {
        "id": 485,
        "name": "Milton Thermosteel Bottle 1L Black",
        "price": 6355,
        "category": "kitchen",
    },
    "486": {
        "id": 486,
        "name": "Samsung Galaxy Buds2 Pro Black",
        "price": 161317,
        "category": "electronics",
    },
    "487": {
        "id": 487,
        "name": "AmazonBasics Wall Clock",
        "price": 34625,
        "category": "home",
    },
    "488": {
        "id": 488,
        "name": "Logitech G Pro X Keyboard",
        "price": 22648,
        "category": "gaming",
    },
    "489": {
        "id": 489,
        "name": "Havells Toaster Pro Edition",
        "price": 7215,
        "category": "kitchen",
    },
    "490": {
        "id": 490,
        "name": "Xbox Series X Black",
        "price": 38708,
        "category": "gaming",
    },
    "491": {
        "id": 491,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 12720,
        "category": "kitchen",
    },
    "492": {
        "id": 492,
        "name": "H&M Oversized Hoodie 2024 Model",
        "price": 6616,
        "category": "clothing",
    },
    "493": {
        "id": 493,
        "name": "Lenovo ThinkPad X1 Carbon 2024 Model",
        "price": 16979,
        "category": "electronics",
    },
    "494": {
        "id": 494,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 16931,
        "category": "gaming",
    },
    "495": {
        "id": 495,
        "name": "Milton Thermosteel Bottle 1L Blue",
        "price": 13615,
        "category": "kitchen",
    },
    "496": {
        "id": 496,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 55536,
        "category": "home",
    },
    "497": {
        "id": 497,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 29427,
        "category": "home",
    },
    "498": {
        "id": 498,
        "name": "Razer DeathAdder V3 Mouse Blue",
        "price": 10771,
        "category": "gaming",
    },
    "499": {
        "id": 499,
        "name": "Nintendo Switch OLED Black",
        "price": 51996,
        "category": "gaming",
    },
    "500": {
        "id": 500,
        "name": "AmazonBasics Wall Clock Black",
        "price": 5230,
        "category": "home",
    },
    "501": {
        "id": 501,
        "name": "Sony PlayStation 5 Silver",
        "price": 22741,
        "category": "gaming",
    },
    "502": {
        "id": 502,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 45493,
        "category": "gaming",
    },
    "503": {
        "id": 503,
        "name": "Noise ColorFit Ultra 2024 Model",
        "price": 127197,
        "category": "electronics",
    },
    "504": {
        "id": 504,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 67830,
        "category": "gaming",
    },
    "505": {
        "id": 505,
        "name": "Xbox Series X 2024 Model",
        "price": 45651,
        "category": "gaming",
    },
    "506": {
        "id": 506,
        "name": "Philips Airfryer XL",
        "price": 13902,
        "category": "kitchen",
    },
    "507": {
        "id": 507,
        "name": "Philips LED Desk Lamp Blue",
        "price": 39243,
        "category": "home",
    },
    "508": {
        "id": 508,
        "name": "Prestige Pressure Cooker Black",
        "price": 5542,
        "category": "kitchen",
    },
    "509": {
        "id": 509,
        "name": "Boat Rockerz 255 Pro+ Blue",
        "price": 160923,
        "category": "electronics",
    },
    "510": {
        "id": 510,
        "name": "Prestige Pressure Cooker Black",
        "price": 4197,
        "category": "kitchen",
    },
    "511": {
        "id": 511,
        "name": "Bosch Mixer Grinder",
        "price": 8892,
        "category": "kitchen",
    },
    "512": {
        "id": 512,
        "name": "Asus ROG Strix G15 2024 Model",
        "price": 60217,
        "category": "electronics",
    },
    "513": {
        "id": 513,
        "name": "Sleepwell Memory Foam Mattress Pro Edition",
        "price": 3204,
        "category": "home",
    },
    "514": {
        "id": 514,
        "name": "Apple Watch Series 9 Black",
        "price": 141032,
        "category": "electronics",
    },
    "515": {
        "id": 515,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 44217,
        "category": "home",
    },
    "516": {
        "id": 516,
        "name": "Sleepwell Memory Foam Mattress",
        "price": 51993,
        "category": "home",
    },
    "517": {
        "id": 517,
        "name": "Sony PlayStation 5",
        "price": 25595,
        "category": "gaming",
    },
    "518": {
        "id": 518,
        "name": "Adidas Supercourt Sneakers 2024 Model",
        "price": 4897,
        "category": "clothing",
    },
    "519": {
        "id": 519,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 4518,
        "category": "kitchen",
    },
    "520": {
        "id": 520,
        "name": "Amazfit GTS 4 Black",
        "price": 16069,
        "category": "electronics",
    },
    "521": {
        "id": 521,
        "name": "Philips Airfryer XL Silver",
        "price": 18961,
        "category": "kitchen",
    },
    "522": {
        "id": 522,
        "name": "HyperX Cloud II Gaming Headset Blue",
        "price": 23016,
        "category": "gaming",
    },
    "523": {
        "id": 523,
        "name": "Samsung Galaxy A54 Blue",
        "price": 109551,
        "category": "electronics",
    },
    "524": {
        "id": 524,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 19768,
        "category": "gaming",
    },
    "525": {
        "id": 525,
        "name": "Zara Slim Fit Blazer Pro Edition",
        "price": 2283,
        "category": "clothing",
    },
    "526": {
        "id": 526,
        "name": "Philips LED Desk Lamp",
        "price": 9605,
        "category": "home",
    },
    "527": {
        "id": 527,
        "name": "Nike Air Max Shoes Blue",
        "price": 4750,
        "category": "clothing",
    },
    "528": {"id": 528, "name": "Havells Toaster", "price": 8621, "category": "kitchen"},
    "529": {
        "id": 529,
        "name": "Bosch Mixer Grinder Silver",
        "price": 14095,
        "category": "kitchen",
    },
    "530": {
        "id": 530,
        "name": "Nintendo Switch OLED",
        "price": 56184,
        "category": "gaming",
    },
    "531": {
        "id": 531,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 11606,
        "category": "kitchen",
    },
    "532": {
        "id": 532,
        "name": "Bosch Mixer Grinder Black",
        "price": 8376,
        "category": "kitchen",
    },
    "533": {
        "id": 533,
        "name": "Adidas Supercourt Sneakers Black",
        "price": 2069,
        "category": "clothing",
    },
    "534": {
        "id": 534,
        "name": "Nike Air Max Shoes Pro Edition",
        "price": 782,
        "category": "clothing",
    },
    "535": {
        "id": 535,
        "name": "Adidas Supercourt Sneakers 2024 Model",
        "price": 1635,
        "category": "clothing",
    },
    "536": {
        "id": 536,
        "name": 'Samsung Neo QLED 55" Black',
        "price": 67021,
        "category": "electronics",
    },
    "537": {
        "id": 537,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 51027,
        "category": "home",
    },
    "538": {
        "id": 538,
        "name": "Prestige Pressure Cooker Black",
        "price": 14972,
        "category": "kitchen",
    },
    "539": {
        "id": 539,
        "name": "Ikea Study Table LINNMON Blue",
        "price": 52179,
        "category": "home",
    },
    "540": {
        "id": 540,
        "name": "Milton Thermosteel Bottle 1L",
        "price": 3548,
        "category": "kitchen",
    },
    "541": {
        "id": 541,
        "name": "JBL Flip 6 Pro Edition",
        "price": 109998,
        "category": "electronics",
    },
    "542": {
        "id": 542,
        "name": "H&M Oversized Hoodie Silver",
        "price": 974,
        "category": "clothing",
    },
    "543": {
        "id": 543,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 6242,
        "category": "kitchen",
    },
    "544": {
        "id": 544,
        "name": "OnePlus 11R Silver",
        "price": 120047,
        "category": "electronics",
    },
    "545": {
        "id": 545,
        "name": "TCL Mini LED TV 2024 Model",
        "price": 160317,
        "category": "electronics",
    },
    "546": {
        "id": 546,
        "name": "Levi's 511 Slim Fit Jeans Blue",
        "price": 2708,
        "category": "clothing",
    },
    "547": {
        "id": 547,
        "name": "Milton Thermosteel Bottle 1L Black",
        "price": 1912,
        "category": "kitchen",
    },
    "548": {
        "id": 548,
        "name": "Sony PlayStation 5 Blue",
        "price": 68396,
        "category": "gaming",
    },
    "549": {
        "id": 549,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 8394,
        "category": "kitchen",
    },
    "550": {
        "id": 550,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 53942,
        "category": "home",
    },
    "551": {
        "id": 551,
        "name": "Nintendo Switch OLED Black",
        "price": 57817,
        "category": "gaming",
    },
    "552": {
        "id": 552,
        "name": "H&M Oversized Hoodie Pro Edition",
        "price": 2952,
        "category": "clothing",
    },
    "553": {
        "id": 553,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 42235,
        "category": "home",
    },
    "554": {
        "id": 554,
        "name": "Lenovo ThinkPad X1 Carbon Pro Edition",
        "price": 170383,
        "category": "electronics",
    },
    "555": {
        "id": 555,
        "name": "Bosch Mixer Grinder Silver",
        "price": 14152,
        "category": "kitchen",
    },
    "556": {
        "id": 556,
        "name": "AmazonBasics Wall Clock Black",
        "price": 10604,
        "category": "home",
    },
    "557": {
        "id": 557,
        "name": "Asus ROG Strix G15 Black",
        "price": 26951,
        "category": "electronics",
    },
    "558": {
        "id": 558,
        "name": "H&M Oversized Hoodie Black",
        "price": 3333,
        "category": "clothing",
    },
    "559": {
        "id": 559,
        "name": "Sony SRS-XB13 2024 Model",
        "price": 147808,
        "category": "electronics",
    },
    "560": {
        "id": 560,
        "name": "Philips LED Desk Lamp 2024 Model",
        "price": 596,
        "category": "home",
    },
    "561": {
        "id": 561,
        "name": "Philips Airfryer XL",
        "price": 2250,
        "category": "kitchen",
    },
    "562": {
        "id": 562,
        "name": "Adidas Supercourt Sneakers",
        "price": 2213,
        "category": "clothing",
    },
    "563": {
        "id": 563,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 10209,
        "category": "home",
    },
    "564": {
        "id": 564,
        "name": "Xbox Series X Black",
        "price": 1647,
        "category": "gaming",
    },
    "565": {
        "id": 565,
        "name": "Sony PlayStation 5 Blue",
        "price": 17496,
        "category": "gaming",
    },
    "566": {
        "id": 566,
        "name": "Puma Running Shoes Blue",
        "price": 6043,
        "category": "clothing",
    },
    "567": {
        "id": 567,
        "name": "JBL Tune 760NC Silver",
        "price": 100561,
        "category": "electronics",
    },
    "568": {
        "id": 568,
        "name": "Puma Running Shoes Black",
        "price": 6623,
        "category": "clothing",
    },
    "569": {
        "id": 569,
        "name": "Allen Solly Cotton Shirt 2024 Model",
        "price": 6891,
        "category": "clothing",
    },
    "570": {
        "id": 570,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 40683,
        "category": "gaming",
    },
    "571": {
        "id": 571,
        "name": "Nike Air Max Shoes Blue",
        "price": 3696,
        "category": "clothing",
    },
    "572": {
        "id": 572,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 11826,
        "category": "kitchen",
    },
    "573": {
        "id": 573,
        "name": "Allen Solly Cotton Shirt Silver",
        "price": 1223,
        "category": "clothing",
    },
    "574": {
        "id": 574,
        "name": "Logitech G Pro X Keyboard Blue",
        "price": 47608,
        "category": "gaming",
    },
    "575": {
        "id": 575,
        "name": "MacBook Pro 14-inch M3 Pro Edition",
        "price": 26593,
        "category": "electronics",
    },
    "576": {
        "id": 576,
        "name": "Havells Toaster Pro Edition",
        "price": 7040,
        "category": "kitchen",
    },
    "577": {
        "id": 577,
        "name": "Boat Stone 1000 Blue",
        "price": 12426,
        "category": "electronics",
    },
    "578": {
        "id": 578,
        "name": "Nintendo Switch OLED",
        "price": 14961,
        "category": "gaming",
    },
    "579": {
        "id": 579,
        "name": "HyperX Cloud II Gaming Headset Black",
        "price": 4730,
        "category": "gaming",
    },
    "580": {
        "id": 580,
        "name": "Apple Watch Series 9 Silver",
        "price": 97076,
        "category": "electronics",
    },
    "581": {
        "id": 581,
        "name": "Philips Airfryer XL Blue",
        "price": 17769,
        "category": "kitchen",
    },
    "582": {
        "id": 582,
        "name": "Bosch Mixer Grinder",
        "price": 15194,
        "category": "kitchen",
    },
    "583": {
        "id": 583,
        "name": "Apple Watch Series 9 Blue",
        "price": 177408,
        "category": "electronics",
    },
    "584": {
        "id": 584,
        "name": "Sleepwell Memory Foam Mattress Silver",
        "price": 50483,
        "category": "home",
    },
    "585": {
        "id": 585,
        "name": "Ikea Study Table LINNMON Black",
        "price": 57319,
        "category": "home",
    },
    "586": {
        "id": 586,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 6318,
        "category": "kitchen",
    },
    "587": {
        "id": 587,
        "name": "HyperX Cloud II Gaming Headset Pro Edition",
        "price": 60824,
        "category": "gaming",
    },
    "588": {
        "id": 588,
        "name": "Ikea Study Table LINNMON Pro Edition",
        "price": 5070,
        "category": "home",
    },
    "589": {
        "id": 589,
        "name": "Havells Toaster 2024 Model",
        "price": 14677,
        "category": "kitchen",
    },
    "590": {
        "id": 590,
        "name": "Ikea Study Table LINNMON Black",
        "price": 20439,
        "category": "home",
    },
    "591": {
        "id": 591,
        "name": "Amazfit GTS 4 Silver",
        "price": 25517,
        "category": "electronics",
    },
    "592": {
        "id": 592,
        "name": "Noise ColorFit Ultra Silver",
        "price": 16935,
        "category": "electronics",
    },
    "593": {
        "id": 593,
        "name": "Philips LED Desk Lamp Pro Edition",
        "price": 39520,
        "category": "home",
    },
    "594": {
        "id": 594,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 6687,
        "category": "kitchen",
    },
    "595": {
        "id": 595,
        "name": "H&M Oversized Hoodie Pro Edition",
        "price": 7989,
        "category": "clothing",
    },
    "596": {
        "id": 596,
        "name": "Milton Thermosteel Bottle 1L Black",
        "price": 6980,
        "category": "kitchen",
    },
    "597": {
        "id": 597,
        "name": "Philips LED Desk Lamp Silver",
        "price": 26352,
        "category": "home",
    },
    "598": {
        "id": 598,
        "name": "Boat Stone 1000 Silver",
        "price": 74741,
        "category": "electronics",
    },
    "599": {
        "id": 599,
        "name": "Xbox Series X Black",
        "price": 60515,
        "category": "gaming",
    },
    "600": {
        "id": 600,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 65680,
        "category": "gaming",
    },
    "601": {
        "id": 601,
        "name": "H&M Oversized Hoodie Blue",
        "price": 4058,
        "category": "clothing",
    },
    "602": {
        "id": 602,
        "name": "Bosch Mixer Grinder Pro Edition",
        "price": 8695,
        "category": "kitchen",
    },
    "603": {
        "id": 603,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 49654,
        "category": "home",
    },
    "604": {
        "id": 604,
        "name": "Zara Slim Fit Blazer Black",
        "price": 4074,
        "category": "clothing",
    },
    "605": {
        "id": 605,
        "name": "Sony Bravia X80K Black",
        "price": 29986,
        "category": "electronics",
    },
    "606": {
        "id": 606,
        "name": "Apple Watch Series 9 Silver",
        "price": 112962,
        "category": "electronics",
    },
    "607": {
        "id": 607,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 65295,
        "category": "gaming",
    },
    "608": {
        "id": 608,
        "name": "Levi's 511 Slim Fit Jeans Silver",
        "price": 3670,
        "category": "clothing",
    },
    "609": {
        "id": 609,
        "name": "Philips Airfryer XL Silver",
        "price": 2380,
        "category": "kitchen",
    },
    "610": {
        "id": 610,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 7607,
        "category": "gaming",
    },
    "611": {
        "id": 611,
        "name": "Milton Thermosteel Bottle 1L",
        "price": 6201,
        "category": "kitchen",
    },
    "612": {
        "id": 612,
        "name": "Allen Solly Cotton Shirt Black",
        "price": 6539,
        "category": "clothing",
    },
    "613": {
        "id": 613,
        "name": "Sleepwell Memory Foam Mattress 2024 Model",
        "price": 10443,
        "category": "home",
    },
    "614": {
        "id": 614,
        "name": "Razer DeathAdder V3 Mouse",
        "price": 65942,
        "category": "gaming",
    },
    "615": {
        "id": 615,
        "name": "Xbox Series X Pro Edition",
        "price": 38342,
        "category": "gaming",
    },
    "616": {
        "id": 616,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 19798,
        "category": "gaming",
    },
    "617": {
        "id": 617,
        "name": "Bosch Mixer Grinder Silver",
        "price": 3883,
        "category": "kitchen",
    },
    "618": {
        "id": 618,
        "name": "LG C2 OLED TV Silver",
        "price": 93598,
        "category": "electronics",
    },
    "619": {
        "id": 619,
        "name": "Philips LED Desk Lamp Black",
        "price": 50257,
        "category": "home",
    },
    "620": {
        "id": 620,
        "name": "Ikea Study Table LINNMON Black",
        "price": 56076,
        "category": "home",
    },
    "621": {
        "id": 621,
        "name": "Google Pixel 8 Pro Silver",
        "price": 157099,
        "category": "electronics",
    },
    "622": {
        "id": 622,
        "name": "Philips Airfryer XL Black",
        "price": 15210,
        "category": "kitchen",
    },
    "623": {
        "id": 623,
        "name": "Havells Toaster 2024 Model",
        "price": 803,
        "category": "kitchen",
    },
    "624": {
        "id": 624,
        "name": "Sleepwell Memory Foam Mattress Black",
        "price": 9094,
        "category": "home",
    },
    "625": {
        "id": 625,
        "name": "Nike Air Max Shoes Black",
        "price": 5044,
        "category": "clothing",
    },
    "626": {
        "id": 626,
        "name": "Zara Slim Fit Blazer Pro Edition",
        "price": 1783,
        "category": "clothing",
    },
    "627": {
        "id": 627,
        "name": "Logitech G Pro X Keyboard",
        "price": 50013,
        "category": "gaming",
    },
    "628": {
        "id": 628,
        "name": "Google Pixel 8 Pro",
        "price": 38983,
        "category": "electronics",
    },
    "629": {
        "id": 629,
        "name": "Boat Rockerz 255 Pro+ 2024 Model",
        "price": 92127,
        "category": "electronics",
    },
    "630": {
        "id": 630,
        "name": "Razer DeathAdder V3 Mouse Blue",
        "price": 64894,
        "category": "gaming",
    },
    "631": {
        "id": 631,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 6731,
        "category": "home",
    },
    "632": {
        "id": 632,
        "name": "MacBook Pro 14-inch M3 Black",
        "price": 161737,
        "category": "electronics",
    },
    "633": {
        "id": 633,
        "name": "Milton Thermosteel Bottle 1L Blue",
        "price": 3451,
        "category": "kitchen",
    },
    "634": {
        "id": 634,
        "name": "Philips LED Desk Lamp 2024 Model",
        "price": 18653,
        "category": "home",
    },
    "635": {
        "id": 635,
        "name": "Havells Toaster 2024 Model",
        "price": 4921,
        "category": "kitchen",
    },
    "636": {
        "id": 636,
        "name": "Nothing Phone 2 Black",
        "price": 40565,
        "category": "electronics",
    },
    "637": {
        "id": 637,
        "name": "Bosch Mixer Grinder Blue",
        "price": 3795,
        "category": "kitchen",
    },
    "638": {
        "id": 638,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 36816,
        "category": "gaming",
    },
    "639": {
        "id": 639,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 37843,
        "category": "home",
    },
    "640": {
        "id": 640,
        "name": "Apple iPhone 15 Pro Silver",
        "price": 49327,
        "category": "electronics",
    },
    "641": {
        "id": 641,
        "name": "Bosch Mixer Grinder 2024 Model",
        "price": 2530,
        "category": "kitchen",
    },
    "642": {
        "id": 642,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 5815,
        "category": "home",
    },
    "643": {
        "id": 643,
        "name": "Milton Thermosteel Bottle 1L Black",
        "price": 16298,
        "category": "kitchen",
    },
    "644": {
        "id": 644,
        "name": "AmazonBasics Wall Clock Black",
        "price": 42330,
        "category": "home",
    },
    "645": {
        "id": 645,
        "name": "Zara Slim Fit Blazer Black",
        "price": 2235,
        "category": "clothing",
    },
    "646": {
        "id": 646,
        "name": "Apple AirPods Pro 2 2024 Model",
        "price": 156494,
        "category": "electronics",
    },
    "647": {
        "id": 647,
        "name": "Puma Running Shoes 2024 Model",
        "price": 2147,
        "category": "clothing",
    },
    "648": {
        "id": 648,
        "name": "Bosch Mixer Grinder Black",
        "price": 9816,
        "category": "kitchen",
    },
    "649": {
        "id": 649,
        "name": "Sony PlayStation 5 Black",
        "price": 4372,
        "category": "gaming",
    },
    "650": {
        "id": 650,
        "name": "Havells Toaster 2024 Model",
        "price": 7495,
        "category": "kitchen",
    },
    "651": {
        "id": 651,
        "name": "Razer DeathAdder V3 Mouse Pro Edition",
        "price": 58051,
        "category": "gaming",
    },
    "652": {
        "id": 652,
        "name": "Sony PlayStation 5",
        "price": 49221,
        "category": "gaming",
    },
    "653": {
        "id": 653,
        "name": "Havells Toaster Pro Edition",
        "price": 1764,
        "category": "kitchen",
    },
    "654": {
        "id": 654,
        "name": "Sony SRS-XB13 Black",
        "price": 158317,
        "category": "electronics",
    },
    "655": {
        "id": 655,
        "name": "Puma Running Shoes Pro Edition",
        "price": 5038,
        "category": "clothing",
    },
    "656": {
        "id": 656,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 12075,
        "category": "kitchen",
    },
    "657": {
        "id": 657,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 21098,
        "category": "home",
    },
    "658": {
        "id": 658,
        "name": "HyperX Cloud II Gaming Headset",
        "price": 44053,
        "category": "gaming",
    },
    "659": {
        "id": 659,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 31384,
        "category": "gaming",
    },
    "660": {
        "id": 660,
        "name": "Philips LED Desk Lamp 2024 Model",
        "price": 19571,
        "category": "home",
    },
    "661": {
        "id": 661,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 29818,
        "category": "home",
    },
    "662": {
        "id": 662,
        "name": "OnePlus 11R Black",
        "price": 32752,
        "category": "electronics",
    },
    "663": {
        "id": 663,
        "name": "Apple Watch Series 9 Pro Edition",
        "price": 58152,
        "category": "electronics",
    },
    "664": {
        "id": 664,
        "name": "Sony SRS-XB13 Silver",
        "price": 53383,
        "category": "electronics",
    },
    "665": {
        "id": 665,
        "name": "Philips LED Desk Lamp Silver",
        "price": 17042,
        "category": "home",
    },
    "666": {
        "id": 666,
        "name": "Xiaomi Smart TV 5A Pro Edition",
        "price": 15297,
        "category": "electronics",
    },
    "667": {
        "id": 667,
        "name": "Philips Airfryer XL Silver",
        "price": 9293,
        "category": "kitchen",
    },
    "668": {
        "id": 668,
        "name": "Nike Air Max Shoes",
        "price": 1306,
        "category": "clothing",
    },
    "669": {
        "id": 669,
        "name": "Zara Slim Fit Blazer 2024 Model",
        "price": 7683,
        "category": "clothing",
    },
    "670": {
        "id": 670,
        "name": "Puma Running Shoes 2024 Model",
        "price": 1302,
        "category": "clothing",
    },
    "671": {
        "id": 671,
        "name": "Asus ROG Strix G15 Pro Edition",
        "price": 69966,
        "category": "electronics",
    },
    "672": {
        "id": 672,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 2261,
        "category": "gaming",
    },
    "673": {
        "id": 673,
        "name": "H&M Oversized Hoodie Silver",
        "price": 766,
        "category": "clothing",
    },
    "674": {
        "id": 674,
        "name": "Logitech G Pro X Keyboard Silver",
        "price": 62236,
        "category": "gaming",
    },
    "675": {
        "id": 675,
        "name": "Apple AirPods Pro 2 2024 Model",
        "price": 37764,
        "category": "electronics",
    },
    "676": {
        "id": 676,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 17989,
        "category": "kitchen",
    },
    "677": {
        "id": 677,
        "name": "Xiaomi Smart TV 5A Black",
        "price": 93722,
        "category": "electronics",
    },
    "678": {
        "id": 678,
        "name": "Ikea Study Table LINNMON Blue",
        "price": 54030,
        "category": "home",
    },
    "679": {
        "id": 679,
        "name": "Levi's 511 Slim Fit Jeans Black",
        "price": 918,
        "category": "clothing",
    },
    "680": {
        "id": 680,
        "name": "JBL Tune 760NC Pro Edition",
        "price": 111276,
        "category": "electronics",
    },
    "681": {
        "id": 681,
        "name": "Xbox Series X Blue",
        "price": 35662,
        "category": "gaming",
    },
    "682": {
        "id": 682,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 1895,
        "category": "kitchen",
    },
    "683": {
        "id": 683,
        "name": "Sleepwell Memory Foam Mattress",
        "price": 22807,
        "category": "home",
    },
    "684": {
        "id": 684,
        "name": "Nintendo Switch OLED 2024 Model",
        "price": 44496,
        "category": "gaming",
    },
    "685": {
        "id": 685,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 35976,
        "category": "home",
    },
    "686": {
        "id": 686,
        "name": "Adidas Supercourt Sneakers Blue",
        "price": 6014,
        "category": "clothing",
    },
    "687": {
        "id": 687,
        "name": "JBL Flip 6 2024 Model",
        "price": 105644,
        "category": "electronics",
    },
    "688": {
        "id": 688,
        "name": "Nike Air Max Shoes Blue",
        "price": 2461,
        "category": "clothing",
    },
    "689": {
        "id": 689,
        "name": "Allen Solly Cotton Shirt",
        "price": 5940,
        "category": "clothing",
    },
    "690": {
        "id": 690,
        "name": "Milton Thermosteel Bottle 1L Blue",
        "price": 9564,
        "category": "kitchen",
    },
    "691": {
        "id": 691,
        "name": "Puma Running Shoes Silver",
        "price": 3518,
        "category": "clothing",
    },
    "692": {
        "id": 692,
        "name": "Philips LED Desk Lamp Blue",
        "price": 27281,
        "category": "home",
    },
    "693": {
        "id": 693,
        "name": "Milton Thermosteel Bottle 1L Blue",
        "price": 333,
        "category": "kitchen",
    },
    "694": {
        "id": 694,
        "name": "MSI Modern 14 Silver",
        "price": 38472,
        "category": "electronics",
    },
    "695": {
        "id": 695,
        "name": "AmazonBasics Wall Clock 2024 Model",
        "price": 15962,
        "category": "home",
    },
    "696": {
        "id": 696,
        "name": "Puma Running Shoes 2024 Model",
        "price": 5199,
        "category": "clothing",
    },
    "697": {
        "id": 697,
        "name": "Philips LED Desk Lamp",
        "price": 38248,
        "category": "home",
    },
    "698": {
        "id": 698,
        "name": "Nike Air Max Shoes Silver",
        "price": 4707,
        "category": "clothing",
    },
    "699": {
        "id": 699,
        "name": "Puma Running Shoes Blue",
        "price": 6661,
        "category": "clothing",
    },
    "700": {
        "id": 700,
        "name": "Razer DeathAdder V3 Mouse 2024 Model",
        "price": 32797,
        "category": "gaming",
    },
    "701": {
        "id": 701,
        "name": "Philips Airfryer XL Black",
        "price": 16614,
        "category": "kitchen",
    },
    "702": {
        "id": 702,
        "name": "Razer DeathAdder V3 Mouse Blue",
        "price": 58824,
        "category": "gaming",
    },
    "703": {
        "id": 703,
        "name": "H&M Oversized Hoodie Pro Edition",
        "price": 7566,
        "category": "clothing",
    },
    "704": {
        "id": 704,
        "name": "Havells Toaster",
        "price": 18028,
        "category": "kitchen",
    },
    "705": {
        "id": 705,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 14672,
        "category": "kitchen",
    },
    "706": {
        "id": 706,
        "name": "Levi's 511 Slim Fit Jeans",
        "price": 3364,
        "category": "clothing",
    },
    "707": {"id": 707, "name": "Havells Toaster", "price": 6765, "category": "kitchen"},
    "708": {
        "id": 708,
        "name": "Adidas Supercourt Sneakers Pro Edition",
        "price": 4911,
        "category": "clothing",
    },
    "709": {
        "id": 709,
        "name": "Sony PlayStation 5 Silver",
        "price": 29124,
        "category": "gaming",
    },
    "710": {
        "id": 710,
        "name": "Logitech G Pro X Keyboard",
        "price": 10531,
        "category": "gaming",
    },
    "711": {
        "id": 711,
        "name": "Bosch Mixer Grinder Pro Edition",
        "price": 14922,
        "category": "kitchen",
    },
    "712": {
        "id": 712,
        "name": "Apple iPhone 15 Pro Black",
        "price": 52202,
        "category": "electronics",
    },
    "713": {
        "id": 713,
        "name": "Nintendo Switch OLED Blue",
        "price": 59884,
        "category": "gaming",
    },
    "714": {
        "id": 714,
        "name": "Havells Toaster Silver",
        "price": 18894,
        "category": "kitchen",
    },
    "715": {
        "id": 715,
        "name": "TCL Mini LED TV Pro Edition",
        "price": 131284,
        "category": "electronics",
    },
    "716": {
        "id": 716,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 9243,
        "category": "kitchen",
    },
    "717": {
        "id": 717,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 10758,
        "category": "kitchen",
    },
    "718": {
        "id": 718,
        "name": "Bosch Mixer Grinder Silver",
        "price": 12327,
        "category": "kitchen",
    },
    "719": {
        "id": 719,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 47890,
        "category": "home",
    },
    "720": {
        "id": 720,
        "name": "HyperX Cloud II Gaming Headset 2024 Model",
        "price": 42768,
        "category": "gaming",
    },
    "721": {
        "id": 721,
        "name": "Havells Toaster 2024 Model",
        "price": 6730,
        "category": "kitchen",
    },
    "722": {
        "id": 722,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 13327,
        "category": "kitchen",
    },
    "723": {
        "id": 723,
        "name": "HyperX Cloud II Gaming Headset Blue",
        "price": 9279,
        "category": "gaming",
    },
    "724": {
        "id": 724,
        "name": "Zara Slim Fit Blazer Blue",
        "price": 3212,
        "category": "clothing",
    },
    "725": {
        "id": 725,
        "name": "Puma Running Shoes Black",
        "price": 5034,
        "category": "clothing",
    },
    "726": {
        "id": 726,
        "name": "Allen Solly Cotton Shirt Silver",
        "price": 3431,
        "category": "clothing",
    },
    "727": {
        "id": 727,
        "name": "Havells Toaster 2024 Model",
        "price": 6443,
        "category": "kitchen",
    },
    "728": {
        "id": 728,
        "name": "Allen Solly Cotton Shirt Blue",
        "price": 7005,
        "category": "clothing",
    },
    "729": {
        "id": 729,
        "name": "Prestige Pressure Cooker Blue",
        "price": 19067,
        "category": "kitchen",
    },
    "730": {
        "id": 730,
        "name": "H&M Oversized Hoodie Black",
        "price": 514,
        "category": "clothing",
    },
    "731": {
        "id": 731,
        "name": "Philips LED Desk Lamp Silver",
        "price": 55943,
        "category": "home",
    },
    "732": {
        "id": 732,
        "name": "Bosch Mixer Grinder",
        "price": 12466,
        "category": "kitchen",
    },
    "733": {
        "id": 733,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 54292,
        "category": "home",
    },
    "734": {
        "id": 734,
        "name": "Apple Watch Series 9 Blue",
        "price": 124804,
        "category": "electronics",
    },
    "735": {
        "id": 735,
        "name": "Adidas Supercourt Sneakers Pro Edition",
        "price": 4068,
        "category": "clothing",
    },
    "736": {
        "id": 736,
        "name": "Nintendo Switch OLED Black",
        "price": 36847,
        "category": "gaming",
    },
    "737": {
        "id": 737,
        "name": "Puma Running Shoes Silver",
        "price": 4394,
        "category": "clothing",
    },
    "738": {
        "id": 738,
        "name": "Adidas Supercourt Sneakers Blue",
        "price": 5399,
        "category": "clothing",
    },
    "739": {
        "id": 739,
        "name": "Apple iPhone 15 Pro Blue",
        "price": 31926,
        "category": "electronics",
    },
    "740": {
        "id": 740,
        "name": "Ikea Study Table LINNMON",
        "price": 50960,
        "category": "home",
    },
    "741": {
        "id": 741,
        "name": "Apple iPhone 14",
        "price": 144369,
        "category": "electronics",
    },
    "742": {
        "id": 742,
        "name": "HyperX Cloud II Gaming Headset Blue",
        "price": 59243,
        "category": "gaming",
    },
    "743": {
        "id": 743,
        "name": "Prestige Pressure Cooker Silver",
        "price": 7512,
        "category": "kitchen",
    },
    "744": {
        "id": 744,
        "name": "Amazfit GTS 4 Silver",
        "price": 135487,
        "category": "electronics",
    },
    "745": {
        "id": 745,
        "name": "Zara Slim Fit Blazer Black",
        "price": 7798,
        "category": "clothing",
    },
    "746": {
        "id": 746,
        "name": "JBL Tune 760NC Blue",
        "price": 150660,
        "category": "electronics",
    },
    "747": {
        "id": 747,
        "name": "Nintendo Switch OLED Blue",
        "price": 67438,
        "category": "gaming",
    },
    "748": {
        "id": 748,
        "name": "Logitech G Pro X Keyboard Black",
        "price": 43265,
        "category": "gaming",
    },
    "749": {
        "id": 749,
        "name": "HyperX Cloud II Gaming Headset Silver",
        "price": 28231,
        "category": "gaming",
    },
    "750": {
        "id": 750,
        "name": "Boat Rockerz 255 Pro+ Pro Edition",
        "price": 121014,
        "category": "electronics",
    },
    "751": {
        "id": 751,
        "name": "Zara Slim Fit Blazer Pro Edition",
        "price": 6447,
        "category": "clothing",
    },
    "752": {
        "id": 752,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 1746,
        "category": "kitchen",
    },
    "753": {
        "id": 753,
        "name": "Havells Toaster Pro Edition",
        "price": 9657,
        "category": "kitchen",
    },
    "754": {
        "id": 754,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 30872,
        "category": "home",
    },
    "755": {
        "id": 755,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 27925,
        "category": "home",
    },
    "756": {
        "id": 756,
        "name": "Prestige Pressure Cooker Silver",
        "price": 2524,
        "category": "kitchen",
    },
    "757": {
        "id": 757,
        "name": "Sony PlayStation 5",
        "price": 6219,
        "category": "gaming",
    },
    "758": {
        "id": 758,
        "name": "Levi's 511 Slim Fit Jeans 2024 Model",
        "price": 6363,
        "category": "clothing",
    },
    "759": {
        "id": 759,
        "name": "Samsung Galaxy Buds2 Pro Silver",
        "price": 38722,
        "category": "electronics",
    },
    "760": {
        "id": 760,
        "name": "Philips LED Desk Lamp",
        "price": 55254,
        "category": "home",
    },
    "761": {
        "id": 761,
        "name": "Havells Toaster Silver",
        "price": 14533,
        "category": "kitchen",
    },
    "762": {
        "id": 762,
        "name": "Sony PlayStation 5 Silver",
        "price": 5959,
        "category": "gaming",
    },
    "763": {
        "id": 763,
        "name": "Bosch Mixer Grinder Silver",
        "price": 18374,
        "category": "kitchen",
    },
    "764": {
        "id": 764,
        "name": "Havells Toaster Pro Edition",
        "price": 10888,
        "category": "kitchen",
    },
    "765": {
        "id": 765,
        "name": "Philips Airfryer XL Black",
        "price": 2161,
        "category": "kitchen",
    },
    "766": {
        "id": 766,
        "name": "Philips Airfryer XL Blue",
        "price": 6076,
        "category": "kitchen",
    },
    "767": {
        "id": 767,
        "name": "Philips LED Desk Lamp Silver",
        "price": 2851,
        "category": "home",
    },
    "768": {
        "id": 768,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 16782,
        "category": "kitchen",
    },
    "769": {
        "id": 769,
        "name": "Philips Airfryer XL",
        "price": 19759,
        "category": "kitchen",
    },
    "770": {
        "id": 770,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 36292,
        "category": "gaming",
    },
    "771": {
        "id": 771,
        "name": "Nintendo Switch OLED Silver",
        "price": 26135,
        "category": "gaming",
    },
    "772": {
        "id": 772,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 47632,
        "category": "gaming",
    },
    "773": {
        "id": 773,
        "name": "Samsung Galaxy Book 3",
        "price": 96776,
        "category": "electronics",
    },
    "774": {
        "id": 774,
        "name": "Nike Air Max Shoes Black",
        "price": 2993,
        "category": "clothing",
    },
    "775": {
        "id": 775,
        "name": "Philips LED Desk Lamp Silver",
        "price": 35868,
        "category": "home",
    },
    "776": {
        "id": 776,
        "name": "Ikea Study Table LINNMON",
        "price": 9759,
        "category": "home",
    },
    "777": {"id": 777, "name": "Xbox Series X", "price": 23746, "category": "gaming"},
    "778": {
        "id": 778,
        "name": "Amazfit GTS 4",
        "price": 173072,
        "category": "electronics",
    },
    "779": {
        "id": 779,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 56499,
        "category": "home",
    },
    "780": {
        "id": 780,
        "name": "H&M Oversized Hoodie Pro Edition",
        "price": 2320,
        "category": "clothing",
    },
    "781": {
        "id": 781,
        "name": "HyperX Cloud II Gaming Headset",
        "price": 38962,
        "category": "gaming",
    },
    "782": {
        "id": 782,
        "name": "Philips Airfryer XL 2024 Model",
        "price": 15647,
        "category": "kitchen",
    },
    "783": {"id": 783, "name": "JBL Flip 6", "price": 69708, "category": "electronics"},
    "784": {
        "id": 784,
        "name": "Allen Solly Cotton Shirt 2024 Model",
        "price": 7345,
        "category": "clothing",
    },
    "785": {
        "id": 785,
        "name": "AmazonBasics Wall Clock Black",
        "price": 17820,
        "category": "home",
    },
    "786": {
        "id": 786,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 5616,
        "category": "home",
    },
    "787": {
        "id": 787,
        "name": "Sony WH-1000XM5 Pro Edition",
        "price": 8942,
        "category": "electronics",
    },
    "788": {
        "id": 788,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 54196,
        "category": "gaming",
    },
    "789": {
        "id": 789,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 1586,
        "category": "kitchen",
    },
    "790": {
        "id": 790,
        "name": "Noise ColorFit Ultra Pro Edition",
        "price": 78797,
        "category": "electronics",
    },
    "791": {
        "id": 791,
        "name": "Logitech G Pro X Keyboard Pro Edition",
        "price": 69673,
        "category": "gaming",
    },
    "792": {
        "id": 792,
        "name": "Lenovo ThinkPad X1 Carbon Pro Edition",
        "price": 43363,
        "category": "electronics",
    },
    "793": {
        "id": 793,
        "name": "Nike Air Max Shoes Silver",
        "price": 3681,
        "category": "clothing",
    },
    "794": {
        "id": 794,
        "name": "Sleepwell Memory Foam Mattress",
        "price": 37544,
        "category": "home",
    },
    "795": {
        "id": 795,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 7132,
        "category": "kitchen",
    },
    "796": {
        "id": 796,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 7369,
        "category": "kitchen",
    },
    "797": {
        "id": 797,
        "name": "Nike Air Max Shoes Silver",
        "price": 7773,
        "category": "clothing",
    },
    "798": {
        "id": 798,
        "name": "Philips LED Desk Lamp",
        "price": 12717,
        "category": "home",
    },
    "799": {
        "id": 799,
        "name": "Logitech G Pro X Keyboard Blue",
        "price": 48956,
        "category": "gaming",
    },
    "800": {
        "id": 800,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 6821,
        "category": "home",
    },
    "801": {
        "id": 801,
        "name": "Sony PlayStation 5 Pro Edition",
        "price": 47885,
        "category": "gaming",
    },
    "802": {
        "id": 802,
        "name": "Bosch Mixer Grinder Black",
        "price": 10405,
        "category": "kitchen",
    },
    "803": {
        "id": 803,
        "name": "Levi's 511 Slim Fit Jeans 2024 Model",
        "price": 4677,
        "category": "clothing",
    },
    "804": {
        "id": 804,
        "name": "Havells Toaster Pro Edition",
        "price": 7687,
        "category": "kitchen",
    },
    "805": {
        "id": 805,
        "name": "Noise ColorFit Ultra",
        "price": 78412,
        "category": "electronics",
    },
    "806": {
        "id": 806,
        "name": "H&M Oversized Hoodie Silver",
        "price": 6098,
        "category": "clothing",
    },
    "807": {
        "id": 807,
        "name": "Havells Toaster 2024 Model",
        "price": 19183,
        "category": "kitchen",
    },
    "808": {
        "id": 808,
        "name": "MSI Modern 14 Silver",
        "price": 162921,
        "category": "electronics",
    },
    "809": {
        "id": 809,
        "name": "Marshall Emberton Pro Edition",
        "price": 74288,
        "category": "electronics",
    },
    "810": {
        "id": 810,
        "name": "Bosch Mixer Grinder Blue",
        "price": 5104,
        "category": "kitchen",
    },
    "811": {
        "id": 811,
        "name": "Prestige Pressure Cooker Black",
        "price": 4369,
        "category": "kitchen",
    },
    "812": {
        "id": 812,
        "name": "Philips LED Desk Lamp Blue",
        "price": 52103,
        "category": "home",
    },
    "813": {
        "id": 813,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 18348,
        "category": "gaming",
    },
    "814": {
        "id": 814,
        "name": "Havells Toaster Blue",
        "price": 11824,
        "category": "kitchen",
    },
    "815": {
        "id": 815,
        "name": "Philips LED Desk Lamp",
        "price": 1302,
        "category": "home",
    },
    "816": {
        "id": 816,
        "name": "Sony PlayStation 5 2024 Model",
        "price": 9789,
        "category": "gaming",
    },
    "817": {"id": 817, "name": "Havells Toaster", "price": 6026, "category": "kitchen"},
    "818": {
        "id": 818,
        "name": "Havells Toaster 2024 Model",
        "price": 1820,
        "category": "kitchen",
    },
    "819": {
        "id": 819,
        "name": "Philips Airfryer XL",
        "price": 13348,
        "category": "kitchen",
    },
    "820": {
        "id": 820,
        "name": "Dyson V12 Vacuum Cleaner Blue",
        "price": 13143,
        "category": "home",
    },
    "821": {
        "id": 821,
        "name": "Sleepwell Memory Foam Mattress Silver",
        "price": 45912,
        "category": "home",
    },
    "822": {
        "id": 822,
        "name": "Dyson V12 Vacuum Cleaner",
        "price": 5537,
        "category": "home",
    },
    "823": {
        "id": 823,
        "name": "Levi's 511 Slim Fit Jeans Black",
        "price": 4897,
        "category": "clothing",
    },
    "824": {
        "id": 824,
        "name": "Philips Airfryer XL Blue",
        "price": 19611,
        "category": "kitchen",
    },
    "825": {
        "id": 825,
        "name": "Sony PlayStation 5",
        "price": 61649,
        "category": "gaming",
    },
    "826": {
        "id": 826,
        "name": "HyperX Cloud II Gaming Headset",
        "price": 44628,
        "category": "gaming",
    },
    "827": {
        "id": 827,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 8999,
        "category": "home",
    },
    "828": {
        "id": 828,
        "name": "Sleepwell Memory Foam Mattress Silver",
        "price": 54492,
        "category": "home",
    },
    "829": {
        "id": 829,
        "name": "Puma Running Shoes Blue",
        "price": 750,
        "category": "clothing",
    },
    "830": {
        "id": 830,
        "name": "Zara Slim Fit Blazer Silver",
        "price": 5054,
        "category": "clothing",
    },
    "831": {
        "id": 831,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 45099,
        "category": "home",
    },
    "832": {
        "id": 832,
        "name": "Google Pixel 8 Pro",
        "price": 133718,
        "category": "electronics",
    },
    "833": {
        "id": 833,
        "name": "Asus ROG Strix G15 Silver",
        "price": 83526,
        "category": "electronics",
    },
    "834": {
        "id": 834,
        "name": "Havells Toaster Blue",
        "price": 19697,
        "category": "kitchen",
    },
    "835": {
        "id": 835,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 55978,
        "category": "home",
    },
    "836": {
        "id": 836,
        "name": "Sleepwell Memory Foam Mattress Blue",
        "price": 50355,
        "category": "home",
    },
    "837": {
        "id": 837,
        "name": "Realme GT Neo 3",
        "price": 163115,
        "category": "electronics",
    },
    "838": {
        "id": 838,
        "name": "Nintendo Switch OLED Pro Edition",
        "price": 64710,
        "category": "gaming",
    },
    "839": {
        "id": 839,
        "name": "Razer DeathAdder V3 Mouse Pro Edition",
        "price": 65848,
        "category": "gaming",
    },
    "840": {
        "id": 840,
        "name": "Xbox Series X Pro Edition",
        "price": 31310,
        "category": "gaming",
    },
    "841": {
        "id": 841,
        "name": "Nike Air Max Shoes Pro Edition",
        "price": 6228,
        "category": "clothing",
    },
    "842": {
        "id": 842,
        "name": "Philips LED Desk Lamp Black",
        "price": 43860,
        "category": "home",
    },
    "843": {
        "id": 843,
        "name": "Nike Air Max Shoes Black",
        "price": 3907,
        "category": "clothing",
    },
    "844": {
        "id": 844,
        "name": "AmazonBasics Wall Clock Blue",
        "price": 32677,
        "category": "home",
    },
    "845": {
        "id": 845,
        "name": "Havells Toaster Blue",
        "price": 16920,
        "category": "kitchen",
    },
    "846": {
        "id": 846,
        "name": "Sleepwell Memory Foam Mattress 2024 Model",
        "price": 44632,
        "category": "home",
    },
    "847": {
        "id": 847,
        "name": "Levi's 511 Slim Fit Jeans Blue",
        "price": 975,
        "category": "clothing",
    },
    "848": {
        "id": 848,
        "name": "Bosch Mixer Grinder Pro Edition",
        "price": 9579,
        "category": "kitchen",
    },
    "849": {
        "id": 849,
        "name": "Sony WH-1000XM5 Black",
        "price": 100950,
        "category": "electronics",
    },
    "850": {
        "id": 850,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 1753,
        "category": "home",
    },
    "851": {
        "id": 851,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 2955,
        "category": "kitchen",
    },
    "852": {
        "id": 852,
        "name": 'Samsung Neo QLED 55"',
        "price": 89571,
        "category": "electronics",
    },
    "853": {"id": 853, "name": "Xbox Series X", "price": 62666, "category": "gaming"},
    "854": {
        "id": 854,
        "name": "Ikea Study Table LINNMON Pro Edition",
        "price": 23585,
        "category": "home",
    },
    "855": {
        "id": 855,
        "name": "Ikea Study Table LINNMON",
        "price": 12403,
        "category": "home",
    },
    "856": {
        "id": 856,
        "name": "Puma Running Shoes",
        "price": 800,
        "category": "clothing",
    },
    "857": {
        "id": 857,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 14088,
        "category": "kitchen",
    },
    "858": {
        "id": 858,
        "name": "Dyson V12 Vacuum Cleaner Blue",
        "price": 22122,
        "category": "home",
    },
    "859": {
        "id": 859,
        "name": "Ikea Study Table LINNMON Black",
        "price": 10354,
        "category": "home",
    },
    "860": {
        "id": 860,
        "name": "Adidas Supercourt Sneakers Black",
        "price": 2985,
        "category": "clothing",
    },
    "861": {
        "id": 861,
        "name": "Logitech G Pro X Keyboard",
        "price": 12926,
        "category": "gaming",
    },
    "862": {
        "id": 862,
        "name": "Lenovo ThinkPad X1 Carbon Black",
        "price": 174949,
        "category": "electronics",
    },
    "863": {
        "id": 863,
        "name": "Xbox Series X Black",
        "price": 1764,
        "category": "gaming",
    },
    "864": {
        "id": 864,
        "name": "Apple iPhone 15 Pro",
        "price": 55922,
        "category": "electronics",
    },
    "865": {
        "id": 865,
        "name": "Havells Toaster Blue",
        "price": 14058,
        "category": "kitchen",
    },
    "866": {
        "id": 866,
        "name": "Ikea Study Table LINNMON Black",
        "price": 42203,
        "category": "home",
    },
    "867": {
        "id": 867,
        "name": "AmazonBasics Wall Clock",
        "price": 58368,
        "category": "home",
    },
    "868": {
        "id": 868,
        "name": "OnePlus 11R Black",
        "price": 16410,
        "category": "electronics",
    },
    "869": {
        "id": 869,
        "name": "Razer DeathAdder V3 Mouse 2024 Model",
        "price": 10919,
        "category": "gaming",
    },
    "870": {
        "id": 870,
        "name": "Philips LED Desk Lamp Silver",
        "price": 15984,
        "category": "home",
    },
    "871": {
        "id": 871,
        "name": "Adidas Supercourt Sneakers Blue",
        "price": 4130,
        "category": "clothing",
    },
    "872": {
        "id": 872,
        "name": "Adidas Supercourt Sneakers Black",
        "price": 5965,
        "category": "clothing",
    },
    "873": {
        "id": 873,
        "name": "Zara Slim Fit Blazer Pro Edition",
        "price": 3575,
        "category": "clothing",
    },
    "874": {
        "id": 874,
        "name": "HyperX Cloud II Gaming Headset Blue",
        "price": 7542,
        "category": "gaming",
    },
    "875": {
        "id": 875,
        "name": "Nintendo Switch OLED Blue",
        "price": 12855,
        "category": "gaming",
    },
    "876": {
        "id": 876,
        "name": "Philips LED Desk Lamp Pro Edition",
        "price": 13476,
        "category": "home",
    },
    "877": {
        "id": 877,
        "name": "Philips Airfryer XL Blue",
        "price": 9114,
        "category": "kitchen",
    },
    "878": {
        "id": 878,
        "name": "Havells Toaster Silver",
        "price": 13463,
        "category": "kitchen",
    },
    "879": {
        "id": 879,
        "name": "Dell XPS 13 Pro Edition",
        "price": 148248,
        "category": "electronics",
    },
    "880": {
        "id": 880,
        "name": "Allen Solly Cotton Shirt",
        "price": 1351,
        "category": "clothing",
    },
    "881": {
        "id": 881,
        "name": "Zara Slim Fit Blazer Silver",
        "price": 4628,
        "category": "clothing",
    },
    "882": {
        "id": 882,
        "name": "Samsung Galaxy Watch 6 Blue",
        "price": 45409,
        "category": "electronics",
    },
    "883": {
        "id": 883,
        "name": "Allen Solly Cotton Shirt Pro Edition",
        "price": 6849,
        "category": "clothing",
    },
    "884": {
        "id": 884,
        "name": "MSI Modern 14 Blue",
        "price": 57036,
        "category": "electronics",
    },
    "885": {
        "id": 885,
        "name": "Nintendo Switch OLED",
        "price": 46352,
        "category": "gaming",
    },
    "886": {
        "id": 886,
        "name": "Sony PlayStation 5 Silver",
        "price": 34500,
        "category": "gaming",
    },
    "887": {
        "id": 887,
        "name": "MSI Modern 14",
        "price": 19187,
        "category": "electronics",
    },
    "888": {
        "id": 888,
        "name": "Bosch Mixer Grinder Pro Edition",
        "price": 527,
        "category": "kitchen",
    },
    "889": {
        "id": 889,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 45093,
        "category": "home",
    },
    "890": {
        "id": 890,
        "name": "Razer DeathAdder V3 Mouse 2024 Model",
        "price": 28143,
        "category": "gaming",
    },
    "891": {
        "id": 891,
        "name": "Puma Running Shoes Silver",
        "price": 6759,
        "category": "clothing",
    },
    "892": {
        "id": 892,
        "name": "Apple AirPods Pro 2 Pro Edition",
        "price": 128340,
        "category": "electronics",
    },
    "893": {
        "id": 893,
        "name": "Philips Airfryer XL Blue",
        "price": 10154,
        "category": "kitchen",
    },
    "894": {
        "id": 894,
        "name": "Dell XPS 13 Blue",
        "price": 132866,
        "category": "electronics",
    },
    "895": {
        "id": 895,
        "name": "H&M Oversized Hoodie Blue",
        "price": 7475,
        "category": "clothing",
    },
    "896": {
        "id": 896,
        "name": "Noise ColorFit Ultra",
        "price": 140118,
        "category": "electronics",
    },
    "897": {
        "id": 897,
        "name": "Sony Bravia X80K",
        "price": 136618,
        "category": "electronics",
    },
    "898": {
        "id": 898,
        "name": "Prestige Pressure Cooker Pro Edition",
        "price": 2402,
        "category": "kitchen",
    },
    "899": {
        "id": 899,
        "name": "Dyson V12 Vacuum Cleaner Blue",
        "price": 40364,
        "category": "home",
    },
    "900": {
        "id": 900,
        "name": "AmazonBasics Wall Clock Black",
        "price": 52368,
        "category": "home",
    },
    "901": {
        "id": 901,
        "name": "Milton Thermosteel Bottle 1L",
        "price": 5688,
        "category": "kitchen",
    },
    "902": {
        "id": 902,
        "name": "H&M Oversized Hoodie 2024 Model",
        "price": 7050,
        "category": "clothing",
    },
    "903": {
        "id": 903,
        "name": "JBL Tune 760NC Black",
        "price": 58707,
        "category": "electronics",
    },
    "904": {
        "id": 904,
        "name": "Bose QuietComfort 45",
        "price": 11447,
        "category": "electronics",
    },
    "905": {
        "id": 905,
        "name": "HyperX Cloud II Gaming Headset",
        "price": 38526,
        "category": "gaming",
    },
    "906": {
        "id": 906,
        "name": "Xbox Series X Pro Edition",
        "price": 40905,
        "category": "gaming",
    },
    "907": {
        "id": 907,
        "name": "Bosch Mixer Grinder Black",
        "price": 8547,
        "category": "kitchen",
    },
    "908": {
        "id": 908,
        "name": "Samsung Galaxy S23 Ultra Blue",
        "price": 126253,
        "category": "electronics",
    },
    "909": {
        "id": 909,
        "name": "Boat Rockerz 255 Pro+",
        "price": 35316,
        "category": "electronics",
    },
    "910": {
        "id": 910,
        "name": "Realme GT Neo 3 Blue",
        "price": 141688,
        "category": "electronics",
    },
    "911": {
        "id": 911,
        "name": "Logitech G Pro X Keyboard 2024 Model",
        "price": 35078,
        "category": "gaming",
    },
    "912": {
        "id": 912,
        "name": "HyperX Cloud II Gaming Headset Silver",
        "price": 53169,
        "category": "gaming",
    },
    "913": {
        "id": 913,
        "name": "Milton Thermosteel Bottle 1L Blue",
        "price": 13411,
        "category": "kitchen",
    },
    "914": {
        "id": 914,
        "name": "Sony SRS-XB13 Pro Edition",
        "price": 68254,
        "category": "electronics",
    },
    "915": {
        "id": 915,
        "name": "Zara Slim Fit Blazer 2024 Model",
        "price": 3002,
        "category": "clothing",
    },
    "916": {
        "id": 916,
        "name": "HyperX Cloud II Gaming Headset Black",
        "price": 32379,
        "category": "gaming",
    },
    "917": {
        "id": 917,
        "name": "Apple Watch Series 9 Blue",
        "price": 137332,
        "category": "electronics",
    },
    "918": {
        "id": 918,
        "name": "AmazonBasics Wall Clock Silver",
        "price": 36630,
        "category": "home",
    },
    "919": {
        "id": 919,
        "name": "Sony Bravia X80K 2024 Model",
        "price": 71021,
        "category": "electronics",
    },
    "920": {
        "id": 920,
        "name": "Prestige Pressure Cooker 2024 Model",
        "price": 3848,
        "category": "kitchen",
    },
    "921": {
        "id": 921,
        "name": "Philips LED Desk Lamp Silver",
        "price": 54993,
        "category": "home",
    },
    "922": {
        "id": 922,
        "name": "LG C2 OLED TV",
        "price": 27213,
        "category": "electronics",
    },
    "923": {
        "id": 923,
        "name": "Razer DeathAdder V3 Mouse 2024 Model",
        "price": 20136,
        "category": "gaming",
    },
    "924": {
        "id": 924,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 4988,
        "category": "home",
    },
    "925": {
        "id": 925,
        "name": "Xiaomi Smart TV 5A Pro Edition",
        "price": 98672,
        "category": "electronics",
    },
    "926": {
        "id": 926,
        "name": "Sony PlayStation 5 Black",
        "price": 11838,
        "category": "gaming",
    },
    "927": {
        "id": 927,
        "name": "Milton Thermosteel Bottle 1L Silver",
        "price": 5254,
        "category": "kitchen",
    },
    "928": {
        "id": 928,
        "name": "Nintendo Switch OLED 2024 Model",
        "price": 29783,
        "category": "gaming",
    },
    "929": {
        "id": 929,
        "name": "Ikea Study Table LINNMON Black",
        "price": 43180,
        "category": "home",
    },
    "930": {
        "id": 930,
        "name": "Zara Slim Fit Blazer Blue",
        "price": 5215,
        "category": "clothing",
    },
    "931": {
        "id": 931,
        "name": "Nike Air Max Shoes Silver",
        "price": 4736,
        "category": "clothing",
    },
    "932": {
        "id": 932,
        "name": "Google Pixel 8 Pro 2024 Model",
        "price": 117598,
        "category": "electronics",
    },
    "933": {
        "id": 933,
        "name": "Samsung Galaxy Watch 6 Silver",
        "price": 44567,
        "category": "electronics",
    },
    "934": {
        "id": 934,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 52516,
        "category": "home",
    },
    "935": {
        "id": 935,
        "name": "Allen Solly Cotton Shirt Pro Edition",
        "price": 1155,
        "category": "clothing",
    },
    "936": {
        "id": 936,
        "name": "Allen Solly Cotton Shirt Blue",
        "price": 4088,
        "category": "clothing",
    },
    "937": {
        "id": 937,
        "name": "Philips Airfryer XL Black",
        "price": 1661,
        "category": "kitchen",
    },
    "938": {
        "id": 938,
        "name": "Sony PlayStation 5 Silver",
        "price": 29021,
        "category": "gaming",
    },
    "939": {
        "id": 939,
        "name": "Xbox Series X 2024 Model",
        "price": 36191,
        "category": "gaming",
    },
    "940": {
        "id": 940,
        "name": "Havells Toaster Black",
        "price": 9932,
        "category": "kitchen",
    },
    "941": {
        "id": 941,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 31187,
        "category": "home",
    },
    "942": {
        "id": 942,
        "name": "Philips LED Desk Lamp",
        "price": 29691,
        "category": "home",
    },
    "943": {
        "id": 943,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 7964,
        "category": "home",
    },
    "944": {
        "id": 944,
        "name": "Allen Solly Cotton Shirt Blue",
        "price": 880,
        "category": "clothing",
    },
    "945": {
        "id": 945,
        "name": "Samsung Galaxy S23 Ultra 2024 Model",
        "price": 50999,
        "category": "electronics",
    },
    "946": {
        "id": 946,
        "name": "Sony PlayStation 5 Pro Edition",
        "price": 22409,
        "category": "gaming",
    },
    "947": {
        "id": 947,
        "name": "Asus ROG Strix G15 Pro Edition",
        "price": 152016,
        "category": "electronics",
    },
    "948": {
        "id": 948,
        "name": "Bosch Mixer Grinder Black",
        "price": 2809,
        "category": "kitchen",
    },
    "949": {
        "id": 949,
        "name": "Nintendo Switch OLED 2024 Model",
        "price": 62449,
        "category": "gaming",
    },
    "950": {
        "id": 950,
        "name": "Sleepwell Memory Foam Mattress Pro Edition",
        "price": 43256,
        "category": "home",
    },
    "951": {
        "id": 951,
        "name": "Nintendo Switch OLED 2024 Model",
        "price": 29403,
        "category": "gaming",
    },
    "952": {
        "id": 952,
        "name": 'Samsung Neo QLED 55"',
        "price": 172788,
        "category": "electronics",
    },
    "953": {
        "id": 953,
        "name": "Bosch Mixer Grinder Blue",
        "price": 11205,
        "category": "kitchen",
    },
    "954": {
        "id": 954,
        "name": "Philips Airfryer XL Blue",
        "price": 16916,
        "category": "kitchen",
    },
    "955": {
        "id": 955,
        "name": "Sony PlayStation 5 Blue",
        "price": 65049,
        "category": "gaming",
    },
    "956": {
        "id": 956,
        "name": "Philips Airfryer XL Pro Edition",
        "price": 3886,
        "category": "kitchen",
    },
    "957": {
        "id": 957,
        "name": "Allen Solly Cotton Shirt",
        "price": 1139,
        "category": "clothing",
    },
    "958": {
        "id": 958,
        "name": "Nintendo Switch OLED Silver",
        "price": 54227,
        "category": "gaming",
    },
    "959": {
        "id": 959,
        "name": "Dell XPS 13",
        "price": 67669,
        "category": "electronics",
    },
    "960": {
        "id": 960,
        "name": "Levi's 511 Slim Fit Jeans Silver",
        "price": 1205,
        "category": "clothing",
    },
    "961": {
        "id": 961,
        "name": "Ikea Study Table LINNMON Silver",
        "price": 41117,
        "category": "home",
    },
    "962": {
        "id": 962,
        "name": "AmazonBasics Wall Clock 2024 Model",
        "price": 59257,
        "category": "home",
    },
    "963": {
        "id": 963,
        "name": "Sony PlayStation 5 Blue",
        "price": 25245,
        "category": "gaming",
    },
    "964": {
        "id": 964,
        "name": "Sony WH-1000XM5 Blue",
        "price": 71829,
        "category": "electronics",
    },
    "965": {
        "id": 965,
        "name": "Dyson V12 Vacuum Cleaner Pro Edition",
        "price": 59775,
        "category": "home",
    },
    "966": {
        "id": 966,
        "name": "Adidas Supercourt Sneakers Silver",
        "price": 1922,
        "category": "clothing",
    },
    "967": {
        "id": 967,
        "name": "Logitech G Pro X Keyboard",
        "price": 9639,
        "category": "gaming",
    },
    "968": {
        "id": 968,
        "name": "Nike Air Max Shoes Silver",
        "price": 3001,
        "category": "clothing",
    },
    "969": {
        "id": 969,
        "name": "Razer DeathAdder V3 Mouse Blue",
        "price": 6966,
        "category": "gaming",
    },
    "970": {
        "id": 970,
        "name": "Acer Aspire 7 2024 Model",
        "price": 160483,
        "category": "electronics",
    },
    "971": {
        "id": 971,
        "name": "H&M Oversized Hoodie Pro Edition",
        "price": 6985,
        "category": "clothing",
    },
    "972": {
        "id": 972,
        "name": "Razer DeathAdder V3 Mouse Pro Edition",
        "price": 6680,
        "category": "gaming",
    },
    "973": {
        "id": 973,
        "name": "Samsung Galaxy Buds2 Pro Pro Edition",
        "price": 28149,
        "category": "electronics",
    },
    "974": {
        "id": 974,
        "name": "Sony PlayStation 5 Silver",
        "price": 43633,
        "category": "gaming",
    },
    "975": {
        "id": 975,
        "name": "Adidas Supercourt Sneakers Silver",
        "price": 3386,
        "category": "clothing",
    },
    "976": {
        "id": 976,
        "name": "Milton Thermosteel Bottle 1L",
        "price": 19291,
        "category": "kitchen",
    },
    "977": {
        "id": 977,
        "name": "Logitech G Pro X Keyboard Blue",
        "price": 65821,
        "category": "gaming",
    },
    "978": {
        "id": 978,
        "name": "HyperX Cloud II Gaming Headset Blue",
        "price": 45756,
        "category": "gaming",
    },
    "979": {
        "id": 979,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 6569,
        "category": "kitchen",
    },
    "980": {
        "id": 980,
        "name": "Milton Thermosteel Bottle 1L 2024 Model",
        "price": 7827,
        "category": "kitchen",
    },
    "981": {
        "id": 981,
        "name": "Nintendo Switch OLED Blue",
        "price": 38449,
        "category": "gaming",
    },
    "982": {
        "id": 982,
        "name": "OnePlus 11R",
        "price": 100773,
        "category": "electronics",
    },
    "983": {
        "id": 983,
        "name": "Allen Solly Cotton Shirt Pro Edition",
        "price": 4693,
        "category": "clothing",
    },
    "984": {
        "id": 984,
        "name": "Levi's 511 Slim Fit Jeans Silver",
        "price": 6614,
        "category": "clothing",
    },
    "985": {
        "id": 985,
        "name": "Dyson V12 Vacuum Cleaner 2024 Model",
        "price": 33440,
        "category": "home",
    },
    "986": {
        "id": 986,
        "name": "Bosch Mixer Grinder Silver",
        "price": 17834,
        "category": "kitchen",
    },
    "987": {
        "id": 987,
        "name": "Nike Air Max Shoes",
        "price": 4059,
        "category": "clothing",
    },
    "988": {
        "id": 988,
        "name": "Dyson V12 Vacuum Cleaner Black",
        "price": 31562,
        "category": "home",
    },
    "989": {
        "id": 989,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 19676,
        "category": "home",
    },
    "990": {
        "id": 990,
        "name": "Razer DeathAdder V3 Mouse Pro Edition",
        "price": 8885,
        "category": "gaming",
    },
    "991": {
        "id": 991,
        "name": "AmazonBasics Wall Clock Pro Edition",
        "price": 1582,
        "category": "home",
    },
    "992": {
        "id": 992,
        "name": "Milton Thermosteel Bottle 1L",
        "price": 1210,
        "category": "kitchen",
    },
    "993": {
        "id": 993,
        "name": "Razer DeathAdder V3 Mouse Black",
        "price": 40405,
        "category": "gaming",
    },
    "994": {
        "id": 994,
        "name": "Dyson V12 Vacuum Cleaner Silver",
        "price": 44560,
        "category": "home",
    },
    "995": {
        "id": 995,
        "name": "Sony PlayStation 5 Black",
        "price": 55271,
        "category": "gaming",
    },
    "996": {
        "id": 996,
        "name": "Milton Thermosteel Bottle 1L Pro Edition",
        "price": 13992,
        "category": "kitchen",
    },
    "997": {
        "id": 997,
        "name": "Havells Toaster Black",
        "price": 19769,
        "category": "kitchen",
    },
    "998": {
        "id": 998,
        "name": "Prestige Pressure Cooker Silver",
        "price": 10466,
        "category": "kitchen",
    },
    "999": {
        "id": 999,
        "name": "Adidas Supercourt Sneakers",
        "price": 1059,
        "category": "clothing",
    },
    "1000": {
        "id": 1000,
        "name": "Sony PlayStation 5 Black",
        "price": 56756,
        "category": "gaming",
    },
}
