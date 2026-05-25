# SnapMeal AI

Food image analysis with Google Gemini, verified nutrition via PySpark, and a Streamlit UI.

## Local run

```powershell
cd FoodAIProject
pip install -r requirements.txt
copy .env.example .env   # add GOOGLE_API_KEY
.\run_local.ps1
```

Open http://localhost:8501 (or the port Streamlit prints).

---

## Deploy on Amazon AWS (EC2) — step by step

This guide deploys the app on a single **EC2** instance with **nginx** in front of Streamlit. Best for a class project, demo, or low-traffic personal use.

### What you need

| Item | Details |
|------|---------|
| AWS account | [aws.amazon.com](https://aws.amazon.com) |
| Gemini API key | [Google AI Studio](https://aistudio.google.com/apikey) |
| SSH key pair | Created in EC2 during launch |
| Git repo | GitHub (or copy project via `scp`) |

**Recommended instance:** `t3.medium` (2 vCPU, 4 GB RAM) — PySpark needs memory.  
**OS:** **Amazon Linux 2023 AMI** (64-bit)  
**SSH user:** `ec2-user`  
**Region:** pick one close to you (e.g. `ap-south-1` Mumbai)

---

### Step 1 — Push code to GitHub

On your PC:

```powershell
cd C:\Users\arjit\Desktop\FoodAIProject
git init
git add .
git commit -m "SnapMeal AI with PySpark"
```

Create a repo on GitHub, then:

```powershell
git remote add origin https://github.com/YOUR_USER/FoodAIProject.git
git push -u origin main
```

Do **not** commit `.env` (API keys). Use `.env.example` only.

---

### Step 2 — Create an EC2 instance

1. AWS Console → **EC2** → **Launch instance**
2. **Name:** `snapmeal-ai`
3. **AMI:** **Amazon Linux 2023 AMI** (64-bit, x86) — *not* Amazon Linux 2 unless you adapt packages
4. **Instance type:** `t3.medium`
5. **Key pair:** Create new or select existing → download `.pem`
6. **Network / Security group:** Create security group with:

   | Type | Port | Source |
   |------|------|--------|
   | SSH | 22 | My IP |
   | HTTP | 80 | 0.0.0.0/0 |
   | HTTPS | 443 | 0.0.0.0/0 (optional, for SSL later) |

7. **Storage:** 20–30 GB gp3
8. **Launch instance**

9. Note the **Public IPv4 address** (e.g. `3.110.x.x`)

---

### Step 3 — Connect with SSH

Windows PowerShell:

```powershell
ssh -i "C:\path\to\your-key.pem" ec2-user@YOUR_EC2_PUBLIC_IP
```

First time: type `yes` when asked about host authenticity.

---

### Step 4 — Clone the project on the server

```bash
cd ~
git clone https://github.com/YOUR_USER/awsdeploy.git FoodAIProject
cd FoodAIProject
```

If you do not use GitHub, copy from your PC instead:

```powershell
scp -i "C:\path\to\your-key.pem" -r C:\Users\arjit\Desktop\FoodAIProject ec2-user@YOUR_EC2_PUBLIC_IP:~/
```

---

### Step 5 — Add your API key

On EC2:

```bash
cd ~/FoodAIProject
cp .env.example .env
nano .env
```

Set:

```
GOOGLE_API_KEY=your_actual_key
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

---

### Step 6 — Run the install script

```bash
chmod +x deploy/setup_ec2.sh
./deploy/setup_ec2.sh
```

This installs Java 17, Python, nginx, creates a venv, installs dependencies, and starts the `snapmeal` systemd service.

Wait 1–2 minutes on first start (PySpark initializes).

Check status:

```bash
sudo systemctl status snapmeal
sudo systemctl status nginx
```

Logs if something fails:

```bash
journalctl -u snapmeal -f
```

---

### Step 7 — Open the app in a browser

Visit:

```
http://YOUR_EC2_PUBLIC_IP
```

You should see SnapMeal AI. First page load may be slow while Spark starts.

---

### Step 8 — (Optional) HTTPS with a domain

1. Point a domain A record to your EC2 public IP (Route 53 or your registrar).
2. On EC2:

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

3. Update `deploy/nginx-snapmeal.conf` `server_name` to your domain, redeploy nginx.

---

### Step 9 — Update the app after changes

On EC2:

```bash
cd ~/FoodAIProject
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart snapmeal
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Site not loading | EC2 security group must allow HTTP (80); check `sudo systemctl status nginx` |
| `snapmeal` failed | `journalctl -u snapmeal -n 50` — often missing `.env` or bad API key |
| PySpark / Java error | `java -version` → 17; `echo $JAVA_HOME` (Corretto path) |
| 502 from nginx | `curl http://127.0.0.1:8501`; SELinux: `sudo setsebool -P httpd_can_network_connect 1` |
| Out of memory | Use `t3.medium` or larger; Spark needs ~2 GB free |

---

## Architecture (EC2)

```
Browser → :80 nginx → :8501 Streamlit → PySpark (local) + Gemini API
```

---

## Cost note

A `t3.medium` running 24/7 is roughly **$30–35/month** on-demand. Stop the instance when not needed to save money: EC2 → Instance → **Stop instance**.
