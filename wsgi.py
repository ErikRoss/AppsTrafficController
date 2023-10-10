from app import app

if __name__ == "__main__":
    app.run(cors_allowed_origins=["http://localhost:3000", "*"])