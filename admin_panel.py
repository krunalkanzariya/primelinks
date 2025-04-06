import os
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime, timedelta
import secrets
from database import Database
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
security = HTTPBasic()
db = Database()

# Create templates directory if it doesn't exist
os.makedirs("templates", exist_ok=True)

# Create templates
templates = Jinja2Templates(directory="templates")

def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(
        credentials.username, os.getenv("ADMIN_USERNAME", "admin")
    )
    correct_password = secrets.compare_digest(
        credentials.password, os.getenv("ADMIN_PASSWORD", "admin")
    )
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, admin: str = Depends(get_current_admin)):
    # Get statistics
    user_stats = db.get_user_stats()
    product_stats = db.get_product_stats()
    
    # Create HTML template
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Amazon Affiliate Bot Admin Panel</title>
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    </head>
    <body class="bg-gray-100">
        <div class="container mx-auto px-4 py-8">
            <h1 class="text-3xl font-bold mb-8">Admin Panel</h1>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- User Statistics -->
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-semibold mb-4">User Statistics</h2>
                    <div class="space-y-4">
                        <div class="flex justify-between">
                            <span class="text-gray-600">Total Users:</span>
                            <span class="font-semibold">{total_users}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">Total Interactions:</span>
                            <span class="font-semibold">{total_interactions}</span>
                        </div>
                    </div>
                </div>

                <!-- Product Statistics -->
                <div class="bg-white rounded-lg shadow p-6">
                    <h2 class="text-xl font-semibold mb-4">Product Statistics</h2>
                    <div class="space-y-4">
                        <div class="flex justify-between">
                            <span class="text-gray-600">Total Products:</span>
                            <span class="font-semibold">{total_products}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">Average Rating:</span>
                            <span class="font-semibold">{avg_rating:.1f}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """.format(
        total_users=user_stats['total_users'],
        total_interactions=user_stats['total_interactions'],
        total_products=product_stats['total_products'],
        avg_rating=product_stats['avg_rating'] or 0
    )
    
    return HTMLResponse(content=html_content)

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main() 
