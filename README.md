# SmartLab — Digital Computer Lab Registration

A runnable educational prototype that replaces a paper lab register with a centralized web application. It supports multiple branches, years, labs, check-in/check-out, an admin dashboard, filters, hourly check-in visualization, and CSV export.

## Requirements
- Python 3.10 or newer
- Internet is needed only if you want the optional Google Fonts to load; the application itself works offline.
- For multi-PC testing, the server PC and client PCs must be on the same trusted LAN/Wi-Fi.

## Run on Windows
1. Extract the ZIP.
2. Open the extracted `smart_lab_system` folder.
3. Open Command Prompt/PowerShell in that folder.
4. Create a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, use Command Prompt:
   ```bat
   .venv\Scripts\activate.bat
   ```
5. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
6. Start the application:
   ```powershell
   python app.py
   ```
7. On that computer, open `http://127.0.0.1:5000`.

## Demo accounts
- Student PINs: `DS001`, `CS001`, `AI001`, `EC001`
- Admin username: `admin`
- Admin password: `ChangeMe123!`

Use only sample/demo records for a demonstration. Do not put real student details into this prototype until your faculty/college approves it.

## Test the app
1. Open the student page and enter `DS001`, then click **Find student**.
2. Select a free computer and a purpose, then click **Check in**.
3. Use the same PIN in the check-out section to end the visit.
4. Open Admin and sign in.
5. Pick today's date to see records; try branch/year filters and CSV export.
6. Use different demo PINs to test different branches and years.

## Connect another computer on a trusted lab network
1. Find the server PC's local IPv4 address (Windows: run `ipconfig` and look for IPv4 Address).
2. Allow Python on the private/trusted network in Windows Firewall, or add a narrowly scoped inbound rule for TCP port 5000. Follow college IT policy.
3. On another computer connected to the same LAN/Wi-Fi, open `http://SERVER-IP:5000`, replacing `SERVER-IP` with the server PC's actual IPv4 address.
4. Keep the server PC running while other PCs use the app.

Do not expose this development server directly to the public internet. For a real college rollout, deploy behind a production WSGI server with HTTPS, strong secrets, backups, role-based permissions, and IT approval. The demo admin password must be changed before any real deployment.

## Configure before a real deployment
- Set `LAB_ADMIN_USER`, `LAB_ADMIN_PASSWORD`, and `LAB_SECRET_KEY` environment variables before first start. The admin account is created on first database initialization; changing the environment password later does not automatically change an existing account.
- The app uses SQLite for a simple single-server prototype. It is suitable for demonstrating a central database, but a college-wide deployment with multiple labs/users should be reviewed by IT and may use MySQL/PostgreSQL.
- Add real students only with permission and through a controlled admin import workflow. This demo does not include a student-management screen.
- System numbers are selected from the list in this prototype. Automatic per-PC detection/configuration is a separate deployment feature.
