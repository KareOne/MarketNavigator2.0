# Services Documentation

## Server Overview

| Server Name | Server IP | Host |
|------------|-----------|------|
| social-m-navigator | 46.34.163.68 | Liara |
| parspack | 185.11.191.128 | parspack |
| marketnavigatorv2 | 89.42.199.54 | Liara |

---

## 1. social-m-navigator (46.34.163.68)

### LinkedIn API

**Deployment Method:** Remote Desktop (Remmina)

**Remote Desktop Credentials:**
- Username: `social`
- Password: `9517530@Hm`

**⚠️ Important Notes:**
- The virtual environment (venv) must be activated before running
- Service runs on pure Python (no Docker)

**🚀 Starting the Service:**

1. Connect via remote desktop
2. Navigate to the project directory:
   ```bash
   cd Documents/projects/python_prjs/MarketNavigator/APIs/LinkedIn-API
   ```
3. Run the entrypoint script:
   ```bash
   ./entrypoint.sh
   ```
4. API will be available at: http://46.34.163.68:5001
5. View API documentation: http://46.34.163.68:5001/swagger

**🔧 Troubleshooting:**

If login fails, follow these steps:

1. Navigate to the login directory:
   ```bash
   cd Documents/projects/python_prjs/LinkedinLogin
   ```
2. Run the login script:
   ```bash
   python index.py
   ```
3. Manually login through Chrome
4. Press Enter in the terminal
5. Restart the service

---

## 2. parspack (185.11.191.128)

### Tracxn API

**Deployment Method:** Remote Desktop (Remmina)

**Remote Desktop Credentials:**
- Username: `test`
- Password: `9517530@Hm`

**⚠️ Important Notes:**
- The virtual environment (venv) must be activated before running
- Service runs on pure Python (no Docker)

**🚀 Starting the Service:**

1. Connect via remote desktop
2. Navigate to the project directory:
   ```bash
   cd ~/projects/MarketNavigator2.0/scrapers/Tracxn_API
   ```

### Crunchbase API

**Deployment Method:** Docker

**🚀 Starting the Service:**

1. SSH to server with root account
2. Navigate to the project directory:
   ```bash
   cd ~/projects/MarketNavigator2.0/scrapers/Crunchbase_API
   ```
3. Start the Docker container:
   ```bash
   docker-compose -f docker-compoer.remote.yml --env-file .env.remote up -d
   ```
4. API will be available at: http://185.11.191.128:8003

### Twitter API

**Deployment Method:** Docker

**🚀 Starting the Service:**

1. SSH to server with root account
2. Navigate to the project directory:
   ```bash
   cd ~/projects/MarketNavigator2.0/scrapers/Twitter_API
   ```
3. Start the Docker container:
   ```bash
   docker-compose -f docker-compoer.remote.yml up -d
   ```
4. API will be available at: http://185.11.191.128:8004

---

## 3. marketnavigatorv2 (89.42.199.54)

### Backend & Frontend

**Deployment Method:** Docker (both services)

**🚀 Starting the Services:**

1. SSH to server with root account
2. Navigate to the project directory:
   ```bash
   cd ~/MarketNavigator2.0/
   ```
3. Start all services:
   ```bash
   docker-compose -f docker-compoer.prod.yml up -d
   ```
4. Access the applications:
   - **Backend:** http://89.42.199.54:8000
   - **Frontend:** http://89.42.199.54:3000